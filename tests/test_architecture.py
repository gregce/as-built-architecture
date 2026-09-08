"""Behavior tests against real temporary Git repositories (standard library only)."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "architecture.py"
spec = importlib.util.spec_from_file_location("architecture", SCRIPT)
architecture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(architecture)


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Architecture Test")
        self.write("app.py", "print('source')\n")
        self.git("add", "app.py")
        self.git("commit", "--quiet", "-m", "Initial source")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def cli(self, command, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), command, "--repo", str(self.repo), *args],
                                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        value = json.loads(result.stdout)
        self.assertEqual(result.returncode, expected, (value, result.stderr.decode()))
        self.assertEqual(result.stderr, b"")
        return value

    def baseline(self, *args):
        value = self.cli("inspect", *args)
        path = self.base / "baseline.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def manage(self, *artifacts):
        artifacts = artifacts or ("AS-BUILT-ARCHITECTURE.html",)
        selections = [argument for path in artifacts for argument in ("--artifact", path)]
        baseline = self.baseline(*selections)
        for path in artifacts:
            if not (self.repo / path).exists():
                self.write(path, "Architecture evidence\n")
        return self.cli("record", "--baseline", str(baseline), *selections)

    def test_inspect_is_deterministic_and_never_prints_contents(self):
        self.write(".env", "SUPER_SECRET_TOKEN=do-not-print-this-value\n")
        first = self.cli("inspect")
        second = self.cli("inspect")
        self.assertEqual(first, second)
        self.assertNotIn("do-not-print-this-value", json.dumps(first))
        self.assertEqual(first["managed"], {"status": "unmanaged"})
        self.assertFalse(first["consistency"]["atomic"])

    def test_mtime_only_change_is_not_drift(self):
        self.manage()
        source = self.repo / "app.py"
        info = source.stat()
        os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
        self.assertEqual(self.cli("check")["status"], "current")

    def test_executable_source_mode_is_part_of_fingerprint(self):
        source = self.write("app.sh", "#!/bin/sh\nprintf hello\n")
        source.chmod(0o644)
        self.manage()
        before = self.cli("inspect")
        source.chmod(0o755)
        result = self.cli("check", expected=1)
        self.assertEqual(result["source_drift"], {"added": [], "changed": ["app.sh"], "deleted": []})
        old_fact = next(item for item in before["source"]["files"] if item["path"] == "app.sh")
        new_fact = next(item for item in result["source"]["files"] if item["path"] == "app.sh")
        self.assertFalse(old_fact["executable"])
        self.assertTrue(new_fact["executable"])
        self.assertEqual(old_fact["sha256"], new_fact["sha256"])
        self.assertEqual(self.cli("plan")["actions"][0]["action"], "update")

    def test_inspect_never_refreshes_git_index(self):
        index = self.repo / ".git" / "index"
        before_bytes, before_mtime = index.read_bytes(), index.stat().st_mtime_ns
        source = self.repo / "app.py"
        info = source.stat()
        os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
        self.cli("inspect")
        self.assertEqual(index.read_bytes(), before_bytes)
        self.assertEqual(index.stat().st_mtime_ns, before_mtime)

    def test_inspect_does_not_execute_repository_fsmonitor_hook(self):
        marker = self.repo / "fsmonitor-invoked"
        hook = self.write(".git/fsmonitor-test", '#!/bin/sh\n: > "$PWD/fsmonitor-invoked"\nprintf "\\000"\n')
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        self.cli("inspect")
        self.assertFalse(marker.exists())

    def test_added_changed_deleted_source_paths_are_exact(self):
        self.write("deleted.py", "old\n")
        self.manage()
        (self.repo / "deleted.py").unlink()
        self.write("app.py", "changed\n")
        self.write("added.py", "new\n")
        result = self.cli("check", expected=1)
        self.assertEqual(result["source_drift"], {
            "added": ["added.py"], "changed": ["app.py"], "deleted": ["deleted.py"],
        })

    def test_existing_both_formats_reconciles_without_duplicate_files(self):
        self.write("docs/as-built-architecture.md", "Manual MD\n")
        self.write("docs/AS-BUILD-ARCHITECTURE.HTML", "Manual HTML\n")
        result = self.cli("plan", "--format", "both")
        self.assertEqual({item["path"] for item in result["actions"]}, {
            "docs/as-built-architecture.md", "docs/AS-BUILD-ARCHITECTURE.HTML",
        })
        self.assertEqual({item["action"] for item in result["actions"]}, {"reconcile"})
        self.assertFalse((self.repo / "AS-BUILT-ARCHITECTURE.html").exists())

    def test_missing_companion_uses_existing_directory_and_stem(self):
        self.write("docs/as-built-architecture.md", "Manual MD\n")
        result = self.cli("plan", "--format", "html")
        self.assertEqual(result["actions"][0]["path"], "docs/as-built-architecture.html")
        self.assertEqual(result["actions"][0]["action"], "create")
        self.assertEqual(result["references"][0]["path"], "docs/as-built-architecture.md")
        self.assertTrue(result["references"][0]["read_only"])

    def test_html_only_update_preserves_md_as_reference(self):
        md = self.write("AS-BUILT-ARCHITECTURE.md", "Hand written reference\n")
        self.manage()
        self.write("app.py", "changed\n")
        result = self.cli("plan", "--format", "html")
        self.assertEqual(result["actions"][0]["action"], "update")
        self.assertEqual([item["path"] for item in result["references"]], [md.name])
        self.assertEqual(md.read_text(), "Hand written reference\n")
        self.assertEqual(self.cli("check", expected=1)["artifact_drift"], {
            "added": [], "changed": [], "deleted": [],
        })

    def test_multiple_candidates_require_explicit_selection(self):
        self.write("AS-BUILT-ARCHITECTURE.html", "Root\n")
        self.write("docs/AS-BUILT-ARCHITECTURE.html", "Nested\n")
        self.assertIn("Ambiguous html", self.cli("plan", expected=2)["error"])
        selected = self.cli("plan", "--artifact", "docs/AS-BUILT-ARCHITECTURE.html")
        self.assertEqual(selected["actions"][0]["path"], "docs/AS-BUILT-ARCHITECTURE.html")
        self.assertEqual(len(selected["references"]), 1)

    def test_custom_path_supported_and_classification_remains_stable(self):
        custom = "docs/platform-map.html"
        self.write("docs/background.md", "Read only architecture companion\n")
        baseline = self.baseline("--artifact", custom, "--artifact", "docs/background.md")
        self.write(custom, "New map\n")
        self.cli("record", "--baseline", str(baseline), "--artifact", custom)
        current = self.cli("check")
        self.assertEqual(current["status"], "current")
        self.assertEqual(current["unmanaged_artifacts"][0]["path"], "docs/background.md")
        self.assertEqual(self.cli("plan")["actions"][0]["action"], "noop")

    def test_artifact_content_edits_are_detected_and_require_reconciliation(self):
        self.manage()
        self.write("AS-BUILT-ARCHITECTURE.html", "Human edit\n")
        result = self.cli("check", expected=1)
        self.assertEqual(result["artifact_drift"]["changed"], ["AS-BUILT-ARCHITECTURE.html"])
        self.assertEqual(result["source_drift"], {"added": [], "changed": [], "deleted": []})
        self.assertEqual(self.cli("plan")["actions"][0]["action"], "reconcile")

    def test_reference_edit_is_observed_without_taking_ownership(self):
        md = self.write("AS-BUILT-ARCHITECTURE.md", "Human reference before\n")
        self.manage()
        html = self.repo / "AS-BUILT-ARCHITECTURE.html"
        html_before = html.read_bytes()
        md.write_text("Human reference after\n")
        result = self.cli("check", expected=1)
        empty = {"added": [], "changed": [], "deleted": []}
        self.assertEqual(result["source_drift"], empty)
        self.assertEqual(result["artifact_drift"], empty)
        self.assertEqual(result["reference_drift"], {"added": [], "changed": [md.name], "deleted": []})
        self.assertEqual([item["path"] for item in result["unmanaged_artifacts"]], [md.name])
        planned = self.cli("plan", "--format", "html")
        self.assertEqual(planned["actions"][0]["action"], "reconcile")
        self.assertEqual(planned["actions"][0]["reasons"], ["reference_evidence_changed"])
        self.assertEqual(planned["reference_drift"], result["reference_drift"])
        self.assertTrue(planned["references"][0]["read_only"])
        self.assertEqual(md.read_text(), "Human reference after\n")
        self.assertEqual(html.read_bytes(), html_before)
        state = json.loads((self.repo / architecture.STATE_NAME).read_text())
        self.assertEqual([item["path"] for item in state["artifacts"]], [html.name])
        self.assertEqual([item["path"] for item in state["references"]], [md.name])

    def test_reference_addition_and_deletion_are_exact(self):
        old = self.write("docs/AS-BUILT-ARCHITECTURE.md", "Old reference\n")
        self.manage()
        old.unlink()
        self.write("manual/AS-BUILT-ARCHITECTURE.md", "New reference\n")
        result = self.cli("check", expected=1)
        self.assertEqual(result["reference_drift"], {
            "added": ["manual/AS-BUILT-ARCHITECTURE.md"], "changed": [],
            "deleted": ["docs/AS-BUILT-ARCHITECTURE.md"],
        })
        self.assertEqual(self.cli("plan")["actions"][0]["action"], "reconcile")

    def test_missing_managed_artifact_detected(self):
        self.manage()
        (self.repo / "AS-BUILT-ARCHITECTURE.html").unlink()
        result = self.cli("check", expected=1)
        self.assertEqual(result["artifact_drift"]["deleted"], ["AS-BUILT-ARCHITECTURE.html"])

    def test_missing_custom_managed_artifact_reuses_recorded_path(self):
        custom = "docs/platform-map.html"
        self.manage(custom)
        (self.repo / custom).unlink()
        result = self.cli("plan")
        self.assertEqual(result["actions"][0]["path"], custom)
        self.assertEqual(result["actions"][0]["action"], "create")

    def test_external_artifact_and_symlink_refused(self):
        outside = self.base / "outside.html"
        outside.write_text("outside\n")
        self.cli("inspect", "--artifact", str(outside), expected=2)
        self.cli("inspect", "--artifact", "../outside.html", expected=2)
        (self.repo / "link.html").symlink_to(outside)
        self.cli("inspect", "--artifact", "link.html", expected=2)
        (self.repo / "linked-directory").symlink_to(self.base, target_is_directory=True)
        self.cli("inspect", "--artifact", "linked-directory/outside.html", expected=2)

    def test_source_symlink_hashes_link_text_without_reading_target(self):
        outside = self.base / "outside.txt"
        outside.write_text("A secret outside the repo\n")
        (self.repo / "source-link").symlink_to(outside)
        before = self.cli("inspect")
        link = next(item for item in before["source"]["files"] if item["path"] == "source-link")
        self.assertEqual(link["kind"], "symlink")
        outside.write_text("Changed secret outside the repo\n")
        self.assertEqual(before["source"], self.cli("inspect")["source"])

    def test_record_refuses_changed_source_baseline_without_writing_state(self):
        baseline = self.baseline()
        self.write("AS-BUILT-ARCHITECTURE.html", "Map\n")
        self.write("app.py", "Source changed during generation\n")
        result = self.cli("record", "--baseline", str(baseline),
                          "--artifact", "AS-BUILT-ARCHITECTURE.html", expected=2)
        self.assertIn("differs from baseline", result["error"])
        self.assertFalse((self.repo / architecture.STATE_NAME).exists())

    def test_malformed_or_unknown_state_is_never_overwritten(self):
        baseline = self.baseline()
        self.write("AS-BUILT-ARCHITECTURE.html", "Map\n")
        for content in ("not json", '{"schema_version":99}',
                        '{"schema_version":1,"generator":"as-built-architecture","source":{}}'):
            state = self.write(architecture.STATE_NAME, content)
            self.cli("record", "--baseline", str(baseline), "--artifact",
                     "AS-BUILT-ARCHITECTURE.html", expected=2)
            self.assertEqual(state.read_text(), content)

    def test_nul_in_saved_artifact_path_is_a_json_error(self):
        self.manage()
        state_file = self.repo / architecture.STATE_NAME
        state = json.loads(state_file.read_text())
        state["artifacts"][0]["path"] = "bad\x00.html"
        state_file.write_text(json.dumps(state))
        result = self.cli("inspect", expected=2)
        self.assertEqual(result["status"], "error")
        self.assertIn("Invalid relative path", result["error"])

    def test_record_is_idempotent_without_touching_mtime(self):
        self.manage()
        baseline = self.baseline()
        state = self.repo / architecture.STATE_NAME
        before_bytes, before_mtime = state.read_bytes(), state.stat().st_mtime_ns
        result = self.cli("record", "--baseline", str(baseline),
                          "--artifact", "AS-BUILT-ARCHITECTURE.html")
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(state.read_bytes(), before_bytes)
        self.assertEqual(state.stat().st_mtime_ns, before_mtime)

    def test_head_only_change_and_docs_only_commit_do_not_stale_source(self):
        self.manage()
        old_head = self.cli("inspect")["head"]
        self.git("add", "AS-BUILT-ARCHITECTURE.html", architecture.STATE_NAME)
        self.git("commit", "--quiet", "-m", "Record architecture")
        result = self.cli("check")
        self.assertNotEqual(result["head"], old_head)
        self.assertEqual(result["status"], "current")
        self.git("commit", "--allow-empty", "--quiet", "-m", "HEAD only")
        self.assertEqual(self.cli("check")["status"], "current")

    def test_scope_excludes_generated_paths_retains_lockfiles_and_claude(self):
        for path in (".specstory/history/session.md", "node_modules/dependency/a.js",
                     ".tmp/run.json", "dist/bundle.js", "build/binary", "vendor/lib.py"):
            self.write(path, "noise\n")
        for path in ("package-lock.json", ".claude/workflows/review.md", "docs/architecture-notes.md"):
            self.write(path, "relevant\n")
        self.write(".gitignore", "ignored.txt\n")
        self.write("ignored.txt", "ignored\n")
        result = self.cli("inspect")
        paths = {item["path"] for item in result["source"]["files"]}
        self.assertEqual(paths, {"app.py", "package-lock.json", ".claude/workflows/review.md",
                                 "docs/architecture-notes.md", ".gitignore"})
        self.assertTrue(result["scope"]["excluded_paths"])

    def test_unmanaged_check_is_explicit_and_nonzero(self):
        result = self.cli("check", expected=1)
        self.assertEqual(result["status"], "unmanaged")
        self.assertIsNone(result["source_drift"])

    def test_tracked_build_target_vendor_source_is_not_excluded(self):
        expected = {"build/compile.py", "target/main.c", "vendor/local-patch.go"}
        for path in expected:
            self.write(path, "Tracked source\n")
        self.write(".specstory/history/session.md", "Tracked session, still excluded\n")
        self.git("add", ".")
        result = self.cli("inspect")
        paths = {item["path"] for item in result["source"]["files"]}
        self.assertTrue(expected.issubset(paths))
        self.assertNotIn(".specstory/history/session.md", paths)

    def test_submodule_is_reported_as_uninspected(self):
        commit = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.git("update-index", "--add", "--cacheinfo", "160000," + commit + ",dependency")
        result = self.cli("inspect")
        self.assertEqual(result["scope"]["uninspected_submodules"], ["dependency"])
        self.assertIn({"path": "dependency", "reason": "git_submodule_not_inspected"}, result["scope"]["excluded_paths"])
        self.assertNotIn("dependency", [item["path"] for item in result["source"]["files"]])

    def test_summary_is_stable_bounded_and_not_recordable(self):
        self.manage()
        for index in range(20):
            self.write(".tmp/entry-%02d.txt" % index, "Ignored\n")
        value = self.cli("inspect", "--summary")
        self.assertEqual(value, self.cli("inspect", "--summary"))
        self.assertNotIn("files", value["source"])
        self.assertNotIn("record", value["managed"])
        self.assertEqual(len(value["scope"]["excluded_path_examples"]), 10)
        self.assertTrue(value["scope"]["excluded_examples_truncated"])
        self.assertEqual(self.cli("plan", "--summary")["actions"][0]["action"], "noop")
        self.assertEqual(self.cli("check", "--summary")["status"], "current")
        baseline = self.base / "summary.json"
        baseline.write_text(json.dumps(value))
        result = self.cli("record", "--baseline", str(baseline), "--artifact", "AS-BUILT-ARCHITECTURE.html", expected=2)
        self.assertIn("Summary output cannot be a baseline", result["error"])

    def test_snapshot_rejects_head_drift(self):
        with mock.patch.object(architecture, "head", side_effect=["before", "after"]):
            with self.assertRaisesRegex(architecture.ArchitectureError, "HEAD or Git file inventory"):
                architecture.snapshot(self.repo)

    def test_snapshot_rejects_inventory_drift(self):
        with mock.patch.object(architecture, "inventory", side_effect=[["app.py"], ["app.py", "new.py"]]):
            with self.assertRaisesRegex(architecture.ArchitectureError, "HEAD or Git file inventory"):
                architecture.snapshot(self.repo)

    def test_snapshot_rejects_file_changed_while_reading(self):
        real_open = architecture.os.open
        def mutate_before_open(path, flags):
            self.write("app.py", "Source raced with inventory\n")
            return real_open(path, flags)
        with mock.patch.object(architecture.os, "open", side_effect=mutate_before_open):
            with self.assertRaisesRegex(architecture.ArchitectureError, "Unstable file while opening"):
                architecture.fact(self.repo, "app.py")


if __name__ == "__main__":
    unittest.main()
