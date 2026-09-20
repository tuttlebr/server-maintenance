import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.job_results import get_job_results


class JobResultTests(unittest.TestCase):
    def test_loads_valid_typed_results_and_ignores_malformed_files(self):
        job_id = "12345678-1234-1234-1234-123456789abc"
        with tempfile.TemporaryDirectory() as directory:
            result_dir = Path(directory) / "job-results" / job_id
            result_dir.mkdir(parents=True)
            (result_dir / "gpu_node.json").write_text(json.dumps({
                "schema_version": 1,
                "report_type": "gpu",
                "hostname": "node-01",
                "total_gpus": 2,
            }))
            (result_dir / "bad.json").write_text("not-json")
            with patch("backend.services.job_results.settings.data_dir", Path(directory)):
                results = get_job_results(job_id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["hostname"], "node-01")

    def test_rejects_unsafe_job_ids(self):
        self.assertEqual(get_job_results("../logs"), [])


if __name__ == "__main__":
    unittest.main()
