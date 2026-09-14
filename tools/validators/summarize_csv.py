r"""Summarize a usd-validation-nvidia issues report into compact JSON.

Pure-stdlib helper used by the interpret-validators skill so the agent doesn't
have to load and parse a multi-thousand-row report directly into context. Runs
under any Python 3 on any OS (POSIX: ``python3 ...``; Windows: ``py -3 ...``
or the bundled ``_build\target-deps\python\python.exe``).

Accepts either driver output and produces the same summary from both:
``--csv-output`` (a CSV) or ``--json-output`` (a JSON whose per-issue rows live
under ``rules[].issues[]``). The input is chosen by file extension.

The script has two output shapes, selected by the flags:

**Default mode** (no ``--locations``) — full summary suitable for an initial
report. Output structure:

    {
      "totals": {
        "rows": <int>,                  # total issues in the (filtered) view
        "rules": <int>,                 # number of rules with at least one issue
        "by_severity": {"failure": N, "warning": N, ...},
        "by_family":   {"Usd Optimize": N, "base": N},
        "failures_by_rule": {"<RuleName>": N, ...}
      },
      "rules": [                        # one entry per rule, sorted by
        {                               #   (max severity weight desc, count desc)
          "rule": "<RuleName>",
          "family": "Usd Optimize" | "base",
          "by_severity": {...},
          "affected_prims": <int>       # distinct Location values, 0 if stage-only
        },
        ...
      ],
      "failures": [                     # all Failure-severity rows, grouped
        {                               #   by (rule, message, suggestion)
          "rule": "<RuleName>",
          "message": "<text>",
          "suggestion": "<text>" | "",
          "locations": ["<path>", ...]  # raw, with Prim/Stage wrapper stripped
        },
        ...
      ]
    }

If ``--rule <RuleName>`` is passed, every section is filtered to that rule.

**Locations mode** (``--rule <RuleName> --locations``) — flat list of every
row for one rule, useful for "Which prims are affected by X?" follow-ups.
Output structure:

    {
      "rule": "<RuleName>",
      "total": <int>,                   # total rows for this rule
      "by_severity": {...},             # severity counts for this rule
      "shown": <int>,                   # number of rows actually emitted
      "locations": [
        {"location": "<path>",
         "severity": "warning" | "failure" | "error" | "info",
         "message": "<text>",
         "suggestion": "<text>" | ""},
        ...
      ]
    }

Locations are sorted (failure > error > warning > info) then by alphabetic
location path. ``--limit N`` caps the emitted list (``total`` still reports
the full count). ``--severity <name>`` further filters to one severity level.

`Location` values are normalized: a leading ``Prim </…>`` / ``Stage </…>`` /
``Attribute (…) Prim </…>`` wrapper is stripped, and the empty/None case is
recorded as the literal string ``"(stage)"``.

Usage:
    python3 tools/validators/summarize_csv.py <report>          # issues.csv or results.json
    python3 tools/validators/summarize_csv.py <report> --max-failures-per-rule 10
    python3 tools/validators/summarize_csv.py <report> --rule <Name>
    python3 tools/validators/summarize_csv.py <report> --rule <Name> --locations --limit 20
    python3 tools/validators/summarize_csv.py <report> --rule <Name> --locations --severity failure

Windows note: replace ``python3`` with ``py -3`` (Python launcher) or the
bundled interpreter at ``_build\target-deps\python\python.exe``.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _raise_csv_field_limit():
    """Raise csv's field-size cap as high as the platform allows.

    Validator issues can carry very large fields -- e.g. a mesh checker that
    lists tens of thousands of affected prim paths in a single cell -- which
    exceeds Python's default 128 KB limit and makes csv.reader raise
    "field larger than field limit". sys.maxsize can overflow the C long the
    csv module uses (notably 32-bit long on Windows), so back off until a
    value is accepted.
    """
    limit = sys.maxsize
    while limit > 1:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 2


_raise_csv_field_limit()


_LOC_RE = re.compile(r"<([^>]*)>")


def _normalize_location(loc: str) -> str:
    """Extract the bare path from validator-style location strings.

    Handles all common shapes:
        Prim </World/Foo>                                    -> /World/Foo
        Stage </path/to/asset.usd>                           -> /path/to/asset.usd
        Attribute (info:mdl:sourceAsset) Prim </Path/X>      -> /Path/X
    Lines without a ``<...>`` group (e.g. ``Sdf.Find('a', 'b')`` for layer-spec
    issues) are returned as-is. Empty / ``None`` cells become ``"(stage)"``.
    """
    if not loc or loc == "None":
        return "(stage)"
    matches = _LOC_RE.findall(loc)
    return matches[-1] if matches else loc.strip()


_SEVERITY_WEIGHT = {"failure": 3, "error": 2, "warning": 1, "info": 0}


def _sort_key_rule(rule: dict) -> tuple[int, int]:
    sev = rule["by_severity"]
    max_w = max((_SEVERITY_WEIGHT.get(k, 0) for k in sev), default=0)
    total = sum(sev.values())
    return (-max_w, -total)


def _read_rows(csv_path: Path):
    """Yield (rule, severity, message, suggestion, location, family) per row."""
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required = {"Rule", "Severity", "Message", "Suggestion", "Location"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"CSV missing required columns. Expected {sorted(required)}, "
                f"got {reader.fieldnames or []}"
            )
        for row in reader:
            rule = row["Rule"]
            sev = row["Severity"].lower()
            msg = row["Message"]
            sug = row["Suggestion"] if row["Suggestion"] != "None" else ""
            loc = _normalize_location(row["Location"])
            family = "Usd Optimize" if rule.startswith("UsdOptimize") else "base"
            yield rule, sev, msg, sug, loc, family


_JSON_SEVERITY_ALIASES = {"failed_check": "failure", "failedcheck": "failure"}


def _json_location(at) -> str:
    """Bare path from an issue's ``at`` field (dict, list, or absent).

    ``at`` is list-valued for some rules, so unwrap before reading the path.
    """
    if isinstance(at, list):
        at = at[0] if at else None
    raw = (at.get("path") or at.get("identifier") or "") if isinstance(at, dict) else (at or "")
    return _normalize_location(raw)


def _require_dict(value, what: str) -> dict:
    """Return *value* as a dict, or raise ValueError naming what was expected.

    Every shape mismatch has to surface as ValueError so ``main`` can report it
    as structured JSON; letting ``.get`` raise AttributeError would print a
    traceback instead.
    """
    if not isinstance(value, dict):
        raise ValueError(
            f"not a usd-validation-nvidia report: expected {what} to be an object, "
            f"got {type(value).__name__}. Re-run run-validators to regenerate the report."
        )
    return value


def _sub_dict(container: dict, key: str) -> dict:
    """``container[key]`` when it is an object, else ``{}``.

    Optional nested fields (``rule``, ``suggestion``) are absent on some issues
    and vary by engine version, so a missing or oddly-typed one reads as empty
    rather than failing the whole report.
    """
    value = container.get(key)
    return value if isinstance(value, dict) else {}


def _read_rows_json(json_path: Path):
    """Yield the same tuples as :func:`_read_rows` from a ``--json-output`` file.

    Shape is ``{"status", "rules": [{"rule": {"name"}, "issues": [...]}]}`` --
    per-issue detail lives under ``rules[].issues[]``, so the JSON carries the
    same rows as the CSV under a different schema.

    Version note: this is the shape emitted by usd-validation-nvidia >= 1.21.0,
    the floor this repo pins. A report produced by an older engine may use a
    different schema; it is rejected below rather than parsed on a guess.
    """
    with json_path.open(encoding="utf-8", errors="replace") as f:
        doc = _require_dict(json.load(f), "the top level")
    rules = doc.get("rules")
    if not isinstance(rules, list):
        raise ValueError(
            "not a usd-validation-nvidia report: expected a top-level 'rules' list "
            f"(as emitted by --json-output on engine >= 1.21.0), got keys {sorted(doc)}. "
            "Re-run run-validators to regenerate the report."
        )
    for entry in rules:
        entry = _require_dict(entry, "each 'rules' entry")
        fallback = _sub_dict(entry, "rule").get("name", "")
        issues = entry.get("issues") or []
        if not isinstance(issues, list):
            raise ValueError(
                "not a usd-validation-nvidia report: expected 'issues' to be a list, "
                f"got {type(issues).__name__}"
            )
        for issue in issues:
            issue = _require_dict(issue, "each issue")
            rule = _sub_dict(issue, "rule").get("name") or fallback
            sev = str(issue.get("severity", "")).lower()
            sev = _JSON_SEVERITY_ALIASES.get(sev, sev)
            sug = _sub_dict(issue, "suggestion").get("message", "") or ""
            loc = _json_location(issue.get("at"))
            family = "Usd Optimize" if rule.startswith("UsdOptimize") else "base"
            yield rule, sev, issue.get("message", ""), sug, loc, family


def _summary_mode(rows, args) -> dict:
    by_rule: dict[str, dict] = defaultdict(
        lambda: {"sev": Counter(), "locs": set(), "family": None}
    )
    failure_groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    failure_totals: Counter = Counter()
    by_severity_total: Counter = Counter()
    by_family_total: Counter = Counter()
    rows_count = 0

    for rule, sev, msg, sug, loc, family in rows:
        if args.rule and rule != args.rule:
            continue
        rows_count += 1
        by_rule[rule]["sev"][sev] += 1
        by_rule[rule]["family"] = family
        if loc != "(stage)":
            by_rule[rule]["locs"].add(loc)
        by_severity_total[sev] += 1
        by_family_total[family] += 1
        if sev == "failure":
            failure_groups[(rule, msg, sug)].append(loc)
            failure_totals[rule] += 1

    rules_out = []
    for rule, d in by_rule.items():
        rules_out.append(
            {
                "rule": rule,
                "family": d["family"],
                "by_severity": dict(d["sev"]),
                "affected_prims": len(d["locs"]),
            }
        )
    rules_out.sort(key=_sort_key_rule)

    failures_out = []
    seen_per_rule: Counter = Counter()
    for (rule, msg, sug), locs in sorted(
        failure_groups.items(), key=lambda kv: -len(kv[1])
    ):
        if args.max_failures_per_rule and seen_per_rule[rule] >= args.max_failures_per_rule:
            continue
        out_locs = list(locs)
        if args.max_failures_per_rule:
            remaining_budget = args.max_failures_per_rule - seen_per_rule[rule]
            if len(out_locs) > remaining_budget:
                out_locs = out_locs[:remaining_budget]
        seen_per_rule[rule] += len(out_locs)
        failures_out.append(
            {
                "rule": rule,
                "message": msg,
                "suggestion": sug,
                "locations": out_locs,
            }
        )

    return {
        "totals": {
            "rows": rows_count,
            "rules": len(by_rule),
            "by_severity": dict(by_severity_total),
            "by_family": dict(by_family_total),
            "failures_by_rule": dict(failure_totals),
        },
        "rules": rules_out,
        "failures": failures_out,
    }


def _locations_mode(rows, args) -> dict:
    if not args.rule:
        raise ValueError("--locations requires --rule <RuleName>")

    sev_filter = args.severity.lower() if args.severity else None
    matched: list[dict] = []
    by_severity: Counter = Counter()
    total = 0

    for rule, sev, msg, sug, loc, _family in rows:
        if rule != args.rule:
            continue
        total += 1
        by_severity[sev] += 1
        if sev_filter and sev != sev_filter:
            continue
        matched.append(
            {"location": loc, "severity": sev, "message": msg, "suggestion": sug}
        )

    matched.sort(
        key=lambda r: (-_SEVERITY_WEIGHT.get(r["severity"], 0), r["location"])
    )
    shown = matched if not args.limit else matched[: args.limit]

    return {
        "rule": args.rule,
        "total": total,
        "by_severity": dict(by_severity),
        "filter": {"severity": sev_filter} if sev_filter else {},
        "shown": len(shown),
        "locations": shown,
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Summarize a usd-validation-nvidia issues report (CSV or JSON).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("report_path", help="--csv-output CSV or --json-output JSON.")
    p.add_argument(
        "--max-failures-per-rule",
        type=int,
        default=0,
        help="If >0, cap the failure rows emitted per rule in summary mode.",
    )
    p.add_argument(
        "--rule",
        default=None,
        help="Filter the output to one rule. Required for --locations.",
    )
    p.add_argument(
        "--locations",
        action="store_true",
        help="Emit a flat per-row list for --rule (use for 'which prims affected by X' follow-ups).",
    )
    p.add_argument(
        "--severity",
        choices=("failure", "error", "warning", "info"),
        default=None,
        help="With --locations, filter by severity.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="With --locations, cap the emitted location list (total still reported).",
    )
    args = p.parse_args(argv)

    report = Path(args.report_path)
    if not report.is_file():
        print(json.dumps({"error": f"report not found: {args.report_path}"}))
        return 1

    read = _read_rows_json if report.suffix.lower() == ".json" else _read_rows
    try:
        rows = list(read(report))
    except (ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}))
        return 1

    try:
        if args.locations:
            out = _locations_mode(rows, args)
        else:
            out = _summary_mode(rows, args)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return 2

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
