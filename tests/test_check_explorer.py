"""Behavioral fixtures for the read-only explorer checker; no third parties."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_explorer.py"
SPEC = importlib.util.spec_from_file_location("check_explorer", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class ExplorerChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.html = self.root / "explorer.html"

    def write(self, name, content="source"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_check(self, html, **options):
        self.html.write_text(html, encoding="utf-8")
        return CHECKER.Checker(self.html, **options).run()

    def codes(self, report):
        return {item["code"] for item in report["findings"]}

    def cli(self, *arguments):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, arguments)], text=True, capture_output=True, check=False)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout), result.stdout

    def test_encoded_targets_queries_and_html_fragments(self):
        self.write("docs/a b.md")
        self.write("other.html", '<h1 id="some heading">Other</h1><a name="legacy"></a>')
        result = self.run_check('<h1 id="here">Here</h1><a href="#here">a</a><a href="docs/a%20b.md?view=source">b</a><a href="other.html?x=1#some%20heading">c</a><a href="other.html#legacy">d</a>')
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["checks"]["local_targets_checked"], 3)
        self.assertEqual(result["checks"]["html_fragments_checked"], 3)

    def test_missing_targets_fragments_and_non_html_fragments(self):
        self.write("README.md", "# Guide")
        result = self.run_check('<a href="missing.md?x=1#what">a</a><a href="#missing">b</a><a href="README.md#guide">c</a>')
        self.assertEqual(self.codes(result), {"missing-local-target", "missing-fragment"})
        self.assertIn("non-html-fragment-unchecked", {item["code"] for item in result["notes"]})

    def test_site_root_and_file_urls(self):
        self.write("source.py")
        html = self.write("docs/page.html", '<a href="/source.py">root</a><a href="'+(self.root / "source.py").as_uri()+'">file</a>')
        result = CHECKER.Checker(html, site_root=self.root).run()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["checks"]["local_targets_checked"], 1)

    def test_javascript_hrefs_entities_controls_and_external_citations(self):
        result = self.run_check('<a href="java&#x09;script:alert(1)">bad</a><a href="https://example.invalid/no-network">citation</a><a href="mailto:owner@example.invalid">email</a>')
        self.assertEqual(self.codes(result), {"javascript-link"})
        self.assertEqual(result["checks"]["external_links_not_fetched"], 2)

    def test_structured_routes_not_misrepresented_as_validated(self):
        result = self.run_check('<a href="#map/component">route</a><a href="#map">flat</a>')
        self.assertEqual(self.codes(result), {"missing-fragment"})
        self.assertEqual(result["checks"]["application_hashes_unvalidated"], 1)
        self.assertEqual(result["checks"]["html_fragments_checked"], 1)

    def test_declared_flat_route_only_applies_to_that_current_document_route(self):
        self.write("other.html", "<p>Other</p>")
        result = self.run_check('<a href="#evidence">route</a><a href="#broken">broken</a><a href="other.html#evidence">other</a>', route_fragments=["evidence"])
        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual({item["ref"] for item in result["findings"]}, {"#broken", "other.html#evidence"})
        self.assertIn("declared-application-route", {item["code"] for item in result["notes"]})

    def test_duplicate_ids_and_tab_relationships(self):
        good = '<button id="label" role="tab" aria-controls="panel">Tab</button><section id="panel" role="tabpanel" aria-labelledby="label">Panel</section>'
        self.assertEqual(self.run_check(good)["status"], "ok")
        result = self.run_check(good + '<div id="panel"></div><button role="tab" aria-controls="label missing">Bad</button><button role="tab">Missing</button><section role="tabpanel" aria-labelledby="lost"></section><section role="tabpanel"></section>')
        self.assertEqual(self.codes(result), {"duplicate-id", "invalid-tab-panel", "tab-missing-controls", "missing-panel-label", "panel-missing-label"})

    def test_explicit_json_sources_recursively_and_object_paths(self):
        self.write("src/a.py")
        self.write("src/b c.py")
        payload = {"nodes": [{"sources": ["src/a.py", {"path": "src/b%20c.py", "line": 4}]}], "prose": "missing.txt", "nested": {"sources": ["missing.py"]}}
        result = self.run_check('<script type="application/json" id="architecture-data">'+json.dumps(payload)+'</script>')
        self.assertEqual(result["checks"]["structured_source_links"], 3)
        self.assertEqual(self.codes(result), {"missing-local-target"})
        self.assertEqual(result["findings"][0]["ref"], "missing.py")

    def test_malformed_json_and_invalid_sources_are_findings(self):
        result = self.run_check('<script id="architecture-data" type="application/json">{"sources": [}</script>')
        self.assertEqual(self.codes(result), {"invalid-architecture-json"})
        result = self.run_check('<script id="architecture-data" type="application/json">{"sources": [3, {}, "", {"path": null}]}</script>')
        self.assertEqual(len(result["findings"]), 4)
        result = self.run_check('<script id="architecture-data" type="application/json">{"sources":"a.py"}</script>')
        self.assertEqual(self.codes(result), {"invalid-sources"})

    def test_js_strings_and_prose_are_not_scanned(self):
        html = '''<script>const data={sources:['imaginary.py']}; const fake='<a id="fake" href="missing.txt"><img src="https://bad.invalid/x">';</script><p>missing/prose/file.py</p><style>.x::after {content: 'url(https://bad.invalid/fake) <img src="remote.png">';} /* url(https://bad.invalid/comment) */</style>'''
        result = self.run_check(html)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["checks"]["static_links"], 0)
        self.assertEqual(result["checks"]["static_ids"], 0)
        self.assertEqual(result["checks"]["asset_references"], 0)
        self.assertEqual(result["checks"]["inline_scripts_not_executed"], 1)
        self.assertFalse(result["checks"]["rendered_links_supplied"])

    def test_non_json_constants_and_duplicate_keys_do_not_hide_sources(self):
        for content in ['{"value": NaN}', '{"sources": ["missing.py"], "sources": []}']:
            with self.subTest(content=content):
                result = self.run_check('<script id="architecture-data" type="application/json">'+content+'</script>')
                self.assertEqual(self.codes(result), {"invalid-architecture-json"})

    def test_asset_packaging_css_and_data_urls(self):
        self.write("local.css")
        html = '''<script src="https://example.invalid/a.js"></script><link rel="stylesheet" href="local.css"><link rel="icon" href="data:image/png;base64,AAAA"><img src="data:image/png;base64,AAAA"><svg><use href="#symbol"></use></svg><style>@import "https://example.invalid/a.css"; .a{background:url(//example.invalid/x.png)} .b{background:url('data:image/png;base64,AAAA')} .c{filter:url(#filter)}</style>'''
        result = self.run_check(html)
        self.assertEqual(self.codes(result), {"non-inline-asset"})
        self.assertEqual(len(result["findings"]), 4)
        self.assertEqual(result["checks"]["asset_references"], 9)
        self.assertEqual(self.run_check(html, allow_assets=True)["status"], "ok")

    def test_escaped_css_names_imports_and_inline_style(self):
        result = self.run_check(r'''<style>@\69mport "https://example.invalid/a.css"; .a{background:u\72l(https://example.invalid/a.png)}</style><div style="background: url(https://example.invalid/b.png)"></div>''')
        self.assertEqual(len(result["findings"]), 3)
        self.assertEqual(result["checks"]["asset_references"], 3)

    def test_allow_assets_still_checks_local_existence(self):
        result = self.run_check('<img src="missing.png"><iframe src="missing.html"></iframe><object data="missing.svg"></object>', allow_assets=True)
        self.assertEqual(self.codes(result), {"missing-local-asset"})
        self.assertEqual(len(result["findings"]), 3)

    def test_srcset_with_data_commas_and_video_poster(self):
        html = '<img srcset="data:image/png;base64,AAAA 1x, https://example.invalid/b.png 2x"><video poster="https://example.invalid/poster.png"><source src="https://example.invalid/v.webm"></video><link rel="preload" imagesrcset="data:image/png;base64,BBBB 1x, https://example.invalid/c.png 2x">'
        result = self.run_check(html)
        self.assertEqual(len(result["findings"]), 4)
        self.assertEqual(result["checks"]["asset_references"], 6)

    def test_base_href_explicitly_unsupported(self):
        result = self.run_check('<base href="https://example.invalid/"><a href="https://example.invalid/a">a</a>')
        self.assertEqual(self.codes(result), {"unsupported-base"})

    def test_rendered_export_checks_dynamic_targets_without_executing(self):
        self.write("found.py")
        result = self.run_check('<script>throw Error("never execute");</script>', rendered_links=["found.py", "missing.py", "#map/item"])
        self.assertEqual(self.codes(result), {"missing-local-target"})
        self.assertEqual(result["checks"]["rendered_links"], 3)
        self.assertTrue(result["checks"]["rendered_links_supplied"])
        self.assertIn("browser-export-scope", {item["code"] for item in result["notes"]})

    def test_cli_exit_codes_and_valid_json_errors(self):
        self.write("explorer.html", "<p>Good</p>")
        self.assertEqual(self.cli(self.html)[0], 0)
        self.write("explorer.html", '<a href="missing">missing</a>')
        self.assertEqual(self.cli(self.html)[0], 1)
        self.assertEqual(self.cli(self.root / "absent.html")[0], 2)
        self.assertEqual(self.cli()[0], 2)
        self.assertEqual(self.cli(self.html, "--site-root", self.root / "missing")[0], 2)
        self.assertEqual(self.cli(self.html, "--route-fragment", "#invalid")[0], 2)
        exported = self.write("links.json", "[3]")
        self.assertEqual(self.cli(self.html, "--rendered-links", exported)[0], 2)
        self.write("links.json", "not JSON")
        self.assertEqual(self.cli(self.html, "--rendered-links", exported)[0], 2)
        self.write("links.json", '["missing.py"]')
        self.assertEqual(self.cli(self.html, "--rendered-links", exported)[1]["checks"]["rendered_links"], 1)

    def test_readonly_no_added_files_no_mtime_changes_and_deterministic_output(self):
        self.write("source.py")
        self.write("explorer.html", '<a href="source.py">source</a><a href="missing.py">missing</a>')
        before = {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        os.chmod(self.html, 0o444)
        first = self.cli(self.html)
        second = self.cli(self.html)
        self.assertEqual(first[2], second[2])
        after = {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
