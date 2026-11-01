import os
import tempfile
import unittest
from unittest.mock import patch

from config import Config, DEFAULT_SECRET, parse_env_file


class TestEnvFile(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, ".env")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_parsing_formats(self):
        path = self.write(
            "# comment\n\n"
            "CLIENT_ID=crm\n"
            'CLIENT_SECRET="se cret # not a comment"\n'
            "export PORT=9000   # trailing comment\n"
            "DB_PATH='my.db'\n"
            "EMPTY=\n")
        self.assertEqual(parse_env_file(path), {
            "CLIENT_ID": "crm", "CLIENT_SECRET": "se cret # not a comment",
            "PORT": "9000", "DB_PATH": "my.db", "EMPTY": ""})

    def test_invalid_line_is_skipped_with_warning(self):
        # Malformed lines (e.g. text accidentally pasted into .env) must not
        # crash startup; they are skipped with a warning naming the line number.
        path = self.write("CLIENT_ID=crm\nthis is wrong\nPORT=9000\n")
        with patch("builtins.print") as fake_print:
            values = parse_env_file(path)
        self.assertEqual(values, {"CLIENT_ID": "crm", "PORT": "9000"})
        warned = " ".join(str(c) for c in fake_print.call_args_list)
        self.assertIn(":2:", warned)

    def test_missing_file_is_fine(self):
        self.assertEqual(parse_env_file("/no/such/.env"), {})

    def test_config_reads_env_file(self):
        path = self.write("CLIENT_ID=fromfile\nCLIENT_SECRET=abc123\nPORT=9001\nTOKEN_TTL=60\n")
        cfg = Config.from_env(environ={}, env_file=path)
        self.assertEqual((cfg.client_id, cfg.client_secret, cfg.port, cfg.token_ttl),
                         ("fromfile", "abc123", 9001, 60))
        self.assertFalse(cfg.uses_default_secret)

    def test_real_env_overrides_file(self):
        path = self.write("CLIENT_ID=fromfile\nCLIENT_SECRET=abc123\n")
        cfg = Config.from_env(environ={"CLIENT_ID": "fromenv"}, env_file=path)
        self.assertEqual((cfg.client_id, cfg.client_secret), ("fromenv", "abc123"))

    def test_static_token_setting(self):
        cfg = Config.from_env(environ={"STATIC_ACCESS_TOKEN": "abc"}, env_file="/no/such/.env")
        self.assertEqual(cfg.static_token, "abc")
        self.assertEqual(Config.from_env(environ={}, env_file="/no/such/.env").static_token, "")

    def test_defaults_when_nothing_set(self):
        cfg = Config.from_env(environ={}, env_file="/no/such/.env")
        self.assertEqual((cfg.client_secret, cfg.port), (DEFAULT_SECRET, 8000))
        self.assertTrue(cfg.uses_default_secret)

    def test_env_file_location_via_env_var(self):
        path = self.write("CLIENT_ID=viaenvfile\n")
        cfg = Config.from_env(environ={"ENV_FILE": path})
        self.assertEqual(cfg.client_id, "viaenvfile")


if __name__ == "__main__":
    unittest.main()