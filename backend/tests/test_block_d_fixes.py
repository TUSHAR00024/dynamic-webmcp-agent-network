"""Regression tests for BLOCK D: relative links, honest claims, verify_setup assertions, and packaging."""
import os
import re
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.verify_setup import verify_all


class TestBlockDFixes(unittest.TestCase):

    def test_d1_no_file_urls_or_absolute_home_paths_in_markdown(self):
        """All repository markdown documents must use relative paths, never file:/// or local home paths."""
        md_files = list(BASE_DIR.glob("**/*.md"))
        # Exclude .venv
        md_files = [f for f in md_files if ".venv" not in f.parts]
        self.assertGreater(len(md_files), 3, "Expected at least 4 markdown documentation files")

        violations = []
        for mf in md_files:
            text = mf.read_text(encoding="utf-8")
            if "file:///" in text:
                violations.append(f"{mf.name}: contains 'file:///' link")
            if "/Users/" in text:
                violations.append(f"{mf.name}: contains absolute '/Users/' local path")

        self.assertEqual(violations, [], f"Detected local absolute paths or file URLs: {violations}")

    def test_d2_verify_setup_active_assertions_pass(self):
        """scripts/verify_setup.py must actively pass all assertions and return True."""
        result = verify_all()
        self.assertTrue(result, "verify_all() returned False or raised an assertion failure")

    def test_d3_package_script_excludes_forbidden_files(self):
        """scripts/package.sh must produce a zip package that excludes .git, .env, .venv, and caches."""
        package_script = BASE_DIR / "scripts" / "package.sh"
        self.assertTrue(package_script.is_file(), "scripts/package.sh must exist")
        self.assertTrue(os.access(package_script, os.X_OK), "scripts/package.sh must be executable")

        zip_output = BASE_DIR / "dynamic-webmcp-agent-network.zip"
        # Run package script
        env = os.environ.copy()
        env["HOME"] = "/tmp"
        res = subprocess.run(["bash", str(package_script)], cwd=str(BASE_DIR), capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, f"package.sh failed:\n{res.stdout}\n{res.stderr}")
        self.assertTrue(zip_output.is_file(), "dynamic-webmcp-agent-network.zip was not created")

        # Inspect zip contents
        with zipfile.ZipFile(zip_output, "r") as zf:
            namelist = zf.namelist()
            for name in namelist:
                self.assertFalse(name.endswith("/.env") or name == "dynamic-webmcp-agent-network/.env",
                                 f"Forbidden .env included in zip: {name}")
                self.assertFalse("/.git/" in name or name.startswith("dynamic-webmcp-agent-network/.git/"),
                                 f"Forbidden .git included in zip: {name}")
                self.assertFalse("/.venv/" in name or name.startswith("dynamic-webmcp-agent-network/.venv/"),
                                 f"Forbidden .venv included in zip: {name}")
                self.assertFalse("__pycache__" in name,
                                 f"Forbidden __pycache__ included in zip: {name}")

        # Clean up created zip
        if zip_output.exists():
            zip_output.unlink()


if __name__ == "__main__":
    unittest.main()
