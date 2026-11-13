"""Command line: `python3 -m cwc verify` and `python3 -m cwc rebuild`.

Both commands build every output in memory from the committed snapshot. `verify`
compares the result with the files on disk and changes nothing. `rebuild` writes
the files and says which of them changed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import charts, data, pipeline, report, site

OUTPUTS_NOTE = "out/findings.json, THESIS.md, README.md (results block), docs/index.html, docs/charts/*.svg"


def build(root: pathlib.Path) -> tuple:
    """Return (findings, {relative path: file content as bytes})."""
    findings = pipeline.rounded(pipeline.build_findings(root))
    files = {
        "out/findings.json": json.dumps(findings, indent=1, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        "THESIS.md": report.render_thesis(findings, (root / "thesis" / "THESIS.template.md").read_text(encoding="utf-8")),
        "README.md": report.render_readme(findings, (root / "README.md").read_text(encoding="utf-8")),
        "docs/index.html": site.render(findings),
    }
    for chart in charts.all_charts(findings):
        files[f"docs/charts/{chart['id']}.svg"] = chart["svg"] + "\n"
    return findings, {path: text.encode("utf-8") for path, text in files.items()}


def headline(findings: dict) -> str:
    v = report.facts(findings)
    lines = [
        f"Verdict: {v['verdict_label']}",
        v["verdict_sentence"],
        f"  take per $100 swapped   {v['take_before']} -> {v['take_after']} cents ({v['take_ratio']}x)",
        f"  break-even loss         {v['break_even']}",
        f"  volume against peers    {v['estimate']}  ({v['interval_level']} interval {v['interval_lo']} to {v['interval_hi']})",
        f"  loss not ruled out      {v['loss_bound']}",
        f"  share of peer basket    {v['share_before']} -> {v['share_after']} -> {v['share_latest']} (before, after, latest)",
        f"  data through            {v['data_through']}",
    ]
    if not findings["verdict"]["prose_matches"]:
        lines.append("WARNING: the outcome of the tests differs from the one the thesis text was written for (config 'written_for').")
    return "\n".join(lines)


def cmd_rebuild(root: pathlib.Path) -> int:
    findings, files = build(root)
    for path, content in files.items():
        target = root / path
        same = target.exists() and target.read_bytes() == content
        if not same:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        print(f"{'unchanged' if same else 'written  '}  {path}")
    print()
    print(headline(findings))
    return 0


def cmd_verify(root: pathlib.Path) -> int:
    findings, files = build(root)
    different = 0
    for path, content in files.items():
        target = root / path
        same = target.exists() and target.read_bytes() == content
        different += 0 if same else 1
        print(f"{'identical' if same else 'DIFFERENT'}  {path}")
    print()
    if different:
        print(f"{different} of {len(files)} committed files differ from a fresh rebuild. Run `python3 -m cwc rebuild` and look at `git diff`.")
        return 1
    print(f"All {len(files)} committed files are byte-identical to a fresh rebuild from the snapshot.")
    print()
    print(headline(findings))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m cwc", description="Rebuild or verify every output from the committed snapshot. Offline.")
    parser.add_argument("command", choices=["verify", "rebuild"], help=f"verify: compare a fresh rebuild with the files on disk. rebuild: write {OUTPUTS_NOTE}.")
    args = parser.parse_args(argv)
    root = data.project_root()
    try:
        return cmd_verify(root) if args.command == "verify" else cmd_rebuild(root)
    except data.SnapshotError as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
