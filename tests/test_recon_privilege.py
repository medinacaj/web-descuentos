"""Invariantes de seguridad del workflow de reconocimiento (solo stdlib)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/recon.yml"


class ReconPrivilegeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = WF.read_text(encoding="utf-8")
        cls.header, jobs = raw.split("jobs:\n", 1)
        cls.recon, cls.publisher = jobs.split("  publish:\n", 1)

    def test_read_only_is_default_and_applied_to_scraper(self):
        self.assertIn("permissions:\n  contents: read", self.header)
        self.assertIn("    permissions:\n      contents: read", self.recon)
        self.assertIn("persist-credentials: false", self.recon)
        self.assertNotIn("contents: write", self.recon)
        self.assertNotIn("git push", self.recon)
        self.assertNotIn("git commit", self.recon)

    def test_only_publisher_can_write(self):
        self.assertIn("needs: recon", self.publisher)
        self.assertIn("permissions:\n      contents: write", self.publisher)
        self.assertIn("persist-credentials: true", self.publisher)
        self.assertIn("git push origin", self.publisher)
        self.assertIn("git add -- reports/ config/sources.yaml", self.publisher)
        self.assertIn("main|master", self.publisher)

    def test_manual_source_filter_remains_data_only(self):
        self.assertIn("RECON_ONLY: ${{ inputs.only || '' }}", self.recon)
        self.assertIn("run: python -m tools.recon_cli", self.recon)
        self.assertNotIn("run: python -m tools.recon --write-sources ${{", self.recon)

    def test_artifact_transfer_is_short_lived(self):
        self.assertIn("uses: actions/upload-artifact@v4", self.recon)
        self.assertIn("retention-days: 1", self.recon)
        self.assertIn("uses: actions/download-artifact@v4", self.publisher)


if __name__ == "__main__":
    unittest.main()
