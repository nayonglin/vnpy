"""Driver must not manufacture requests or retry an existing attempt."""
import tempfile
from pathlib import Path
import unittest

try:
    import stage044_qualified_wait_driver as module
except ImportError:
    module = None


class QualifiedWaitDriverTests(unittest.TestCase):
    def test_no_real_wait_request_is_rejected(self):
        self.assertIsNotNone(module, "bounded wait driver is missing")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                module.current_request(Path(temp))

    def test_an_existing_partial_or_failed_attempt_is_never_retried(self):
        self.assertIsNotNone(module, "bounded wait driver is missing")
        with tempfile.TemporaryDirectory() as temp:
            packet = Path(temp)
            self.assertEqual(module.provider_action(packet), "prepare")
            (packet / "network_attempt1").mkdir()
            with self.assertRaises(ValueError):
                module.provider_action(packet)
            (packet / "network_attempt1" / "parent_receipt.json").write_text('{"exit_code": 1}')
            with self.assertRaises(ValueError):
                module.provider_action(packet)


if __name__ == "__main__":
    unittest.main()
