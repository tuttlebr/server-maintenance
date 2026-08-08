<template>
  <div v-if="chatAvailable" class="help-chat">
    <button
      v-if="!isOpen"
      class="chat-fab"
      :class="{ 'chat-fab-pulse': showCoach }"
      type="button"
      aria-label="Ask DGX Help — questions about drivers, networking, troubleshooting"
      title="Ask DGX Help"
      @click="open"
    >
      <i class="fas fa-comments" aria-hidden="true"></i>
    </button>
    <span v-if="!isOpen && showCoach" class="chat-fab-coach" role="status">
      Ask DGX Help
      <button class="chat-fab-coach-close" type="button" aria-label="Dismiss tip" @click.stop="dismissCoach">&times;</button>
    </span>

    <div v-if="isOpen" class="chat-panel" role="dialog" aria-label="DGX Help">
      <div class="chat-header">
        <span class="chat-title">
          <i class="fas fa-robot" aria-hidden="true"></i> DGX Help
        </span>
        <div class="chat-header-actions">
          <button
            class="chat-icon-btn"
            type="button"
            aria-label="Clear chat history"
            title="Clear history"
            :disabled="isStreaming || messages.length === 0"
            @click="clearHistory"
          >
            <i class="fas fa-trash-alt" aria-hidden="true"></i>
          </button>
          <button class="chat-close" type="button" aria-label="Close chat" @click="isOpen = false">&times;</button>
        </div>
      </div>

      <div ref="messagesEl" class="chat-messages">
        <div v-if="messages.length === 0 && !isStreaming" class="chat-welcome">
          <p><strong>Hi! I can help with DGX systems.</strong></p>
          <p>Ask about DGX Spark, A100, H100 setup, drivers, networking, and more.</p>
        </div>

        <template v-for="(msg, i) in messages" :key="i">
          <div :class="['chat-msg', `chat-msg-${msg.role}`]">
            <div class="chat-msg-content chat-msg-markdown" v-html="renderMarkdown(msg.content)"></div>
            <button
              v-if="msg.steps && msg.steps.length"
              type="button"
              class="chat-steps-toggle"
              :aria-expanded="!!stepsOpen[i]"
              @click="stepsOpen[i] = !stepsOpen[i]"
            >
              <i :class="['fas', stepsOpen[i] ? 'fa-chevron-down' : 'fa-chevron-right']" aria-hidden="true"></i>
              {{ msg.steps.length }} {{ msg.steps.length === 1 ? "step" : "steps" }}
            </button>
            <ul v-if="stepsOpen[i]" class="chat-steps-list">
              <li v-for="(s, si) in msg.steps" :key="si">
                <i class="fas fa-check" aria-hidden="true"></i> {{ s }}
              </li>
            </ul>
          </div>
        </template>

        <div v-if="isStreaming" class="chat-msg chat-msg-assistant chat-msg-streaming">
          <ul v-if="currentSteps.length" class="chat-streaming-steps">
            <li v-for="(s, i) in currentSteps.slice(0, -1)" :key="i" class="chat-streaming-step done">
              <i class="fas fa-check" aria-hidden="true"></i> {{ s }}
            </li>
            <li v-if="!streamingContent.trim()" class="chat-streaming-step active">
              <span class="dot dot-blue dot-pulse" aria-hidden="true"></span>
              {{ currentSteps[currentSteps.length - 1] }}
              <span class="chat-streaming-dots"><span></span><span></span><span></span></span>
            </li>
            <li v-else class="chat-streaming-step done">
              <i class="fas fa-check" aria-hidden="true"></i> {{ currentSteps[currentSteps.length - 1] }}
            </li>
          </ul>
          <div v-else-if="!streamingContent.trim()" class="chat-streaming-step active chat-streaming-step-solo">
            <span class="dot dot-blue dot-pulse" aria-hidden="true"></span>
            Thinking
            <span class="chat-streaming-dots"><span></span><span></span><span></span></span>
          </div>

          <div
            v-if="streamingContent.trim()"
            class="chat-msg-content chat-msg-markdown"
            v-html="renderMarkdown(cleanedStreamingContent, true)"
          ></div>
        </div>
      </div>

      <form class="chat-input-area" @submit.prevent="send">
        <label class="visually-hidden" for="chat-input">Ask DGX Help</label>
        <input
          id="chat-input"
          ref="inputEl"
          v-model="input"
          class="form-input chat-input"
          placeholder="Ask about DGX systems…"
          :disabled="isStreaming"
          autocomplete="off"
        />
        <button
          type="submit"
          class="btn btn-green btn-sm chat-send"
          :aria-label="isStreaming ? 'Sending' : 'Send message'"
          :disabled="!input.trim() || isStreaming"
        >
          <i :class="['fas', isStreaming ? 'fa-spinner fa-spin' : 'fa-paper-plane']" aria-hidden="true"></i>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import DOMPurify from "dompurify";
import { marked } from "marked";
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { getChatStatus, streamChat } from "../api";

const MARKDOWN_TAGS = [
  "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3",
  "h4", "h5", "h6", "hr", "input", "li", "ol", "p", "pre", "strong",
  "table", "tbody", "td", "th", "thead", "tr", "ul",
];
const MARKDOWN_ATTRIBUTES = [
  "align", "checked", "class", "disabled", "href", "rel", "start", "target",
  "title", "type",
];
const MARKDOWN_OPTIONS = {
  async: false,
  breaks: true,
  gfm: true,
};

const chatAvailable = ref(false);
const isOpen = ref(false);
const messages = ref([]);
const input = ref("");
const isStreaming = ref(false);
const showCoach = ref(false);
let coachTimer = null;
const streamingContent = ref("");
const currentSteps = ref([]); // status updates received during this turn
const currentTurnPriorAssistantAnswers = ref([]);
const stepsOpen = reactive({});
const messagesEl = ref(null);
const inputEl = ref(null);

let streamController = null;

// While streaming, the model may emit leading whitespace/newlines as it
// reasons. Don't let that balloon the bubble — only render once a real
// character arrives, and collapse 3+ consecutive newlines down to 2.
const cleanedStreamingContent = computed(() => {
  const raw = streamingContent.value;
  if (!raw) return "";
  // Trim leading whitespace; preserve trailing space (cursor sits at end).
  const cleaned = raw.replace(/^\s+/, "").replace(/\n{3,}/g, "\n\n");
  return stripLeadingRepeatedAnswers(cleaned, currentTurnPriorAssistantAnswers.value);
});

function renderMarkdown(content, includeCursor = false) {
  const source = String(content || "");
  let parsed;
  try {
    parsed = marked.parse(source, MARKDOWN_OPTIONS);
  } catch {
    parsed = source;
  }

  const sanitized = DOMPurify.sanitize(parsed, {
    ALLOWED_ATTR: MARKDOWN_ATTRIBUTES,
    ALLOWED_TAGS: MARKDOWN_TAGS,
    ALLOW_DATA_ATTR: false,
  });
  const template = document.createElement("template");
  template.innerHTML = sanitized;

  template.content.querySelectorAll("a[href]").forEach((link) => {
    if (!link.getAttribute("href")?.startsWith("#")) {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }
  });

  if (includeCursor) {
    const cursor = document.createElement("span");
    cursor.className = "chat-cursor";
    cursor.setAttribute("aria-hidden", "true");
    cursor.textContent = "|";
    const lastBlock = template.content.lastElementChild;
    if (lastBlock?.tagName === "P") {
      lastBlock.append(cursor);
    } else {
      template.content.append(cursor);
    }
  }

  return template.innerHTML;
}

onMounted(async () => {
  try {
    const status = await getChatStatus();
    chatAvailable.value = status.available;
  } catch {
    chatAvailable.value = false;
  }
  if (chatAvailable.value && !localStorage.getItem("dgx-help-seen")) {
    showCoach.value = true;
    coachTimer = setTimeout(() => {
      showCoach.value = false;
    }, 12_000);
  }
  window.addEventListener("helpchat:open", onExternalOpen);
});

function onExternalOpen(e) {
  const prompt = e?.detail?.prompt;
  open();
  if (prompt) {
    nextTick(() => {
      input.value = prompt;
      inputEl.value?.focus();
    });
  }
}

onUnmounted(() => {
  window.removeEventListener("helpchat:open", onExternalOpen);
  clearTimeout(coachTimer);
});

function dismissCoach() {
  showCoach.value = false;
  clearTimeout(coachTimer);
  localStorage.setItem("dgx-help-seen", "1");
}

watch(isOpen, (open) => {
  if (open) nextTick(() => inputEl.value?.focus());
});

function open() {
  isOpen.value = true;
  showCoach.value = false;
  clearTimeout(coachTimer);
  localStorage.setItem("dgx-help-seen", "1");
}

function clearHistory() {
  if (isStreaming.value) return;
  messages.value = [];
  currentSteps.value = [];
  currentTurnPriorAssistantAnswers.value = [];
  streamingContent.value = "";
  Object.keys(stepsOpen).forEach((key) => delete stepsOpen[key]);
  nextTick(() => inputEl.value?.focus());
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
    }
  });
}

function send() {
  const text = input.value.trim();
  if (!text || isStreaming.value) return;

  currentTurnPriorAssistantAnswers.value = messages.value
    .filter((m) => m.role === "assistant" && m.content && !m.excludeFromHistory)
    .map((m) => m.content);
  messages.value.push({ role: "user", content: text });
  input.value = "";
  isStreaming.value = true;
  streamingContent.value = "";
  currentSteps.value = [];
  scrollToBottom();

  const chatMessages = messages.value
    .filter((m) => !m.excludeFromHistory)
    .map((m) => ({ role: m.role, content: m.content }));

  streamController = new AbortController();

  streamChat(chatMessages, {
    signal: streamController.signal,
    onStatus: (statusText) => {
      // De-dupe back-to-back identical statuses; collapse minor variants
      // (e.g., the same tool announced twice as it accumulates arguments).
      const trimmed = statusText.trim();
      if (!trimmed) return;
      const last = currentSteps.value[currentSteps.value.length - 1];
      if (last === trimmed) return;
      // Replace the last step if the new one is a superset (tool name → tool name + query).
      if (last && trimmed.startsWith(last) && trimmed.length > last.length) {
        currentSteps.value[currentSteps.value.length - 1] = trimmed;
      } else {
        currentSteps.value.push(trimmed);
      }
      scrollToBottom();
    },
    onContent: (chunk) => {
      streamingContent.value += chunk;
      scrollToBottom();
    },
    onDone: () => {
      const finalText = cleanedStreamingContent.value.trim();
      if (finalText) {
        messages.value.push({
          role: "assistant",
          content: finalText,
          steps: currentSteps.value.slice(),
        });
      }
      streamingContent.value = "";
      currentSteps.value = [];
      currentTurnPriorAssistantAnswers.value = [];
      isStreaming.value = false;
      streamController = null;
      scrollToBottom();
    },
    onError: (err) => {
      messages.value.push({
        role: "assistant",
        content: `Sorry — something went wrong: ${err?.message || err}`,
        steps: currentSteps.value.slice(),
        excludeFromHistory: true,
      });
      streamingContent.value = "";
      currentSteps.value = [];
      currentTurnPriorAssistantAnswers.value = [];
      isStreaming.value = false;
      streamController = null;
      scrollToBottom();
    },
  });
}

function stripLeadingRepeatedAnswers(text, previousAnswers) {
  let result = text;
  const candidates = previousAnswers
    .filter(Boolean)
    .map((answer) => String(answer).trim())
    .filter((answer) => answer.length >= 24)
    .sort((a, b) => b.length - a.length);

  for (const answer of candidates) {
    const end = leadingWhitespaceInsensitiveMatchEnd(result, answer);
    if (end === null) continue;
    result = result.slice(end).replace(/^\s*(?:[-–—]+\s*)?/, "");
  }

  return result;
}

function leadingWhitespaceInsensitiveMatchEnd(text, prefix) {
  let ti = 0;
  let pi = 0;

  while (ti < text.length && /\s/.test(text[ti])) ti += 1;
  while (pi < prefix.length && /\s/.test(prefix[pi])) pi += 1;

  while (pi < prefix.length) {
    const pc = prefix[pi];
    const tc = text[ti];

    if (/\s/.test(pc)) {
      while (pi < prefix.length && /\s/.test(prefix[pi])) pi += 1;
      if (pi >= prefix.length) break;
      if (ti >= text.length || !/\s/.test(text[ti])) return null;
      while (ti < text.length && /\s/.test(text[ti])) ti += 1;
      continue;
    }

    if (tc !== pc) return null;
    pi += 1;
    ti += 1;
  }

  while (ti < text.length && /\s/.test(text[ti])) ti += 1;
  return ti;
}
</script>

<style scoped>
.chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 900;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--color-accent);
  color: #fff;
  border: none;
  cursor: pointer;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-dropdown);
  transition: transform var(--transition-standard), box-shadow var(--transition-standard);
}

.chat-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
}

.chat-fab-pulse {
  animation: chat-fab-pulse-ring 1.8s ease-out infinite;
}
@keyframes chat-fab-pulse-ring {
  0%   { box-shadow: 0 0 0 0 rgba(118, 185, 0, 0.55), var(--shadow-dropdown); }
  70%  { box-shadow: 0 0 0 18px rgba(118, 185, 0, 0),    var(--shadow-dropdown); }
  100% { box-shadow: 0 0 0 0 rgba(118, 185, 0, 0),       var(--shadow-dropdown); }
}

.chat-fab-coach {
  position: fixed;
  bottom: 36px;
  right: 96px;
  z-index: 901;
  background: var(--surface-dark);
  color: var(--text-on-dark);
  padding: 8px 28px 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  box-shadow: var(--shadow-dropdown);
  animation: chat-coach-slide 0.3s ease-out;
}
.chat-fab-coach::after {
  content: "";
  position: absolute;
  right: -6px;
  top: 50%;
  transform: translateY(-50%);
  border: 6px solid transparent;
  border-left-color: var(--surface-dark);
}
.chat-fab-coach-close {
  position: absolute;
  top: 2px;
  right: 4px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  opacity: 0.7;
  padding: 0 4px;
}
.chat-fab-coach-close:hover { opacity: 1; }
@keyframes chat-coach-slide {
  from { opacity: 0; transform: translateX(8px); }
  to   { opacity: 1; transform: translateX(0); }
}
@media (max-width: 600px) {
  .chat-fab-coach { display: none; }
}

.chat-panel {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 900;
  width: 380px;
  height: 540px;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-md);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
  overflow: hidden;
  background: var(--surface-white);
  font-family: var(--font-family);
  border: 1px solid var(--border-subtle);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 15px;
  background: var(--surface-dark);
  color: var(--text-on-dark);
  flex-shrink: 0;
}

.chat-title {
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-title i {
  color: var(--color-accent);
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chat-icon-btn,
.chat-close {
  background: none;
  border: none;
  color: var(--text-on-dark);
  cursor: pointer;
  opacity: 0.7;
  transition: opacity var(--transition-standard);
}

.chat-icon-btn {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.chat-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.28;
}

.chat-icon-btn:not(:disabled):hover {
  background: rgba(255, 255, 255, 0.08);
  opacity: 1;
}

.chat-close {
  font-size: 22px;
  padding: 0 4px;
  line-height: 1;
}

.chat-close:hover { opacity: 1; }

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--surface-light);
}

.chat-welcome {
  text-align: center;
  color: var(--text-secondary);
  padding: 30px 15px;
  font-size: 13px;
  line-height: 1.6;
}

.chat-welcome p { margin: 0 0 6px; }

.chat-msg {
  max-width: 85%;
  animation: fadeIn 0.15s ease-out;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-msg-user { align-self: flex-end; }
.chat-msg-assistant { align-self: flex-start; }

/* While streaming, the wrapper can be wider so the steps list reads well. */
.chat-msg-streaming { max-width: 95%; width: 95%; }

.chat-msg-content {
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  /* Prevent ballooning if upstream tokens are pathological. */
  min-height: 28px;
  max-height: 460px;
  overflow-y: auto;
}

.chat-msg-markdown :deep(> :first-child) { margin-top: 0; }
.chat-msg-markdown :deep(> :last-child) { margin-bottom: 0; }

.chat-msg-markdown :deep(p) {
  margin: 0 0 0.65em;
}

.chat-msg-markdown :deep(h1),
.chat-msg-markdown :deep(h2),
.chat-msg-markdown :deep(h3),
.chat-msg-markdown :deep(h4),
.chat-msg-markdown :deep(h5),
.chat-msg-markdown :deep(h6) {
  line-height: 1.25;
  margin: 0.8em 0 0.35em;
}

.chat-msg-markdown :deep(h1) { font-size: 1.3em; }
.chat-msg-markdown :deep(h2) { font-size: 1.2em; }
.chat-msg-markdown :deep(h3) { font-size: 1.1em; }
.chat-msg-markdown :deep(h4),
.chat-msg-markdown :deep(h5),
.chat-msg-markdown :deep(h6) { font-size: 1em; }

.chat-msg-markdown :deep(ul),
.chat-msg-markdown :deep(ol) {
  margin: 0.35em 0 0.7em;
  padding-left: 1.5em;
}

.chat-msg-markdown :deep(li + li) { margin-top: 0.2em; }
.chat-msg-markdown :deep(li > p) { margin: 0; }

.chat-msg-markdown :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  color: var(--text-secondary);
  margin: 0.6em 0;
  padding-left: 0.75em;
}

.chat-msg-markdown :deep(code) {
  background: var(--surface-light);
  border-radius: 3px;
  font-family: var(--font-mono, monospace);
  font-size: 0.92em;
  padding: 0.1em 0.3em;
}

.chat-msg-markdown :deep(pre) {
  background: var(--surface-dark);
  border-radius: var(--radius-sm);
  color: var(--text-on-dark);
  margin: 0.6em 0;
  overflow-x: auto;
  padding: 9px 10px;
  white-space: pre;
}

.chat-msg-markdown :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  white-space: inherit;
}

.chat-msg-markdown :deep(a) {
  color: var(--color-info);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.chat-msg-markdown :deep(table) {
  border-collapse: collapse;
  font-size: 0.92em;
  margin: 0.6em 0;
  min-width: 100%;
}

.chat-msg-markdown :deep(th),
.chat-msg-markdown :deep(td) {
  border: 1px solid var(--border-subtle);
  padding: 4px 6px;
  text-align: left;
}

.chat-msg-markdown :deep(th) {
  background: var(--surface-light);
  font-weight: 600;
}

.chat-msg-markdown :deep(hr) {
  border: 0;
  border-top: 1px solid var(--border-subtle);
  margin: 0.75em 0;
}

.chat-msg-markdown :deep(input[type="checkbox"]) {
  margin: 0 0.35em 0 0;
}

.chat-msg-user .chat-msg-content {
  background: var(--surface-success-soft);
  border: 1px solid rgba(118, 185, 0, 0.35);
  color: var(--text-on-light);
}

.chat-msg-assistant .chat-msg-content {
  background: var(--surface-white);
  border: 1px solid var(--border-subtle);
  color: var(--text-on-light);
}

.chat-msg-markdown :deep(.chat-cursor) {
  animation: blink 0.85s step-end infinite;
  color: var(--color-accent);
  font-weight: 700;
  margin-left: 1px;
}

/* Streaming step list (current turn) */
.chat-streaming-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-info-soft);
  border: 1px solid rgba(0, 116, 223, 0.25);
  border-radius: var(--radius-md);
  padding: 8px 10px;
}

.chat-streaming-step {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 1px 0;
}

.chat-streaming-step.done {
  color: var(--text-secondary);
}

.chat-streaming-step.done i {
  color: var(--color-success);
  font-size: 10px;
}

.chat-streaming-step.active {
  color: var(--text-on-light);
  font-weight: 500;
}

.chat-streaming-step-solo {
  background: var(--surface-info-soft);
  border: 1px solid rgba(0, 116, 223, 0.25);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  font-size: 12px;
}

/* Three-dot loading animation appended to the active step */
.chat-streaming-dots {
  display: inline-flex;
  gap: 2px;
  margin-left: 4px;
}
.chat-streaming-dots span {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: chat-dot 1.2s ease-in-out infinite;
}
.chat-streaming-dots span:nth-child(2) { animation-delay: 0.15s; }
.chat-streaming-dots span:nth-child(3) { animation-delay: 0.3s; }

@keyframes chat-dot {
  0%, 60%, 100% { opacity: 0.2; transform: translateY(0); }
  30%           { opacity: 1;   transform: translateY(-2px); }
}

/* Completed-message step trail (collapsible) */
.chat-steps-toggle {
  align-self: flex-start;
  appearance: none;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  cursor: pointer;
  padding: 2px 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.chat-steps-toggle:hover { color: var(--text-secondary); }

.chat-steps-list {
  list-style: none;
  padding: 6px 10px;
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--surface-light);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-steps-list li {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-steps-list li i {
  color: var(--color-success);
  font-size: 9px;
}

.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--border-subtle);
  background: var(--surface-white);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  font-size: 13px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  min-width: 0;
}

.chat-send {
  flex-shrink: 0;
  padding: 8px 12px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes blink {
  50% { opacity: 0; }
}

@media (max-width: 440px) {
  .chat-panel {
    width: calc(100vw - 16px);
    right: 8px;
    bottom: 8px;
    height: 70vh;
  }

  .chat-fab {
    right: 16px;
    bottom: 16px;
  }
}
</style>
