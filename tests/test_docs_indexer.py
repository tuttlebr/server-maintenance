import re
import tomllib
import unittest
from pathlib import Path

from backend.config import Settings


REPO_ROOT = Path(__file__).resolve().parents[1]


def _example_environment() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (REPO_ROOT / ".env.example").read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


class DocsIngesterPackagingTests(unittest.TestCase):
    def test_packaged_ingester_path_matches_runtime_configuration(self):
        manifest = tomllib.loads(
            (REPO_ROOT / "tools" / "dgx-doc-ingester" / "Cargo.toml").read_text()
        )
        binary_name = manifest["package"]["name"]
        packaged_path = Path("/usr/local/bin") / binary_name

        configured_default = Settings.model_fields["docs_ingester_bin"].default
        configured_example = Path(_example_environment()["DOCS_INGESTER_BIN"])

        self.assertEqual(configured_default, packaged_path)
        self.assertEqual(configured_example, packaged_path)

        dockerfile = (REPO_ROOT / "Dockerfile").read_text()
        copy_pattern = re.compile(
            rf"^COPY --from=docs-ingester-build "
            rf"\S*/target/release/{re.escape(binary_name)} "
            rf"{re.escape(str(packaged_path))}$",
            re.MULTILINE,
        )
        self.assertRegex(dockerfile, copy_pattern)


if __name__ == "__main__":
    unittest.main()
