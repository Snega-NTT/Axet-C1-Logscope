"""
tests.test_gen_log
~~~~~~~~~~~~~~~~~~
Unit tests for scripts/gen_log (the synthetic log generator).

Run with:
    python -m pytest tests/test_gen_log.py -v
or:
    python -m unittest tests.test_gen_log -v
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

# Make scripts/ importable
_SCRIPTS = pathlib.Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _import_gen_log():
    """Import gen_log as a module from scripts/gen_log.py."""
    import importlib.util
    # gen_log.py is the importable copy; gen_log (no extension) is the
    # executable entry point kept for Unix chmod +x usage.
    spec = importlib.util.spec_from_file_location(
        "gen_log", _SCRIPTS / "gen_log.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestParseSizeGen(unittest.TestCase):
    """parse_size correctly interprets size strings."""

    def setUp(self):
        self.gen = _import_gen_log()

    def test_mb(self) -> None:
        self.assertEqual(self.gen.parse_size("1MB"), 1_048_576)

    def test_100mb(self) -> None:
        self.assertEqual(self.gen.parse_size("100MB"), 104_857_600)

    def test_kb(self) -> None:
        self.assertEqual(self.gen.parse_size("10KB"), 10_240)

    def test_gb(self) -> None:
        self.assertEqual(self.gen.parse_size("1GB"), 1_073_741_824)

    def test_invalid_unit(self) -> None:
        with self.assertRaises(ValueError):
            self.gen.parse_size("100XB")

    def test_empty_string(self) -> None:
        with self.assertRaises(ValueError):
            self.gen.parse_size("")


class TestGenerate(unittest.TestCase):
    """generate() produces files with correct properties."""

    def setUp(self):
        self.gen = _import_gen_log()

    def _generate(self, size_bytes: int, malformed_pct: float = 1.0, seed: int = 42):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "test.log"
            actual, valid, malformed = self.gen.generate(out, size_bytes, malformed_pct, seed)
            disk_size = out.stat().st_size
            lines = out.read_text(encoding="utf-8", errors="replace").splitlines()
        return actual, valid, malformed, lines, disk_size

    def test_output_at_least_requested_size(self) -> None:
        target = 50_000
        actual, _, _, _, disk_size = self._generate(target)
        self.assertGreaterEqual(actual, target)

    def test_reported_size_matches_disk_size(self) -> None:
        """written_bytes returned by generate() must equal the on-disk file size."""
        target = 50_000
        actual, _, _, _, disk_size = self._generate(target)
        self.assertEqual(actual, disk_size,
                         "generator reported size does not match on-disk size")

    def test_overshoot_bounded_to_one_line(self) -> None:
        """On-disk overshoot must be less than one maximum-length line (~100 bytes)."""
        target = 50_000
        actual, _, _, _, disk_size = self._generate(target)
        # A single generated line is at most ~80 chars + newline; allow 200-byte margin
        self.assertLess(disk_size - target, 200,
                        f"on-disk overshoot {disk_size - target} bytes exceeds one line")

    def test_valid_entries_present(self) -> None:
        _, valid, _, _, _ = self._generate(10_000)
        self.assertGreater(valid, 0)

    def test_malformed_lines_present_with_nonzero_percent(self) -> None:
        # With 10% malformed and enough lines, expect some malformed
        _, _, malformed, _, _ = self._generate(50_000, malformed_pct=10.0)
        self.assertGreater(malformed, 0)

    def test_zero_malformed_with_zero_percent(self) -> None:
        _, _, malformed, _, _ = self._generate(20_000, malformed_pct=0.0)
        self.assertEqual(malformed, 0)

    def test_valid_count_plus_malformed_equals_total_lines(self) -> None:
        _, valid, malformed, lines, _ = self._generate(30_000)
        self.assertEqual(valid + malformed, len(lines))

    def test_seed_reproducibility(self) -> None:
        """Same seed must produce identical files."""
        with tempfile.TemporaryDirectory() as d:
            p1 = pathlib.Path(d) / "a.log"
            p2 = pathlib.Path(d) / "b.log"
            self.gen.generate(p1, 20_000, 1.0, 99)
            self.gen.generate(p2, 20_000, 1.0, 99)
            self.assertEqual(p1.read_text(), p2.read_text())

    def test_different_seeds_produce_different_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p1 = pathlib.Path(d) / "a.log"
            p2 = pathlib.Path(d) / "b.log"
            self.gen.generate(p1, 20_000, 1.0, 1)
            self.gen.generate(p2, 20_000, 1.0, 2)
            self.assertNotEqual(p1.read_text(), p2.read_text())

    def test_generated_valid_lines_parseable(self) -> None:
        """All non-malformed lines must parse successfully."""
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        from logscope.parser import parse_line

        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "test.log"
            actual, valid, malformed = self.gen.generate(out, 30_000, 1.0, 7)
            parsed_ok = 0
            parsed_bad = 0
            with out.open("r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    if parse_line(raw) is not None:
                        parsed_ok += 1
                    else:
                        parsed_bad += 1
        # parsed_ok must match declared valid count
        self.assertEqual(parsed_ok, valid)
        self.assertEqual(parsed_bad, malformed)

    def test_parent_dirs_created(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "nested" / "deep" / "test.log"
            self.gen.generate(out, 5_000, 1.0, 42)
            self.assertTrue(out.exists())

    def test_levels_all_present_in_large_enough_file(self) -> None:
        """INFO, WARN, and ERROR must all appear in a 50 KB file."""
        _, _, _, lines, _ = self._generate(50_000, malformed_pct=0.0)
        content = "\n".join(lines)
        for level in ("INFO", "WARN", "ERROR"):
            self.assertIn(f" {level} ", content)


if __name__ == "__main__":
    unittest.main()
