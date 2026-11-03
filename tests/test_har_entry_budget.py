"""Synthetic, bounded subprocess acceptance tests; no network or private HARs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "har_entry_budget.py"


def archive(entries):
    return {"log": {"version": "1.2", "entries": entries}}


def entry(time=100, body=200):
    return {"time": time, "response": {"bodySize": body}}


class BudgetTests(unittest.TestCase):
    def run_raw(self, raw, expected=0, extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "synthetic.har"
            target.write_bytes(raw)
            before = hashlib.sha256(target.read_bytes()).digest()
            cp = subprocess.run(
                [sys.executable, SCRIPT.name, str(target), "--max-time-ms", "100",
                 "--max-body-bytes", "200", *(extra or [])],
                cwd=ROOT, capture_output=True, timeout=10,
            )
            self.assertEqual(cp.returncode, expected, cp.stdout + cp.stderr)
            self.assertEqual(cp.stderr, b"")
            self.assertEqual(before, hashlib.sha256(target.read_bytes()).digest())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [target.name])
            return json.loads(cp.stdout)

    def run_doc(self, doc, expected=0, extra=None):
        return self.run_raw(json.dumps(doc).encode(), expected, extra)

    def test_exact_threshold_clean(self):
        r = self.run_doc(archive([entry()]))
        self.assertEqual(r["code"], "CLEAN")
        self.assertEqual(r["findings"], [])

    def test_fractional_time_over(self):
        r = self.run_doc(archive([entry(100.25)]), 1)
        self.assertEqual(r["findings"], [{"entry": 1, "code": "TIME_OVER", "measurement": 100.25, "budget": 100}])

    def test_decimal_comparison_is_exact(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[{"time":0.100000000000000001,"response":{"bodySize":0}}]}}', 1, ["--max-time-ms", "0.1"])

    def test_mixed_unknown_and_over(self):
        r = self.run_doc(archive([entry(101, -1), {"response": {"bodySize": 201}}, {}]), 1)
        self.assertEqual(r["counts"], {"time_over": 1, "body_over": 1, "time_unknown": 2, "body_unknown": 2})
        self.assertEqual([f["entry"] for f in r["findings"]], [1, 1, 2, 2, 3, 3])

    def test_content_size_does_not_replace_body(self):
        r = self.run_doc(archive([{"time": 0, "response": {"content": {"size": 0}}}]), 1)
        self.assertEqual(r["findings"], [{"entry": 1, "code": "BODY_UNKNOWN"}])

    def test_content_metadata_not_validated_as_measurement(self):
        self.run_doc(archive([{"time": 0, "response": {"bodySize": 0, "content": {"size": "ignored"}}}]))

    def test_empty_entries_clean(self):
        self.run_doc(archive([]))

    def test_bom_accepted(self):
        self.run_raw(b"\xef\xbb\xbf" + json.dumps(archive([entry()])).encode())

    def test_large_finite_time(self):
        r = self.run_doc(archive([entry(1e308)]), 1)
        self.assertEqual(r["findings"][0]["measurement"], 1e308)

    def test_maximum_finite_boundary(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[{"time":1.7976931348623157e308,"response":{"bodySize":0}}]}}',
                     0, ["--max-time-ms", "1.7976931348623157e308"])

    def test_very_small_finite_measurement(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[{"time":1e-1000,"response":{"bodySize":0}}]}}',
                     1, ["--max-time-ms", "0"])

    def test_numeric_range_comparison_is_exact(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[]},"x":1.79769313486231570000000000001e308}', 2)

    def test_negative_time_invalid_even_minus_one(self):
        for v in [-1, -0.01]:
            with self.subTest(v=v):
                self.run_doc(archive([entry(v)]), 2)

    def test_invalid_measurement_types(self):
        for v in [None, True, "100", [], {}]:
            with self.subTest(v=v):
                self.run_doc(archive([entry(v)]), 2)
        for v in [None, True, "200", 1.5, -2, 1.0]:
            with self.subTest(body=v):
                self.run_doc(archive([entry(body=v)]), 2)

    def test_malformed_response_invalid(self):
        for v in [None, 0, [], "private"]:
            self.run_doc(archive([{"time": 0, "response": v}]), 2)

    def test_structure_invalid(self):
        for doc in [[], {}, {"log": []}, {"log": {"version": "1.3", "entries": []}},
                    {"log": {"version": 1.2, "entries": []}},
                    {"log": {"version": "1.2", "entries": {}}}, archive([None])]:
            self.run_doc(doc, 2)

    def test_nonfinite_and_overflow_rejected_everywhere(self):
        for token in [b"NaN", b"Infinity", b"-Infinity", b"1e309", b"-1e309"]:
            raw = b'{"log":{"version":"1.2","entries":[],"ignored":' + token + b'}}'
            self.run_raw(raw, 2)

    def test_duplicate_keys_rejected_everywhere(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[],"secret":{"a":1,"a":2}}}', 2)

    def test_surrogates_rejected_keys_and_values(self):
        for raw in [b'{"log":{"version":"1.2","entries":[]},"x":"\\ud800"}',
                    b'{"log":{"version":"1.2","entries":[]},"\\udfff":0}']:
            self.run_raw(raw, 2)

    def test_paired_surrogate_accepted(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[]},"x":"\\ud83d\\ude00"}')

    def test_malformed_json_utf8(self):
        for raw in [b'{', b'\xff', b'{}{}', b'{"x":01}', b'{"x":1,}']:
            self.run_raw(raw, 2)

    def test_depth_cap(self):
        raw = b'{"log":{"version":"1.2","entries":[]},"x":' + b'[' * 64 + b'0' + b']' * 64 + b'}'
        self.run_raw(raw, 2)

    def test_depth_boundary_and_brackets_in_strings(self):
        raw = b'{"log":{"version":"1.2","entries":[]},"x":' + b'[' * 63 + b'"[\\\"]"' + b']' * 63 + b'}'
        self.run_raw(raw)

    def test_entry_cap(self):
        self.run_doc(archive([entry(0, 0)] * 10000))
        self.run_doc(archive([entry(0, 0)] * 10001), 2)

    def test_node_cap(self):
        doc = archive([])
        doc["metadata"] = [None] * 100001
        self.run_doc(doc, 2)

    def test_byte_cap(self):
        self.run_raw(b' ' * (2 * 1024 * 1024 + 1), 2)

    def test_numeric_token_cap(self):
        self.run_raw(b'{"log":{"version":"1.2","entries":[]},"x":' + b'1' * 129 + b'}', 2)

    def test_output_privacy_even_malformed(self):
        secret = "SYNTHETIC_PRIVATE_MARKER"
        for raw, status in [(json.dumps({**archive([entry(101, 201)]), "url": secret, "cookies": secret}).encode(), 1),
                            (b'{"' + secret.encode() + b'":', 2)]:
            r = self.run_raw(raw, status)
            self.assertNotIn(secret, json.dumps(r))

    def test_invalid_arguments_neutral(self):
        for args in [[], ["private-path"], ["private-path", "--max-time-ms", "NaN", "--max-body-bytes", "1"],
                     ["private-path", "--max-time-ms", "-1", "--max-body-bytes", "1"],
                     ["private-path", "--max-time-ms", "1", "--max-body-bytes", "1.0"]]:
            cp = subprocess.run([sys.executable, SCRIPT.name, *args], cwd=ROOT, capture_output=True, timeout=10)
            self.assertEqual(cp.returncode, 2)
            self.assertEqual(cp.stderr, b"")
            self.assertEqual(json.loads(cp.stdout), {"code": "INVALID_ARGUMENTS"})

    def test_missing_and_directory_neutral(self):
        for target in ["tests/no-such-private-file.har", "tests"]:
            cp = subprocess.run([sys.executable, SCRIPT.name, target, "--max-time-ms", "1", "--max-body-bytes", "1"], cwd=ROOT, capture_output=True, timeout=10)
            self.assertEqual(cp.returncode, 2)
            self.assertEqual(cp.stderr, b"")
            self.assertNotIn(target.encode(), cp.stdout)

    def test_closed_stdout_real_pipe_including_help(self):
        for args in [["--help"], ["examples/clean.har", "--max-time-ms", "100", "--max-body-bytes", "200"]]:
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                cp = subprocess.run([sys.executable, SCRIPT.name, *args], cwd=ROOT, stdout=write_fd, stderr=subprocess.PIPE, timeout=10)
            finally:
                os.close(write_fd)
            self.assertEqual(cp.returncode, 2)
            self.assertEqual(cp.stderr, b"")

    def test_path_refusal_precedes_stat_and_open(self):
        spec = importlib.util.spec_from_file_location("budget_under_test", SCRIPT)
        if not SCRIPT.exists():
            self.fail("source must provide pre-access path validation")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paths = ["https://private/x", "file:///private/x", "s3:private", "//private/share", "\\\\private\\share", "/\\private/share", "\\/private/share", "\\\\?\\C:\\private", "NUL", "nested/COM1.txt", "C:/x/CON", "C:relative", "-"]
        with patch.object(module.os, "stat", side_effect=AssertionError("stat called")), patch("builtins.open", side_effect=AssertionError("open called")):
            for target in paths:
                with self.subTest(target=target):
                    with self.assertRaises(module.InvalidInput):
                        module.load_document(target)


if __name__ == "__main__":
    unittest.main()
