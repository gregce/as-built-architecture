#!/usr/bin/env python3
"""Content evidence and document planning for an as-built architecture skill.

This program inventories Git worktrees. It never generates or edits architecture
documents, and its hashes cannot establish that a document is architecturally true.
Python 3 standard library only.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

SCHEMA_VERSION = 1
STATE_NAME = ".as-built-architecture.json"
GENERATOR = "as-built-architecture"
EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".specstory", ".runstory", ".tmp", ".cache", ".venv", "venv",
    "__pycache__", "node_modules", "dist", "build", ".build", "target",
    ".next", ".nuxt", ".output", ".turbo", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "coverage", ".coverage", "htmlcov", ".tox", ".nox",
    "vendor", "bower_components", "tmp", "temp",
})
ALWAYS_EXCLUDED_DIRECTORIES = frozenset({".git", ".specstory", ".runstory", ".tmp"})
ARTIFACT_NAME = re.compile(r"^as-buil[dt]-architecture\.(md|html)$", re.IGNORECASE)
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ArchitectureError(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def source_fingerprint(files):
    return digest(canonical(files).encode("utf-8"))


def git(root, *args, allow_failure=False):
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=str(root), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False, env=environment)
    if result.returncode and not allow_failure:
        raise ArchitectureError("Git inventory failed (no command output included).")
    return result


def repository(path):
    location = Path(path).expanduser().resolve()
    if not location.is_dir():
        raise ArchitectureError("--repo must name an existing Git worktree directory.")
    result = git(location, "rev-parse", "--show-toplevel")
    return Path(os.fsdecode(result.stdout.rstrip(b"\n"))).resolve()


def head(root):
    result = git(root, "rev-parse", "--verify", "HEAD", allow_failure=True)
    return result.stdout.decode("ascii").strip() if result.returncode == 0 else None


def inventory(root):
    result = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return sorted({os.fsdecode(item) for item in result.stdout.split(b"\0") if item})


def index_inventory(root):
    result = git(root, "ls-files", "--stage", "-z")
    tracked, submodules = set(), set()
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        path = os.fsdecode(path_bytes)
        tracked.add(path)
        if metadata.startswith(b"160000 "):
            submodules.add(path)
    return tracked, submodules


def relative_path(root, raw):
    """Validate lexically before examining symlinks; do not resolve their targets."""
    if not isinstance(raw, str) or "\x00" in raw:
        raise ArchitectureError("Artifact paths must be strings without NUL characters.")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(root)
        except ValueError:
            raise ArchitectureError("Artifact paths must stay inside the repository.")
    parts = candidate.parts
    if not parts or any(part in {"..", ".git"} for part in parts):
        raise ArchitectureError("Artifact paths must stay inside the repository, outside .git.")
    path = PurePosixPath(*parts).as_posix()
    if path in {".", STATE_NAME}:
        raise ArchitectureError("Artifact path must name a Markdown or HTML document.")
    if PurePosixPath(path).suffix.lower() not in {".md", ".html"}:
        raise ArchitectureError("Artifact path must end in .md or .html.")
    assert_no_symlinks(root, path)
    if (root / path).exists() and not (root / path).is_file():
        raise ArchitectureError("Artifact path is not a regular file: " + path)
    return path


def assert_no_symlinks(root, relative, include_leaf=True):
    parts = PurePosixPath(relative).parts
    current = root
    for part in parts if include_leaf else parts[:-1]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(info.st_mode):
            raise ArchitectureError("Refusing a symlink in path: " + relative)


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode)


def fact(root, relative, artifact=False):
    assert_no_symlinks(root, relative, include_leaf=artifact)
    path = root / relative
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(before.st_mode):
        if artifact:
            raise ArchitectureError("Refusing an artifact symlink: " + relative)
        data = os.fsencode(os.readlink(path))
        if signature(before) != signature(path.lstat()):
            raise ArchitectureError("Unstable file while reading; retry: " + relative)
        return {"path": relative, "kind": "symlink", "sha256": digest(data), "bytes": len(data)}
    if not stat.S_ISREG(before.st_mode):
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or signature(before) != signature(opened):
                raise ArchitectureError("Unstable file while opening; retry: " + relative)
            hasher = hashlib.sha256()
            total = 0
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                total += len(chunk)
            after_read = os.fstat(stream.fileno())
        after_path = path.lstat()
    except OSError:
        raise ArchitectureError("Unable to safely read file; retry: " + relative)
    if signature(before) != signature(after_read) or signature(before) != signature(after_path):
        raise ArchitectureError("Unstable file while reading; retry: " + relative)
    output = {"path": relative, "kind": "file", "sha256": hasher.hexdigest(), "bytes": total}
    if artifact:
        output["format"] = PurePosixPath(relative).suffix.lower()[1:]
    else:
        output["executable"] = bool(before.st_mode & 0o111)
    return output


def validate_source(source):
    if (not isinstance(source, dict) or set(source) != {"files", "fingerprint"} or
            not isinstance(source.get("files"), list)):
        raise ArchitectureError("Invalid source snapshot.")
    files = source["files"]
    seen = set()
    for entry in files:
        validate_fact(entry)
        if entry["path"] in seen:
            raise ArchitectureError("Duplicate source path in snapshot.")
        seen.add(entry["path"])
    if files != sorted(files, key=lambda entry: entry["path"]):
        raise ArchitectureError("Source snapshot paths must be sorted.")
    if source.get("fingerprint") != source_fingerprint(files):
        raise ArchitectureError("Source snapshot fingerprint is invalid.")


def validate_fact(entry, artifact=False):
    if not isinstance(entry, dict):
        raise ArchitectureError("Invalid file facts in saved data.")
    path = entry.get("path")
    if (not isinstance(path, str) or not path or "\x00" in path or path.startswith("/") or
            ".." in PurePosixPath(path).parts):
        raise ArchitectureError("Invalid relative path in saved data.")
    if path != PurePosixPath(path).as_posix() or ".git" in PurePosixPath(path).parts:
        raise ArchitectureError("Invalid relative path in saved data.")
    if entry.get("kind") not in ({"file"} if artifact else {"file", "symlink"}):
        raise ArchitectureError("Invalid file kind in saved data.")
    if not isinstance(entry.get("sha256"), str) or not HEX_DIGEST.fullmatch(entry["sha256"]):
        raise ArchitectureError("Invalid content digest in saved data.")
    if type(entry.get("bytes")) is not int or entry["bytes"] < 0:
        raise ArchitectureError("Invalid byte count in saved data.")
    expected_fields = {"path", "kind", "sha256", "bytes"}
    if artifact:
        expected_fields.add("format")
    elif entry["kind"] == "file":
        expected_fields.add("executable")
        if type(entry.get("executable")) is not bool:
            raise ArchitectureError("Invalid executable flag in source facts.")
    if set(entry) != expected_fields:
        raise ArchitectureError("Unknown or missing fields in saved file facts.")
    if artifact and (entry.get("format") not in {"md", "html"} or
                     PurePosixPath(path).suffix.lower() != "." + entry["format"]):
        raise ArchitectureError("Invalid artifact format in saved data.")


def read_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise ArchitectureError("Cannot read valid JSON " + label + ".")


def read_state(root):
    path = root / STATE_NAME
    assert_no_symlinks(root, STATE_NAME)
    if not path.exists():
        return None
    value = read_json(path, "managed state")
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int or
            value["schema_version"] != SCHEMA_VERSION or value.get("generator") != GENERATOR):
        raise ArchitectureError("Malformed or unknown managed state schema; refusing to overwrite it.")
    if set(value) != {"schema_version", "generator", "source", "artifacts", "references"}:
        raise ArchitectureError("Unknown or missing managed state fields; refusing to overwrite it.")
    validate_source(value.get("source"))
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ArchitectureError("Malformed managed state artifacts; refusing to overwrite it.")
    paths = []
    for entry in artifacts:
        validate_fact(entry, artifact=True)
        relative_path(root, entry["path"])
        paths.append(entry["path"])
    if paths != sorted(set(paths)):
        raise ArchitectureError("Malformed managed state artifact ordering.")
    references = value.get("references")
    if not isinstance(references, list):
        raise ArchitectureError("Malformed observed reference facts.")
    reference_paths = []
    for entry in references:
        validate_fact(entry, artifact=True)
        if relative_path(root, entry["path"]) != entry["path"]:
            raise ArchitectureError("Malformed observed reference path.")
        reference_paths.append(entry["path"])
    if reference_paths != sorted(set(reference_paths)) or set(reference_paths) & set(paths):
        raise ArchitectureError("Malformed managed state reference ordering.")
    return value


def exclusion(path, tracked=False):
    parts = PurePosixPath(path).parts
    for part in parts[:-1]:
        if part.lower() in ALWAYS_EXCLUDED_DIRECTORIES or (not tracked and part.lower() in EXCLUDED_DIRECTORIES):
            return "excluded_directory:" + part
    if path == STATE_NAME:
        return "managed_state"
    return None


def snapshot(root, explicit=(), extra_artifacts=()):
    first_head = head(root)
    first_list = inventory(root)
    tracked, submodules = index_inventory(root)
    state = read_state(root)
    artifact_paths = set(explicit) | set(extra_artifacts)
    if state:
        artifact_paths.update(item["path"] for item in state["artifacts"])
        artifact_paths.update(item["path"] for item in state["references"])
    for path in first_list:
        if not exclusion(path, path in tracked) and ARTIFACT_NAME.fullmatch(PurePosixPath(path).name):
            artifact_paths.add(path)
    for path in artifact_paths:
        relative_path(root, path)
    artifacts = []
    for path in sorted(artifact_paths):
        item = fact(root, path, artifact=True)
        if item:
            artifacts.append(item)
    files, excluded = [], []
    for path in first_list:
        reason = "architecture_artifact" if path in artifact_paths else exclusion(path, path in tracked)
        if path in submodules:
            reason = "git_submodule_not_inspected"
        if reason:
            excluded.append({"path": path, "reason": reason})
            continue
        item = fact(root, path)
        if item:
            files.append(item)
        else:
            excluded.append({"path": path, "reason": "missing_or_non_regular"})
    dirty = bool(git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout)
    if first_head != head(root) or first_list != inventory(root) or (tracked, submodules) != index_inventory(root):
        raise ArchitectureError("HEAD or Git file inventory changed during inspection; retry.")
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": str(root), "head": first_head, "dirty": dirty,
        "source": {"fingerprint": source_fingerprint(files), "files": files},
        "artifacts": artifacts,
        "managed": {"status": "managed", "record": state} if state else {"status": "unmanaged"},
        "scope": {
            "inventory": "git ls-files --cached --others --exclude-standard",
            "excluded_directory_names": sorted(EXCLUDED_DIRECTORIES),
            "always_excluded_directory_names": sorted(ALWAYS_EXCLUDED_DIRECTORIES),
            "tracked_generated_directories": "Tracked files are retained unless under an always-excluded directory.",
            "excluded_paths": excluded,
            "uninspected_submodules": sorted(submodules),
            "ignored_untracked_files": "Excluded by Git ignore rules; explicit artifacts are still read.",
            "symlinks": "Source link text is hashed; targets are never followed. Artifact symlinks are refused.",
            "source_metadata": "Regular source files include an executable boolean; timestamps and other permissions are not fingerprint inputs.",
            "limitations": ["Exclusions are heuristic; review them for repository-specific source directories.",
                            "Submodule contents and ignored untracked files are not inventoried.",
                            "Content facts do not establish architecture semantics or document correctness."],
        },
        "consistency": {"stable": True, "atomic": False,
                        "checks": ["per-file identity and metadata before/after reading", "HEAD before/after", "Git file list before/after", "tracked paths and submodule paths before/after"],
                        "limitation": "A file can change after its read; this is not an atomic filesystem snapshot."},
    }


def differences(before, after):
    old = {item["path"]: item for item in before}
    new = {item["path"]: item for item in after}
    return {"added": sorted(new.keys() - old.keys()),
            "changed": sorted(path for path in old.keys() & new.keys() if old[path] != new[path]),
            "deleted": sorted(old.keys() - new.keys())}


def has_drift(value):
    return any(value.values())


def reference_differences(state, artifacts):
    managed_paths = {item["path"] for item in state["artifacts"]}
    return differences(state["references"], [item for item in artifacts if item["path"] not in managed_paths])


def plan(snapshot_value, requested_format, explicit):
    requested = ["html", "md"] if requested_format == "both" else [requested_format]
    artifacts = snapshot_value["artifacts"]
    existing = {item["path"]: item for item in artifacts}
    state = snapshot_value["managed"].get("record")
    old = {item["path"]: item for item in state["artifacts"]} if state else {}
    source_changed = bool(state and state["source"]["fingerprint"] != snapshot_value["source"]["fingerprint"])
    reference_drift = reference_differences(state, artifacts) if state else None
    references_changed = bool(reference_drift and has_drift(reference_drift))
    actions = []
    for fmt in requested:
        selected = sorted(path for path in explicit if PurePosixPath(path).suffix.lower() == "." + fmt)
        candidates = selected or sorted({item["path"] for item in artifacts if item["format"] == fmt} |
                                        {path for path, item in old.items() if item["format"] == fmt})
        if len(candidates) > 1:
            raise ArchitectureError("Ambiguous " + fmt + " architecture artifacts; select one with --artifact: " + ", ".join(candidates))
        if candidates:
            path = candidates[0]
        else:
            companions = sorted(set(existing) | set(explicit))
            path = str(PurePosixPath(companions[0]).with_suffix("." + fmt)) if len(companions) == 1 else "AS-BUILT-ARCHITECTURE." + fmt
        if path not in existing:
            action, reasons = "create", ["artifact_missing"]
        elif path not in old:
            action, reasons = "reconcile", ["existing_artifact_unmanaged"]
        elif old[path] != existing[path]:
            action, reasons = "reconcile", ["artifact_content_changed"]
            if source_changed:
                reasons.append("source_inputs_changed")
            if references_changed:
                reasons.append("reference_evidence_changed")
        elif references_changed:
            action, reasons = "reconcile", ["reference_evidence_changed"]
            if source_changed:
                reasons.append("source_inputs_changed")
        elif source_changed:
            action, reasons = "update", ["source_inputs_changed"]
        else:
            action, reasons = "noop", ["recorded_source_and_artifact_content_unchanged"]
        actions.append({"path": path, "format": fmt, "action": action, "reasons": reasons})
    chosen = {item["path"] for item in actions}
    snapshot_value.update({"command": "plan", "actions": actions, "reference_drift": reference_drift,
                           "references": [dict(item, read_only=True) for item in artifacts if item["path"] not in chosen]})
    return snapshot_value


def record(root, baseline_path, explicit):
    baseline_file = Path(baseline_path).expanduser().resolve()
    baseline = read_json(baseline_file, "baseline")
    if not isinstance(baseline, dict) or baseline.get("schema_version") != SCHEMA_VERSION:
        raise ArchitectureError("Invalid baseline schema; use inspect or plan JSON.")
    if baseline.get("summary"):
        raise ArchitectureError("Summary output cannot be a baseline; save full inspect or plan JSON.")
    validate_source(baseline.get("source"))
    if baseline.get("repo") != str(root):
        raise ArchitectureError("Baseline belongs to a different repository.")
    baseline_artifacts = baseline.get("artifacts", [])
    if not isinstance(baseline_artifacts, list):
        raise ArchitectureError("Invalid baseline artifacts.")
    for entry in baseline_artifacts:
        validate_fact(entry, artifact=True)
        relative_path(root, entry["path"])
    current = snapshot(root, explicit, [entry["path"] for entry in baseline_artifacts])
    if current["source"]["fingerprint"] != baseline["source"]["fingerprint"]:
        raise ArchitectureError("Source content differs from baseline; inspect and reconcile again before recording.")
    available = {item["path"]: item for item in current["artifacts"]}
    missing = sorted(set(explicit) - available.keys())
    if missing:
        raise ArchitectureError("Cannot record missing artifacts: " + ", ".join(missing))
    state = {"schema_version": SCHEMA_VERSION, "generator": GENERATOR,
             "source": current["source"], "artifacts": [available[path] for path in sorted(set(explicit))],
             "references": [available[path] for path in sorted(available.keys() - set(explicit))]}
    encoded = (json.dumps(state, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    target = root / STATE_NAME
    original = target.read_bytes() if target.exists() else None
    changed = original != encoded
    if changed:
        descriptor, temporary = tempfile.mkstemp(prefix=".as-built-architecture.", suffix=".tmp", dir=root)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            # Refuse an intervening malformed state or lost update.
            read_state(root)
            if (target.read_bytes() if target.exists() else None) != original:
                raise ArchitectureError("Managed state changed during recording; retry.")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {"schema_version": SCHEMA_VERSION, "command": "record", "status": "recorded" if changed else "unchanged",
            "state_path": STATE_NAME, "source_fingerprint": state["source"]["fingerprint"],
            "artifacts": state["artifacts"], "semantic_verification": "Not performed; recording freezes content evidence only."}


def check(snapshot_value):
    state = snapshot_value["managed"].get("record")
    snapshot_value["command"] = "check"
    if not state:
        snapshot_value.update({"status": "unmanaged", "source_drift": None, "artifact_drift": None,
                               "reference_drift": None,
                               "unmanaged_artifacts": snapshot_value["artifacts"]})
        return snapshot_value, 1
    managed_paths = {item["path"] for item in state["artifacts"]}
    source_drift = differences(state["source"]["files"], snapshot_value["source"]["files"])
    artifact_drift = differences(state["artifacts"], [item for item in snapshot_value["artifacts"] if item["path"] in managed_paths])
    reference_drift = reference_differences(state, snapshot_value["artifacts"])
    stale = has_drift(source_drift) or has_drift(artifact_drift) or has_drift(reference_drift)
    snapshot_value.update({"status": "drift" if stale else "current", "source_drift": source_drift,
                           "artifact_drift": artifact_drift,
                           "reference_drift": reference_drift,
                           "unmanaged_artifacts": [item for item in snapshot_value["artifacts"] if item["path"] not in managed_paths]})
    return snapshot_value, int(stale)


def summarize(value):
    """Bound the largest evidence payloads; full output remains the record baseline."""
    value["summary"] = True
    source = value["source"]
    value["source"] = {"fingerprint": source["fingerprint"], "file_count": len(source["files"])}
    record_value = value["managed"].get("record")
    if record_value:
        value["managed"] = {"status": "managed", "source_fingerprint": record_value["source"]["fingerprint"],
                            "source_file_count": len(record_value["source"]["files"]),
                            "artifact_count": len(record_value["artifacts"]),
                            "reference_count": len(record_value["references"])}
    excluded = value["scope"].pop("excluded_paths")
    counts = {}
    for entry in excluded:
        counts[entry["reason"]] = counts.get(entry["reason"], 0) + 1
    value["scope"]["excluded_path_count"] = len(excluded)
    value["scope"]["excluded_reason_counts"] = counts
    value["scope"]["excluded_path_examples"] = excluded[:10]
    value["scope"]["excluded_examples_truncated"] = len(excluded) > 10
    return value


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("inspect", "plan", "record", "check"):
        command = commands.add_parser(name)
        command.add_argument("--repo", default=".", help="Git worktree (default: current directory)")
        command.add_argument("--artifact", action="append", default=[], required=name == "record",
                             help="Repository-relative or absolute Markdown/HTML artifact; repeat to select paths")
        if name != "record":
            command.add_argument("--summary", action="store_true", help="Compact JSON for review; cannot be a record baseline")
        if name == "plan":
            command.add_argument("--format", choices=("md", "html", "both"), default="html")
        if name == "record":
            command.add_argument("--baseline", required=True, help="inspect/plan JSON saved outside the repository")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = repository(args.repo)
        explicit = sorted({relative_path(root, value) for value in args.artifact})
        if args.command == "record":
            output, code = record(root, args.baseline, explicit), 0
        else:
            value = snapshot(root, explicit)
            value["command"] = args.command
            if args.command == "plan":
                output, code = plan(value, args.format, explicit), 0
            elif args.command == "check":
                output, code = check(value)
            else:
                output, code = value, 0
            if args.summary:
                output = summarize(output)
        print(json.dumps(output, sort_keys=True, indent=2, ensure_ascii=True))
        return code
    except (ArchitectureError, OSError) as error:
        # Never include file contents, Git stderr, or full exception reprs.
        message = str(error) if isinstance(error, ArchitectureError) else "Filesystem operation failed."
        print(json.dumps({"schema_version": SCHEMA_VERSION, "command": args.command,
                          "status": "error", "error": message}, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
