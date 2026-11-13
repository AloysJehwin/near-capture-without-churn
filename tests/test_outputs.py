import json
import re
import socket
import unittest

from tests.helpers import ROOT, built
from cwc import __main__ as cli
from cwc import report

ALLOWED = [
    r"https?://\S+",                                   # links
    r"`[^`]*`",                                        # code
    r"\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b",   # dates of cited sources
    r"\b(early|late)( [A-Z][a-z]+)? \d{4}\b",            # "early 2026", "late February 2026"
    r"\((19|20)\d{2}\)",                               # years of cited papers
    r"^#{1,6} \d+\. ",                                 # section numbers
    r"^\d+\. ",                                        # list numbers
    r"\*\*\d+\.\d+ ",                                  # numbered paragraphs
    r"section \d+",                                    # cross-references
    r"\$100\b",                                        # the unit of the take measure
    r"\b50/50\b",                                      # the split NEAR's documentation states
    r"SHA-256",
    r"Python 3\.10",
    r"\bt0\b|\bt1\b|- 1\b",                            # the break-even formula
    r"\bRule \d\b",
]


class Template(unittest.TestCase):
    def test_template_contains_no_typed_results(self):
        text = (ROOT / "thesis" / "THESIS.template.md").read_text(encoding="utf-8")
        text = re.sub(r"\{\{[a-z0-9_]+\}\}", "", text)
        for pattern in ALLOWED:
            text = re.sub(pattern, "", text, flags=re.MULTILINE)
        left = sorted(set(re.findall(r"\S*\d\S*", text)))
        self.assertEqual(left, [], f"digits typed in the template outside placeholders: {left}")

    def test_every_placeholder_is_defined(self):
        findings, _ = built()
        text = (ROOT / "thesis" / "THESIS.template.md").read_text(encoding="utf-8")
        names = set(re.findall(r"\{\{([a-z0-9_]+)\}\}", text))
        defined = set(report.facts(findings)) | {"banner"}
        self.assertEqual(names - defined, set())
        with self.assertRaises(KeyError):
            report.fill("{{no_such_name}}", {})

    def test_readme_block_is_rewritten_between_the_markers(self):
        findings, _ = built()
        out = report.render_readme(findings, f"top\n{report.START}\nold\n{report.END}\nbottom\n")
        self.assertTrue(out.startswith("top\n") and out.endswith("\nbottom\n"))
        self.assertNotIn("old", out)
        with self.assertRaises(KeyError):
            report.render_readme(findings, "no markers here")


class Outputs(unittest.TestCase):
    def test_committed_files_equal_a_fresh_rebuild(self):
        _, files = built()
        self.assertEqual(len(files), 12)
        for path, content in files.items():
            self.assertTrue((ROOT / path).exists(), f"{path} is missing; run python3 -m cwc rebuild")
            self.assertEqual((ROOT / path).read_bytes(), content, f"{path} differs from a fresh rebuild")

    def test_rebuild_opens_no_network_connection_and_is_repeatable(self):
        _, first = built()
        real = socket.socket

        def blocked(*args, **kwargs):
            raise AssertionError("the rebuild tried to open a network connection")

        socket.socket = blocked
        try:
            _, second = cli.build(ROOT)
        finally:
            socket.socket = real
        self.assertEqual(first, second)

    def test_text_outputs_agree_with_findings(self):
        findings, files = built()
        thesis = files["THESIS.md"].decode("utf-8")
        readme = files["README.md"].decode("utf-8")
        page = files["docs/index.html"].decode("utf-8")
        values = report.facts(findings)
        self.assertIn(f"**Verdict: {findings['verdict']['label']}.**", thesis)
        self.assertIn(f"**Verdict: {findings['verdict']['label']}.**", readme)
        self.assertIn(findings["verdict"]["label"], page)
        for name in ("take_before", "take_after", "break_even", "estimate", "interval_lo", "interval_hi", "share_before", "share_latest"):
            self.assertIn(values[name], thesis, name)
            self.assertIn(values[name], readme, name)
        self.assertNotIn("{{", thesis)
        self.assertTrue(findings["verdict"]["prose_matches"], "the test outcomes differ from config 'written_for'; reread the thesis text")
        self.assertNotIn("Read this first", thesis)

    def test_findings_file_is_plain_finite_json(self):
        _, files = built()
        text = files["out/findings.json"].decode("ascii")
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        loaded = json.loads(text)
        self.assertEqual(loaded["meta"]["event_date"], loaded["config"]["event_date"])

    def test_charts_are_self_contained(self):
        _, files = built()
        for path, content in files.items():
            if path.endswith(".svg"):
                svg = content.decode("utf-8")
                self.assertTrue(svg.startswith("<svg") and svg.rstrip().endswith("</svg>"))
                self.assertNotIn("<script", svg)
                self.assertEqual(re.findall(r'(?:href|src)="(?!#)[^"]*"', svg), [], path)
        page = files["docs/index.html"].decode("utf-8")
        self.assertEqual(re.findall(r'<(?:link|img|script)[^>]+(?:href|src)="', page), [], "the page must not load external files")


if __name__ == "__main__":
    unittest.main()
