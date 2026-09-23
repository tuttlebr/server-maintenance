use std::collections::{HashSet, VecDeque};
use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{anyhow, bail, Context, Result};
use clap::Parser;
use futures::stream::{FuturesUnordered, StreamExt};
use regex::Regex;
use reqwest::header::{CONTENT_TYPE, USER_AGENT};
use reqwest::{Client, StatusCode};
use scraper::{Html, Selector};
use serde::Deserialize;
use serde_json::{json, Value};
use url::Url;

const DEFAULT_EMBED_MODEL: &str = "nvidia/qwen/qwen3-embedding-0.6b";
const DEFAULT_EMBED_BASE_URL: &str = "https://inference-api.nvidia.com/v1";
const DEFAULT_MILVUS_URI: &str = "http://localhost:19530";
const DEFAULT_COLLECTION: &str = "fleet_docs";
const DEFAULT_MAX_CHUNK_CHARS: usize = 4000;
const DEFAULT_TEXT_FIELD_CHARS: usize = 16_384;

macro_rules! status {
    ($($arg:tt)*) => {{
        write_status(format_args!($($arg)*));
    }};
}

#[derive(Parser, Debug)]
#[command(
    author,
    version,
    about = "Crawl DGX docs, convert HTML to Markdown, embed, and ingest into Milvus"
)]
struct Cli {
    #[arg(long, default_value = "docs/urls.txt")]
    urls: PathBuf,

    /// Directory containing local Markdown files to include in the same Milvus index.
    #[arg(long)]
    local_docs_dir: Option<PathBuf>,

    /// Skip local Markdown files and only ingest crawled HTML documentation.
    #[arg(long, default_value_t = false)]
    no_local_markdown: bool,

    #[arg(long, default_value = ".env")]
    env_file: PathBuf,

    #[arg(long)]
    milvus_uri: Option<String>,

    #[arg(long, default_value = DEFAULT_COLLECTION)]
    collection: String,

    #[arg(long, default_value = "docs/crawled")]
    markdown_dir: PathBuf,

    #[arg(long, default_value_t = 8)]
    fetch_concurrency: usize,

    #[arg(long, default_value_t = 16)]
    embed_batch_size: usize,

    #[arg(long, default_value_t = 64)]
    insert_batch_size: usize,

    #[arg(long, default_value_t = DEFAULT_MAX_CHUNK_CHARS)]
    max_chunk_chars: usize,

    #[arg(long, default_value_t = DEFAULT_TEXT_FIELD_CHARS)]
    text_field_chars: usize,

    /// Maximum pages to crawl per input URL. 0 means unlimited within that URL's prefix.
    #[arg(long, default_value_t = 0)]
    max_pages_per_seed: usize,

    /// Keep an existing Milvus collection and append new rows. By default the collection is rebuilt.
    #[arg(long, default_value_t = false)]
    append: bool,

    /// Crawl and write Markdown, but skip embedding and Milvus writes.
    #[arg(long, default_value_t = false)]
    dry_run: bool,

    #[arg(long, default_value = "fleet-doc-ingester/0.1")]
    user_agent: String,

    #[arg(long, default_value_t = 45)]
    request_timeout_secs: u64,
}

#[derive(Debug, Clone)]
struct AppConfig {
    embed_model: String,
    embed_dim: Option<usize>,
    embed_base_url: String,
    embed_api_key: String,
    milvus_uri: String,
    milvus_token: Option<String>,
}

#[derive(Debug, Clone)]
struct CrawlScope {
    scheme: String,
    host: String,
    port: Option<u16>,
    prefix: String,
    source_label: String,
}

#[derive(Debug, Clone)]
struct PageDoc {
    url: Url,
    source: String,
    title: String,
    markdown: String,
}

#[derive(Debug, Clone)]
struct LocalMarkdownDoc {
    path: PathBuf,
    reference: String,
    source: String,
    title: String,
    markdown: String,
}

#[derive(Debug, Clone)]
struct DocChunk {
    source: String,
    heading: String,
    text: String,
}

#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingItem>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingItem {
    index: usize,
    embedding: Vec<f32>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    load_env(&cli.env_file)?;
    let config = AppConfig::from_env(&cli)?;

    let client = Client::builder()
        .timeout(Duration::from_secs(cli.request_timeout_secs))
        .redirect(reqwest::redirect::Policy::limited(10))
        .build()
        .context("failed to build HTTP client")?;

    let seeds = read_seed_urls(&cli.urls)?;
    if seeds.is_empty() {
        bail!("no URLs found in {}", cli.urls.display());
    }

    status!(
        "Loaded {} seed URL(s) from {}",
        seeds.len(),
        cli.urls.display()
    );
    status!("Using embedding model: {}", config.embed_model);

    let mut pages = Vec::new();
    let mut global_seen = HashSet::new();
    for seed in seeds {
        let scope = CrawlScope::from_seed(&seed);
        status!("Crawling {} under {}", seed, scope.prefix);
        let crawled = crawl_seed(
            client.clone(),
            seed,
            scope,
            cli.fetch_concurrency.max(1),
            cli.max_pages_per_seed,
            &cli.user_agent,
        )
        .await?;

        for page in crawled {
            let key = page.url.as_str().to_string();
            if global_seen.insert(key) {
                pages.push(page);
            }
        }
    }

    let local_docs_dir = cli
        .local_docs_dir
        .clone()
        .or_else(|| cli.urls.parent().map(Path::to_path_buf));
    let local_docs = if cli.no_local_markdown {
        Vec::new()
    } else if let Some(dir) = local_docs_dir.as_deref() {
        load_local_markdown_docs(dir)?
    } else {
        Vec::new()
    };
    if !local_docs.is_empty() {
        status!(
            "Loaded {} local Markdown doc(s) from {}",
            local_docs.len(),
            local_docs_dir
                .as_deref()
                .map(Path::display)
                .map(|display| display.to_string())
                .unwrap_or_else(|| "<none>".to_string())
        );
    }

    if pages.is_empty() && local_docs.is_empty() {
        bail!("crawler did not produce any HTML pages and no local Markdown docs were found");
    }

    write_markdown_pages(&pages, &cli.markdown_dir).with_context(|| {
        format!(
            "failed to write Markdown under {}",
            cli.markdown_dir.display()
        )
    })?;
    write_local_markdown_docs(&local_docs, &cli.markdown_dir).with_context(|| {
        format!(
            "failed to write local Markdown under {}",
            cli.markdown_dir.display()
        )
    })?;
    status!(
        "Wrote {} crawled Markdown page(s) and {} local Markdown doc(s) to {}",
        pages.len(),
        local_docs.len(),
        cli.markdown_dir.display()
    );

    let mut chunks = build_chunks(&pages, cli.max_chunk_chars, cli.text_field_chars);
    chunks.extend(build_local_chunks(
        &local_docs,
        cli.max_chunk_chars,
        cli.text_field_chars,
    ));
    if chunks.is_empty() {
        bail!("no non-empty chunks were produced from documentation content");
    }
    status!("Prepared {} Markdown chunk(s)", chunks.len());

    if cli.dry_run {
        status!("Dry run complete; skipped embeddings and Milvus writes");
        return Ok(());
    }

    if config.embed_api_key.is_empty() {
        bail!(
            "missing embedding API key; set EMBED_API_KEY or AI_HELPER_API_KEY in {}",
            cli.env_file.display()
        );
    }

    let embedder =
        EmbeddingClient::new(client.clone(), config.clone(), cli.embed_batch_size.max(1));
    let texts: Vec<&str> = chunks.iter().map(|chunk| chunk.text.as_str()).collect();
    let embeddings = embedder.embed_texts(&texts).await?;
    let actual_dim = embeddings
        .first()
        .map(|embedding| embedding.len())
        .ok_or_else(|| anyhow!("embedding API returned no vectors"))?;

    if let Some(configured_dim) = config.embed_dim {
        if configured_dim != actual_dim {
            bail!(
                "EMBED_DIM={} but {} returned {} dimensions",
                configured_dim,
                config.embed_model,
                actual_dim
            );
        }
    }

    let milvus = MilvusClient::new(
        client,
        config.milvus_uri,
        config.milvus_token,
        cli.collection,
    );
    milvus
        .ensure_collection(actual_dim, cli.text_field_chars, !cli.append)
        .await
        .context("failed to prepare Milvus collection")?;
    milvus
        .insert_chunks(&chunks, &embeddings, cli.insert_batch_size.max(1))
        .await
        .context("failed to insert chunks into Milvus")?;
    milvus
        .load_collection()
        .await
        .context("failed to load Milvus collection")?;

    status!(
        "Ingested {} chunk(s) from {} page(s) and {} local doc(s) into Milvus collection '{}'",
        chunks.len(),
        pages.len(),
        local_docs.len(),
        milvus.collection
    );

    Ok(())
}

fn load_env(env_file: &Path) -> Result<()> {
    if env_file.exists() {
        dotenvy::from_path(env_file)
            .with_context(|| format!("failed to read env file {}", env_file.display()))?;
    }
    Ok(())
}

fn write_status(args: std::fmt::Arguments<'_>) {
    let mut stdout = io::stdout().lock();
    let _ = writeln!(stdout, "{args}");
    let _ = stdout.flush();
}

impl AppConfig {
    fn from_env(cli: &Cli) -> Result<Self> {
        let embed_model =
            env::var("EMBED_MODEL").unwrap_or_else(|_| DEFAULT_EMBED_MODEL.to_string());
        let embed_dim = optional_usize("EMBED_DIM")?;
        let embed_base_url = env::var("EMBED_BASE_URL")
            .or_else(|_| env::var("AI_HELPER_BASE_URL"))
            .unwrap_or_else(|_| DEFAULT_EMBED_BASE_URL.to_string());
        let embed_api_key = env::var("EMBED_API_KEY")
            .or_else(|_| env::var("AI_HELPER_API_KEY"))
            .unwrap_or_default();
        let milvus_uri = cli
            .milvus_uri
            .clone()
            .or_else(|| env::var("MILVUS_URI").ok())
            .unwrap_or_else(|| DEFAULT_MILVUS_URI.to_string());
        let milvus_token = env::var("MILVUS_TOKEN")
            .ok()
            .filter(|token| !token.trim().is_empty());

        Ok(Self {
            embed_model,
            embed_dim,
            embed_base_url,
            embed_api_key,
            milvus_uri,
            milvus_token,
        })
    }
}

fn optional_usize(name: &str) -> Result<Option<usize>> {
    match env::var(name) {
        Ok(raw) if raw.trim().is_empty() => Ok(None),
        Ok(raw) => raw
            .trim()
            .parse::<usize>()
            .map(Some)
            .with_context(|| format!("{name} must be a positive integer")),
        Err(_) => Ok(None),
    }
}

fn read_seed_urls(path: &Path) -> Result<Vec<Url>> {
    let raw =
        fs::read_to_string(path).with_context(|| format!("failed to read {}", path.display()))?;
    raw.lines()
        .enumerate()
        .filter_map(|(idx, line)| {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('#') {
                None
            } else {
                Some(
                    Url::parse(trimmed)
                        .with_context(|| format!("invalid URL at {}:{}", path.display(), idx + 1)),
                )
            }
        })
        .collect()
}

impl CrawlScope {
    fn from_seed(seed: &Url) -> Self {
        let prefix = scope_prefix(seed.path());
        Self {
            scheme: seed.scheme().to_string(),
            host: seed.host_str().unwrap_or_default().to_string(),
            port: seed.port_or_known_default(),
            source_label: source_label_from_prefix(&prefix),
            prefix,
        }
    }

    fn contains(&self, url: &Url) -> bool {
        url.scheme() == self.scheme
            && url.host_str().unwrap_or_default() == self.host
            && url.port_or_known_default() == self.port
            && url.path().starts_with(&self.prefix)
            && is_htmlish(url.path())
            && !is_skipped_path(url.path())
    }
}

fn scope_prefix(path: &str) -> String {
    let normalized = if path.is_empty() { "/" } else { path };
    if normalized.ends_with('/') {
        return normalized.to_string();
    }

    let lower = normalized.to_ascii_lowercase();
    if lower.ends_with("/index.html")
        || lower.ends_with("/index.htm")
        || last_segment_has_extension(normalized)
    {
        let parent = normalized
            .rsplit_once('/')
            .map(|(parent, _)| parent)
            .unwrap_or("");
        return format!("{}/", parent.trim_end_matches('/'));
    }

    format!("{}/", normalized.trim_end_matches('/'))
}

fn last_segment_has_extension(path: &str) -> bool {
    path.rsplit('/')
        .next()
        .map(|segment| segment.contains('.'))
        .unwrap_or(false)
}

fn source_label_from_prefix(prefix: &str) -> String {
    let segment = prefix
        .trim_matches('/')
        .rsplit('/')
        .find(|part| !part.is_empty())
        .unwrap_or("docs");
    title_case(&segment.replace(['-', '_'], " "))
}

fn title_case(input: &str) -> String {
    input
        .split_whitespace()
        .map(|word| {
            let lower = word.to_ascii_lowercase();
            match lower.as_str() {
                "dgx" | "bmc" | "fw" | "os" | "api" => lower.to_ascii_uppercase(),
                _ if lower.starts_with("dgx") => lower.to_ascii_uppercase(),
                _ => {
                    let mut chars = lower.chars();
                    match chars.next() {
                        Some(first) => first.to_ascii_uppercase().to_string() + chars.as_str(),
                        None => String::new(),
                    }
                }
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn is_htmlish(path: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    if lower.ends_with('/') {
        return true;
    }
    match lower.rsplit('/').next() {
        Some(segment) if !segment.contains('.') => true,
        Some(segment) => segment.ends_with(".html") || segment.ends_with(".htm"),
        None => false,
    }
}

fn is_skipped_path(path: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    lower.contains("/_static/")
        || lower.contains("/_sources/")
        || lower.contains("/_images/")
        || lower.ends_with("/search.html")
        || lower.ends_with("/genindex.html")
        || lower.ends_with("/py-modindex.html")
}

async fn crawl_seed(
    client: Client,
    seed: Url,
    scope: CrawlScope,
    concurrency: usize,
    max_pages: usize,
    user_agent: &str,
) -> Result<Vec<PageDoc>> {
    let mut queue = VecDeque::from([normalize_url(seed)]);
    let mut seen = HashSet::new();
    let mut pages = Vec::new();
    let mut in_flight = FuturesUnordered::new();

    while !queue.is_empty() || !in_flight.is_empty() {
        while in_flight.len() < concurrency {
            if max_pages > 0 && seen.len() >= max_pages {
                queue.clear();
                break;
            }
            let Some(next) = queue.pop_front() else {
                break;
            };
            if !scope.contains(&next) || !seen.insert(next.as_str().to_string()) {
                continue;
            }
            in_flight.push(fetch_html(client.clone(), next, user_agent.to_string()));
        }

        let Some((url, result)) = in_flight.next().await else {
            continue;
        };

        let html = match result {
            Ok(html) => html,
            Err(err) => {
                status!("WARN: failed to fetch {url}: {err:#}");
                continue;
            }
        };

        for link in extract_links(&url, &html) {
            let normalized = normalize_url(link);
            if scope.contains(&normalized) && !seen.contains(normalized.as_str()) {
                queue.push_back(normalized);
            }
        }

        match html_to_page(&url, &scope.source_label, &html) {
            Ok(Some(page)) => pages.push(page),
            Ok(None) => {}
            Err(err) => status!("WARN: failed to convert {url}: {err:#}"),
        }
    }

    status!(
        "  crawled {} page(s) for {}",
        pages.len(),
        scope.source_label
    );
    Ok(pages)
}

async fn fetch_html(client: Client, url: Url, user_agent: String) -> (Url, Result<String>) {
    let result = async {
        let response = client
            .get(url.clone())
            .header(USER_AGENT, user_agent)
            .send()
            .await
            .with_context(|| format!("request failed for {url}"))?;

        if response.status() != StatusCode::OK {
            bail!("unexpected HTTP status {}", response.status());
        }

        let content_type = response
            .headers()
            .get(CONTENT_TYPE)
            .and_then(|value| value.to_str().ok())
            .unwrap_or_default()
            .to_ascii_lowercase();
        if !content_type.is_empty() && !content_type.contains("text/html") {
            bail!("unexpected content type {content_type}");
        }

        response
            .text()
            .await
            .context("failed to read response body")
    }
    .await;
    (url, result)
}

fn normalize_url(mut url: Url) -> Url {
    url.set_fragment(None);
    url.set_query(None);
    url
}

fn extract_links(base: &Url, html: &str) -> Vec<Url> {
    let document = Html::parse_document(html);
    let selector =
        Selector::parse("a[href], link[rel='next'][href], link[rel='prev'][href]").unwrap();
    document
        .select(&selector)
        .filter_map(|element| element.value().attr("href"))
        .filter(|href| {
            let lower = href.trim().to_ascii_lowercase();
            !lower.starts_with("mailto:")
                && !lower.starts_with("javascript:")
                && !lower.starts_with("tel:")
                && !lower.starts_with("data:")
        })
        .filter_map(|href| base.join(href).ok())
        .collect()
}

fn html_to_page(url: &Url, source: &str, html: &str) -> Result<Option<PageDoc>> {
    let document = Html::parse_document(html);
    let content_html = select_content_html(&document).unwrap_or_else(|| html.to_string());
    let content_html = strip_sphinx_headerlinks(&content_html)?;
    let markdown = clean_markdown(&html2md::parse_html(&content_html))?;
    if markdown.len() < 50 {
        return Ok(None);
    }

    let title = extract_title(&document).unwrap_or_else(|| url.path().to_string());
    Ok(Some(PageDoc {
        url: url.clone(),
        source: source.to_string(),
        title,
        markdown,
    }))
}

fn select_content_html(document: &Html) -> Option<String> {
    let selectors = [
        "article.bd-article",
        "article",
        "main",
        "div.document",
        "div.body",
        "div[role='main']",
        "#main-content",
        "body",
    ];

    selectors.iter().find_map(|selector| {
        let selector = Selector::parse(selector).ok()?;
        document
            .select(&selector)
            .map(|element| {
                let text_len = element.text().collect::<String>().trim().len();
                (text_len, element.inner_html())
            })
            .max_by_key(|(text_len, _)| *text_len)
            .and_then(|(text_len, html)| if text_len > 40 { Some(html) } else { None })
    })
}

fn extract_title(document: &Html) -> Option<String> {
    for selector in ["article h1", "main h1", "h1", "title"] {
        let selector = Selector::parse(selector).ok()?;
        if let Some(element) = document.select(&selector).next() {
            let raw = element.text().collect::<Vec<_>>().join(" ");
            let title = normalize_space(raw.split(['—', '|']).next().unwrap_or(raw.as_str()));
            if !title.is_empty() {
                return Some(title);
            }
        }
    }
    None
}

fn strip_sphinx_headerlinks(html: &str) -> Result<String> {
    let re = Regex::new(r#"<a[^>]*class="[^"]*headerlink[^"]*"[^>]*>.*?</a>"#)?;
    Ok(re.replace_all(html, "").to_string())
}

fn clean_markdown(markdown: &str) -> Result<String> {
    let inline_headerlink = Regex::new(r"\s*\[#\]\([^)]+\)")?;
    let blank_lines = Regex::new(r"\n{3,}")?;
    let mut cleaned = inline_headerlink.replace_all(markdown, "").to_string();
    cleaned = cleaned
        .lines()
        .map(str::trim_end)
        .filter(|line| {
            let trimmed = line.trim();
            !matches!(
                trimmed,
                "Skip to main content" | "Back to top" | "NVIDIA Docs Hub" | "NVIDIA DGX Platform"
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    cleaned = blank_lines.replace_all(&cleaned, "\n\n").to_string();
    Ok(cleaned.trim().to_string())
}

fn normalize_space(input: &str) -> String {
    input.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn load_local_markdown_docs(dir: &Path) -> Result<Vec<LocalMarkdownDoc>> {
    if !dir.exists() {
        status!(
            "WARN: local Markdown directory does not exist: {}",
            dir.display()
        );
        return Ok(Vec::new());
    }

    let mut paths = Vec::new();
    for entry in fs::read_dir(dir)
        .with_context(|| format!("failed to read local Markdown directory {}", dir.display()))?
    {
        let entry =
            entry.with_context(|| format!("failed to read entry under {}", dir.display()))?;
        let path = entry.path();
        if path.is_file()
            && path
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| ext.eq_ignore_ascii_case("md"))
                .unwrap_or(false)
        {
            paths.push(path);
        }
    }
    paths.sort();

    let dir_label = dir
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("docs");

    let mut docs = Vec::new();
    for path in paths {
        let raw = fs::read_to_string(&path)
            .with_context(|| format!("failed to read local Markdown {}", path.display()))?;
        let markdown = clean_markdown(&raw)
            .with_context(|| format!("failed to clean local Markdown {}", path.display()))?;
        if markdown.trim().len() < 50 {
            continue;
        }

        let title = extract_markdown_title(&markdown).unwrap_or_else(|| {
            path.file_stem()
                .and_then(|stem| stem.to_str())
                .map(|stem| title_case(&stem.replace(['-', '_'], " ")))
                .unwrap_or_else(|| "Local Documentation".to_string())
        });
        let reference = path
            .strip_prefix(dir)
            .ok()
            .map(|relative| format!("{dir_label}/{}", relative.display()))
            .unwrap_or_else(|| path.display().to_string());

        docs.push(LocalMarkdownDoc {
            path,
            reference,
            source: title.clone(),
            title,
            markdown,
        });
    }

    Ok(docs)
}

fn extract_markdown_title(markdown: &str) -> Option<String> {
    markdown.lines().find_map(markdown_heading)
}

fn write_markdown_pages(pages: &[PageDoc], markdown_dir: &Path) -> Result<()> {
    fs::create_dir_all(markdown_dir)?;
    for page in pages {
        let path = markdown_path(markdown_dir, &page.url);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let content = format!(
            "---\nsource: {}\nurl: {}\ntitle: {}\n---\n\n{}",
            page.source, page.url, page.title, page.markdown
        );
        fs::write(path, content)?;
    }
    Ok(())
}

fn write_local_markdown_docs(docs: &[LocalMarkdownDoc], markdown_dir: &Path) -> Result<()> {
    let local_dir = markdown_dir.join("local");
    fs::create_dir_all(&local_dir)?;
    for doc in docs {
        let path = local_markdown_path(markdown_dir, &doc.path);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let content = format!(
            "---\nsource: {}\npath: {}\ntitle: {}\n---\n\n{}",
            doc.source, doc.reference, doc.title, doc.markdown
        );
        fs::write(path, content)?;
    }
    Ok(())
}

fn markdown_path(base: &Path, url: &Url) -> PathBuf {
    let host = url.host_str().unwrap_or("site");
    let slug = slugify(url.path().trim_matches('/'), "index");
    base.join(host).join(format!("{slug}.md"))
}

fn local_markdown_path(base: &Path, path: &Path) -> PathBuf {
    let stem = path
        .file_stem()
        .and_then(|stem| stem.to_str())
        .unwrap_or("local-doc");
    let slug = slugify(stem, "local-doc");
    base.join("local").join(format!("{slug}.md"))
}

fn slugify(input: &str, fallback: &str) -> String {
    let mut slug = input.replace(|c: char| !c.is_ascii_alphanumeric(), "-");
    if slug.is_empty() {
        slug = fallback.to_string();
    }
    while slug.contains("--") {
        slug = slug.replace("--", "-");
    }
    slug = slug.trim_matches('-').to_string();
    if slug.len() > 180 {
        slug.truncate(180);
        slug = slug.trim_matches('-').to_string();
    }
    if slug.is_empty() {
        fallback.to_string()
    } else {
        slug
    }
}

fn build_chunks(
    pages: &[PageDoc],
    max_chunk_chars: usize,
    text_field_chars: usize,
) -> Vec<DocChunk> {
    let max_text_chars = max_chunk_chars
        .min(text_field_chars.saturating_sub(256))
        .max(500);
    let mut chunks = Vec::new();

    for page in pages {
        let sections = split_markdown_sections(&page.markdown, &page.title);
        for (heading, section_text) in sections {
            let heading = if heading.eq_ignore_ascii_case(&page.title) {
                heading
            } else {
                format!("{}: {}", page.title, heading)
            };
            let text_prefix = format!("Source URL: {}\n\n", page.url);
            let available = max_text_chars.saturating_sub(text_prefix.len()).max(500);
            for (part_heading, part_text) in split_large_text(&section_text, &heading, available) {
                let text = format!("{}{}", text_prefix, part_text);
                if text.trim().len() >= 50 {
                    chunks.push(DocChunk {
                        source: truncate_field(&page.source, 256),
                        heading: truncate_field(&part_heading, 512),
                        text: truncate_field(&text, text_field_chars),
                    });
                }
            }
        }
    }

    chunks
}

fn build_local_chunks(
    docs: &[LocalMarkdownDoc],
    max_chunk_chars: usize,
    text_field_chars: usize,
) -> Vec<DocChunk> {
    let max_text_chars = max_chunk_chars
        .min(text_field_chars.saturating_sub(256))
        .max(500);
    let mut chunks = Vec::new();

    for doc in docs {
        let sections = split_markdown_sections(&doc.markdown, &doc.title);
        for (heading, section_text) in sections {
            let heading = if heading.eq_ignore_ascii_case(&doc.title) {
                heading
            } else {
                format!("{}: {}", doc.title, heading)
            };
            let text_prefix = format!(
                "Source: {}\nLocal document: {}\n\n",
                doc.source, doc.reference
            );
            let available = max_text_chars.saturating_sub(text_prefix.len()).max(500);
            for (part_heading, part_text) in split_large_text(&section_text, &heading, available) {
                let text = format!("{}{}", text_prefix, part_text);
                if text.trim().len() >= 50 {
                    chunks.push(DocChunk {
                        source: truncate_field(&doc.source, 256),
                        heading: truncate_field(&part_heading, 512),
                        text: truncate_field(&text, text_field_chars),
                    });
                }
            }
        }
    }

    chunks
}

fn split_markdown_sections(markdown: &str, default_heading: &str) -> Vec<(String, String)> {
    let mut sections = Vec::new();
    let mut current_heading = default_heading.to_string();
    let mut current = String::new();

    for line in markdown.lines() {
        if let Some(heading) = markdown_heading(line) {
            if current.trim().len() >= 50 {
                sections.push((current_heading.clone(), current.trim().to_string()));
            }
            current_heading = heading;
            current.clear();
        }
        current.push_str(line);
        current.push('\n');
    }

    if current.trim().len() >= 50 {
        sections.push((current_heading, current.trim().to_string()));
    }

    sections
}

fn markdown_heading(line: &str) -> Option<String> {
    let trimmed = line.trim();
    let hashes = trimmed.chars().take_while(|ch| *ch == '#').count();
    if hashes == 0 || hashes > 6 {
        return None;
    }
    let rest = trimmed[hashes..].trim().trim_matches('#').trim();
    if rest.is_empty() {
        None
    } else {
        Some(rest.to_string())
    }
}

fn split_large_text(text: &str, heading: &str, max_chars: usize) -> Vec<(String, String)> {
    if text.len() <= max_chars {
        return vec![(heading.to_string(), text.to_string())];
    }

    let mut chunks = Vec::new();
    let mut current = String::new();
    let mut part_num = 1;

    for paragraph in text.split("\n\n") {
        let paragraph_parts = split_long_paragraph(paragraph, max_chars);
        for part in paragraph_parts {
            let separator = if current.is_empty() { 0 } else { 2 };
            if !current.is_empty() && current.len() + part.len() + separator > max_chars {
                chunks.push((
                    format!("{heading} (part {part_num})"),
                    current.trim().to_string(),
                ));
                current.clear();
                part_num += 1;
            }
            if !current.is_empty() {
                current.push_str("\n\n");
            }
            current.push_str(&part);
        }
    }

    if !current.trim().is_empty() {
        let label = if part_num > 1 {
            format!("{heading} (part {part_num})")
        } else {
            heading.to_string()
        };
        chunks.push((label, current.trim().to_string()));
    }

    chunks
}

fn split_long_paragraph(paragraph: &str, max_chars: usize) -> Vec<String> {
    if paragraph.len() <= max_chars {
        return vec![paragraph.to_string()];
    }

    let mut parts = Vec::new();
    let mut current = String::new();
    for word in paragraph.split_whitespace() {
        if word.len() > max_chars {
            if !current.trim().is_empty() {
                parts.push(current.trim().to_string());
                current.clear();
            }
            let mut piece = String::new();
            for ch in word.chars() {
                if piece.len() + ch.len_utf8() > max_chars {
                    parts.push(piece);
                    piece = String::new();
                }
                piece.push(ch);
            }
            if !piece.is_empty() {
                parts.push(piece);
            }
            continue;
        }

        let separator = if current.is_empty() { 0 } else { 1 };
        if !current.is_empty() && current.len() + word.len() + separator > max_chars {
            parts.push(current.trim().to_string());
            current.clear();
        }
        if !current.is_empty() {
            current.push(' ');
        }
        current.push_str(word);
    }

    if !current.trim().is_empty() {
        parts.push(current.trim().to_string());
    }

    parts
}

fn truncate_field(input: &str, max_bytes: usize) -> String {
    if input.len() <= max_bytes {
        return input.to_string();
    }
    let mut output = String::new();
    for ch in input.chars() {
        if output.len() + ch.len_utf8() > max_bytes {
            break;
        }
        output.push(ch);
    }
    output.trim().to_string()
}

struct EmbeddingClient {
    http: Client,
    base_url: String,
    api_key: String,
    model: String,
    batch_size: usize,
}

impl EmbeddingClient {
    fn new(http: Client, config: AppConfig, batch_size: usize) -> Self {
        Self {
            http,
            base_url: config.embed_base_url.trim_end_matches('/').to_string(),
            api_key: config.embed_api_key,
            model: config.embed_model,
            batch_size,
        }
    }

    async fn embed_texts(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>> {
        let mut embeddings = Vec::with_capacity(texts.len());
        let total_batches = (texts.len() + self.batch_size - 1) / self.batch_size;

        for (batch_idx, batch) in texts.chunks(self.batch_size).enumerate() {
            status!("Embedding batch {}/{}", batch_idx + 1, total_batches);
            let mut batch_embeddings = self.call_embeddings(batch).await?;
            embeddings.append(&mut batch_embeddings);
        }

        Ok(embeddings)
    }

    async fn call_embeddings(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>> {
        let url = format!("{}/embeddings", self.base_url);
        let response = self
            .http
            .post(url)
            .bearer_auth(&self.api_key)
            .json(&json!({
                "model": self.model,
                "input": texts,
                "encoding_format": "float",
                "input_type": "passage"
            }))
            .send()
            .await
            .context("embedding request failed")?;

        let status = response.status();
        let body = response
            .text()
            .await
            .context("failed to read embedding response")?;
        if !status.is_success() {
            bail!("embedding API returned {status}: {body}");
        }

        let mut parsed: EmbeddingResponse = serde_json::from_str(&body)
            .with_context(|| format!("invalid embedding response: {body}"))?;
        parsed.data.sort_by_key(|item| item.index);
        Ok(parsed.data.into_iter().map(|item| item.embedding).collect())
    }
}

struct MilvusClient {
    http: Client,
    base_url: String,
    token: Option<String>,
    collection: String,
}

impl MilvusClient {
    fn new(http: Client, uri: String, token: Option<String>, collection: String) -> Self {
        Self {
            http,
            base_url: uri.trim_end_matches('/').to_string(),
            token,
            collection,
        }
    }

    async fn ensure_collection(
        &self,
        dim: usize,
        text_field_chars: usize,
        rebuild: bool,
    ) -> Result<()> {
        if self.has_collection().await? {
            if rebuild {
                status!("Dropping existing Milvus collection '{}'", self.collection);
                self.drop_collection().await?;
            } else {
                status!(
                    "Appending to existing Milvus collection '{}'",
                    self.collection
                );
                return Ok(());
            }
        }

        status!(
            "Creating Milvus collection '{}' (dim={dim})",
            self.collection
        );
        self.create_collection(dim, text_field_chars).await
    }

    async fn has_collection(&self) -> Result<bool> {
        let data = self
            .post_json(
                "/v2/vectordb/collections/has",
                json!({ "collectionName": self.collection }),
            )
            .await?;
        Ok(data.get("has").and_then(Value::as_bool).unwrap_or(false))
    }

    async fn drop_collection(&self) -> Result<()> {
        self.post_json(
            "/v2/vectordb/collections/drop",
            json!({ "collectionName": self.collection }),
        )
        .await?;
        Ok(())
    }

    async fn create_collection(&self, dim: usize, text_field_chars: usize) -> Result<()> {
        self.post_json(
            "/v2/vectordb/collections/create",
            json!({
                "collectionName": self.collection,
                "schema": {
                    "autoId": true,
                    "enabledDynamicField": false,
                    "fields": [
                        {
                            "fieldName": "id",
                            "dataType": "Int64",
                            "isPrimary": true
                        },
                        {
                            "fieldName": "source",
                            "dataType": "VarChar",
                            "elementTypeParams": { "max_length": "256" }
                        },
                        {
                            "fieldName": "heading",
                            "dataType": "VarChar",
                            "elementTypeParams": { "max_length": "512" }
                        },
                        {
                            "fieldName": "text",
                            "dataType": "VarChar",
                            "elementTypeParams": { "max_length": text_field_chars.to_string() }
                        },
                        {
                            "fieldName": "vector",
                            "dataType": "FloatVector",
                            "elementTypeParams": { "dim": dim.to_string() }
                        }
                    ]
                },
                "indexParams": [
                    {
                        "fieldName": "vector",
                        "metricType": "L2",
                        "indexName": "vector",
                        "params": {
                            "index_type": "IVF_FLAT",
                            "nlist": "64"
                        }
                    }
                ]
            }),
        )
        .await?;
        Ok(())
    }

    async fn insert_chunks(
        &self,
        chunks: &[DocChunk],
        embeddings: &[Vec<f32>],
        batch_size: usize,
    ) -> Result<()> {
        if chunks.len() != embeddings.len() {
            bail!(
                "chunk count {} did not match embedding count {}",
                chunks.len(),
                embeddings.len()
            );
        }

        let total_batches = (chunks.len() + batch_size - 1) / batch_size;
        for (batch_idx, (chunk_batch, embedding_batch)) in chunks
            .chunks(batch_size)
            .zip(embeddings.chunks(batch_size))
            .enumerate()
        {
            status!("Inserting Milvus batch {}/{}", batch_idx + 1, total_batches);
            let data: Vec<Value> = chunk_batch
                .iter()
                .zip(embedding_batch.iter())
                .map(|(chunk, vector)| {
                    json!({
                        "source": chunk.source,
                        "heading": chunk.heading,
                        "text": chunk.text,
                        "vector": vector
                    })
                })
                .collect();

            self.post_json(
                "/v2/vectordb/entities/insert",
                json!({
                    "collectionName": self.collection,
                    "data": data
                }),
            )
            .await?;
        }

        Ok(())
    }

    async fn load_collection(&self) -> Result<()> {
        self.post_json(
            "/v2/vectordb/collections/load",
            json!({ "collectionName": self.collection }),
        )
        .await?;
        Ok(())
    }

    async fn post_json(&self, path: &str, body: Value) -> Result<Value> {
        let url = format!("{}{}", self.base_url, path);
        let mut request = self.http.post(url).json(&body);
        if let Some(token) = &self.token {
            request = request.bearer_auth(token);
        }

        let response = request
            .send()
            .await
            .with_context(|| format!("Milvus request failed for {path}"))?;
        let status = response.status();
        let text = response
            .text()
            .await
            .context("failed to read Milvus response")?;
        if !status.is_success() {
            bail!("Milvus returned HTTP {status} for {path}: {text}");
        }

        let value: Value = serde_json::from_str(&text)
            .with_context(|| format!("invalid Milvus response for {path}: {text}"))?;
        let code = value
            .get("code")
            .and_then(|raw| {
                raw.as_i64()
                    .or_else(|| raw.as_str().and_then(|s| s.parse().ok()))
            })
            .unwrap_or(0);
        if code != 0 {
            let message = value
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("unknown Milvus error");
            bail!("Milvus returned code {code} for {path}: {message}");
        }
        Ok(value.get("data").cloned().unwrap_or(Value::Null))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seed_scope_uses_guide_directory_for_index_pages() {
        let url = Url::parse("https://docs.nvidia.com/dgx/dgxb300-user-guide/index.html").unwrap();
        let scope = CrawlScope::from_seed(&url);
        assert_eq!(scope.prefix, "/dgx/dgxb300-user-guide/");
        assert!(scope.contains(
            &Url::parse("https://docs.nvidia.com/dgx/dgxb300-user-guide/foo.html").unwrap()
        ));
        assert!(!scope.contains(&Url::parse("https://docs.nvidia.com/dgx/other/foo.html").unwrap()));
    }

    #[test]
    fn split_large_text_keeps_chunks_under_limit() {
        let text = "a ".repeat(1000);
        let chunks = split_large_text(&text, "Heading", 100);
        assert!(chunks.len() > 1);
        assert!(chunks.iter().all(|(_, chunk)| chunk.len() <= 100));
    }

    #[test]
    fn markdown_heading_extracts_hash_headings() {
        assert_eq!(
            markdown_heading("## Power Specifications"),
            Some("Power Specifications".to_string())
        );
        assert_eq!(markdown_heading("plain text"), None);
    }

    #[test]
    fn local_markdown_chunks_include_reference() {
        let docs = vec![LocalMarkdownDoc {
            path: PathBuf::from("docs/fleet-manager-ui.md"),
            reference: "docs/fleet-manager-ui.md".to_string(),
            source: "Fleet Manager UI Guide".to_string(),
            title: "Fleet Manager UI Guide".to_string(),
            markdown: "# Fleet Manager UI Guide\n\n## Operations\n\nUse Operations to run actions supported by each device's discovered capabilities.".to_string(),
        }];

        let chunks = build_local_chunks(&docs, 1000, 2000);

        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].source, "Fleet Manager UI Guide");
        assert!(chunks[0].text.contains("docs/fleet-manager-ui.md"));
        assert_eq!(chunks[0].heading, "Fleet Manager UI Guide: Operations");
    }
}
