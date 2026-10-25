"""Rejects command injection through manual GitHub Actions inputs."""
import unittest
from tools.recon_cli import parse_source_ids


class ReconInputsTest(unittest.TestCase):
    def test_all_sources(self):
        self.assertEqual(parse_source_ids(None), [])
        self.assertEqual(parse_source_ids(""), [])

    def test_valid_source_ids(self):
        self.assertEqual(parse_source_ids("falabella,apple_cl,bci"), ["--only", "falabella,apple_cl,bci"])
        self.assertEqual(parse_source_ids(" apple_cl "), ["--only", "apple_cl"])

    def test_rejects_shell_metacharacters_and_multiline(self):
        for value in ("foo;echo injected", "$(whoami)", "`id`", "foo\nbar", "foo|cat", "foo && id", "foo > /tmp/file", "--write-sources"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_source_ids(value)

    def test_rejects_duplicates_and_excessively_long_filters(self):
        for value in ("bci,bci", "a" * 501, "foo,,bar", ",foo"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_source_ids(value)


if __name__ == "__main__":
    unittest.main()
