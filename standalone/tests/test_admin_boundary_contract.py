"""Security contract: Pool control must never be authorized by family PIN alone."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PoolAdminBoundaryContract(unittest.TestCase):
    def test_pool_command_has_backend_administrator_guard(self):
        source = (ROOT / 'server.py').read_text()
        self.assertIn('Administrator authorization required', source)
        self.assertIn('if key == "pool"', source)

if __name__ == '__main__':
    unittest.main()
