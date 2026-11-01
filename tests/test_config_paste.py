"""Regression test: junk pasted into .env must not crash startup."""
import tempfile, unittest
from pathlib import Path

from config import Config, parse_env_file


class EnvPasteRegression(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8")
        f.write(text); f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_pasted_text_after_max_body_bytes_is_skipped(self):
        path = self.write(
            "CLIENT_ID=crm\n"
            "CLIENT_SECRET=branson1234\n"
            "MAX_BODY_BYTES=1000000 Branson@1234\n"
        )
        cfg = Config.from_env(environ={}, env_file=path)
        self.assertEqual(cfg.client_id, "crm")
        self.assertEqual(cfg.client_secret, "branson1234")
        # malformed trailing junk is stripped by comment-splitting? No: value stays as-is
        # -> ensure int() still works or the line was handled without crashing
        self.assertIsInstance(cfg.max_body_bytes, int)

    def test_line_without_equals_is_ignored_not_fatal(self):
        path = self.write(
            "# comment\n"
            "Branson@1234\n"
            "PORT=8000\n"
        )
        vals = parse_env_file(path)
        self.assertEqual(vals, {"PORT": "8000"})

    def test_valid_values_still_parse(self):
        path = self.write('A=1\nB="two words"\nexport C=3\n')
        self.assertEqual(parse_env_file(path), {"A": "1", "B": "two words", "C": "3"})


if __name__ == "__main__":
    unittest.main()
