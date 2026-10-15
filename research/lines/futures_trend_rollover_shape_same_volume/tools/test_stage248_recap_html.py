"""Safety gates for the frozen Stage246 display adapter."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


class RecapGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('stage248_recap_html.py')
        spec = importlib.util.spec_from_file_location('recap248', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_missing_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                self.module.require_evidence(Path(tmp))

    def test_open_positions_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Residual'):
            self.module.require_closed({'unclosed_cycle_count': 1, 'unclosed_abs_contracts': 2})

    def test_output_cannot_escape_line_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(ValueError):
                self.module.validate_output(base / '..' / 'escaped', base)
            target = base / 'stage248'
            target.mkdir()
            with self.assertRaises(FileExistsError):
                self.module.validate_output(target, base)

    def test_renderer_is_pinned_and_has_no_runtime_import(self):
        renderer = self.module.load_renderer({})
        self.assertIn('_html', renderer)
        self.assertNotIn('TqApi', renderer)
        self.assertNotIn('s901', renderer)


if __name__ == '__main__':
    unittest.main()
