# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Unit tests for the report summarizer (``tools/validators/summarize_csv.py``).

The summarizer accepts either the driver's ``--csv-output`` CSV or its
``--json-output`` JSON and must produce the same summary from both. These tests
pin the JSON reader's tuple output, the CSV/JSON equivalence, and the promise
that a malformed report is reported as structured JSON rather than a traceback.
"""

import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


def _load_summarizer():
    """Import tools/validators/summarize_csv.py, or return None if not found.

    Walks up from this file so it works from a source checkout and from the
    extracted test package (``tools/`` is not shipped, but in CI the source
    checkout is still an ancestor of the extraction dir).
    """
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        candidate = os.path.join(d, "tools", "validators", "summarize_csv.py")
        if os.path.isfile(candidate):
            spec = importlib.util.spec_from_file_location("usd_optimize_summarize_report", candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        if os.path.dirname(d) == d:
            return None
        d = os.path.dirname(d)


_sum = _load_summarizer()

# One issue per shape the reader has to handle: a plain prim location, a
# list-valued `at` (some rules emit several), an absent `at` (stage-level), an
# issue that inherits its rule name from the parent entry, and the upper-case
# FAILED_CHECK severity alias.
_REPORT = {
    "status": "FAIL",
    "rules": [
        {
            "rule": {"name": "UsdOptimizeNonManifoldChecker"},
            "issues": [
                {
                    "rule": {"name": "UsdOptimizeNonManifoldChecker"},
                    "message": "non-manifold mesh",
                    "severity": "FAILURE",
                    "at": {"type": "PRIM", "path": "/World/Cube"},
                    "suggestion": {"message": "Run meshCleanup"},
                },
                {  # no per-issue rule -> falls back to the entry's rule name
                    "message": "another one",
                    "severity": "WARNING",
                    "at": [{"path": "/World/A"}, {"path": "/World/B"}],
                },
            ],
        },
        {
            "rule": {"name": "ExtentsChecker"},
            "issues": [
                {"message": "no extent", "severity": "FAILED_CHECK"},  # no `at` -> stage
            ],
        },
    ],
}

_EXPECTED_ROWS = [
    (
        "UsdOptimizeNonManifoldChecker",
        "failure",
        "non-manifold mesh",
        "Run meshCleanup",
        "/World/Cube",
        "Usd Optimize",
    ),
    ("UsdOptimizeNonManifoldChecker", "warning", "another one", "", "/World/A", "Usd Optimize"),
    ("ExtentsChecker", "failure", "no extent", "", "(stage)", "base"),
]


class Test(unittest.TestCase):
    def setUp(self):
        if _sum is None:
            self.skipTest("tools/validators/summarize_csv.py not found (packaged run without source tree)")
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def _write(self, name, text):
        path = os.path.join(self._tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def _run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = _sum.main(list(argv))
        return rc, json.loads(out.getvalue())

    # ---- JSON reader --------------------------------------------------------

    def test_json_rows_match_expected_tuples(self):
        path = self._write("r.json", json.dumps(_REPORT))
        self.assertEqual(list(_sum._read_rows_json(Path(path))), _EXPECTED_ROWS)

    def test_json_location_shapes(self):
        # dict, list (first wins), identifier fallback, and the empty cases.
        cases = [
            ({"path": "/World/X"}, "/World/X"),
            ([{"path": "/A"}, {"path": "/B"}], "/A"),
            ({"identifier": "layer.usda"}, "layer.usda"),
            ({}, "(stage)"),
            ([], "(stage)"),
            (None, "(stage)"),
            ("Prim </World/Wrapped>", "/World/Wrapped"),
        ]
        for at, expected in cases:
            with self.subTest(at=at):
                self.assertEqual(_sum._json_location(at), expected)

    # ---- CSV / JSON equivalence --------------------------------------------

    def test_csv_and_json_produce_the_same_summary(self):
        csv_text = (
            "Asset,Rule,Message,Severity,Suggestion,Location\n"
            "a.usd,UsdOptimizeNonManifoldChecker,non-manifold mesh,Failure,Run meshCleanup,Prim </World/Cube>\n"
            "a.usd,UsdOptimizeNonManifoldChecker,another one,Warning,None,Prim </World/A>\n"
            "a.usd,ExtentsChecker,no extent,Failure,None,\n"
        )
        _, from_csv = self._run_main(self._write("i.csv", csv_text))
        _, from_json = self._run_main(self._write("r.json", json.dumps(_REPORT)))
        self.assertEqual(from_csv, from_json)
        self.assertEqual(from_json["totals"]["by_family"], {"Usd Optimize": 2, "base": 1})

    # ---- malformed input is structured, never a traceback -------------------

    def test_malformed_shapes_raise_value_error(self):
        cases = [
            ("[1, 2, 3]", "the top level"),
            ('"a string"', "the top level"),
            ('{"rules": {"not": "a list"}}', "'rules' list"),
            ('{"rules": ["notadict"]}', "'rules' entry"),
            ('{"rules": [{"issues": {"not": "a list"}}]}', "'issues' to be a list"),
            ('{"rules": [{"issues": ["notadict"]}]}', "each issue"),
        ]
        for body, expect in cases:
            with self.subTest(body=body):
                path = self._write("bad.json", body)
                rc, out = self._run_main(path)
                self.assertEqual(rc, 1)
                self.assertIn(expect, out["error"])

    def test_odd_nested_field_types_do_not_crash(self):
        # A string where an object is expected reads as empty rather than failing.
        body = {"rules": [{"rule": "str", "issues": [{"rule": "str", "suggestion": "str", "severity": "WARNING"}]}]}
        rc, out = self._run_main(self._write("odd.json", json.dumps(body)))
        self.assertEqual(rc, 0)
        self.assertEqual(out["totals"]["rows"], 1)

    def test_missing_report(self):
        rc, out = self._run_main(os.path.join(self._tmp, "nope.json"))
        self.assertEqual(rc, 1)
        self.assertIn("report not found", out["error"])


if __name__ == "__main__":
    unittest.main()
