"""Test runner for Phase 1 and Phase 2 Routing Engine validation."""
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir.parent))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(backend_dir / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
