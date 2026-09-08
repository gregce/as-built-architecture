# Deterministic discovery and refresh

The helper produces stable JSON from repository facts. It does not interpret architecture, rewrite a document or establish live acceptance.

## Inspect and plan

```sh
python3 <skill-dir>/scripts/architecture.py inspect --repo <repo> --summary
python3 <skill-dir>/scripts/architecture.py plan --repo <repo> --format both --summary
```

The source fingerprint uses file contents, paths and executable status, not wall-clock time or file modification time. The report separately identifies HEAD, dirty state, artifacts, the managed record and excluded inputs. Git-tracked files and nonignored untracked files are considered within the reported scope. Tracked source under names such as `build` and `vendor` is retained; generated-directory exclusions apply to untracked files. Histories and private scratch remain excluded, and submodules are reported as uninspected. Architecture outputs and the record are excluded from source inputs to avoid self-generated drift.

`--summary` bounds source inventory and exclusion details for a useful conversation. Save full JSON without that option when creating a baseline. Summary output cannot be used for recording.

The snapshot is a read-only observation of a working tree. Read the consistency notes; it is not an atomic filesystem snapshot. Hash equality means unchanged observed inputs, not that earlier prose was correct.

The plan selects existing requested files in place. A missing companion normally follows the unique existing file's directory and stem. Repeat `--artifact` to select explicit paths, including custom names:

```sh
python3 <skill-dir>/scripts/architecture.py plan --repo <repo> --format both \
  --artifact docs/AS-BUILT-ARCHITECTURE.md \
  --artifact docs/AS-BUILT-ARCHITECTURE.html
```

When multiple candidate files could satisfy a requested format, the helper reports ambiguity rather than guessing. Present the inspected candidates in an input dialog and rerun with the selected paths. Files outside the requested format remain read-only references.

## Existing artifact policy

| Situation | Agent behavior |
| --- | --- |
| No existing artifact | Create only requested formats at the selected paths |
| Only Markdown exists | Read it for content and user intent; source-check it; create HTML only if requested |
| Only HTML exists | Inspect its rendered interactions and content; preserve its design; create Markdown only if requested |
| Both exist | Reconcile facts against source and keep their descriptions consistent within the authorized update scope |
| Multiple candidates | Inspect and ask which exact paths belong to this task |
| Existing files have no managed record | Treat them as user-owned references; reconcile before adopting them into the record |
| A recorded artifact was edited | Preserve and understand the edit; do not overwrite it from a remembered model |
| Source changed | Review changed files, affected call sites and dependent claims, including return and recovery paths |
| Source and artifact bytes are unchanged | Avoid re-rendering, date-only updates and unnecessary source review unless the user asks for reassessment |
| A recorded artifact disappeared | Report deletion; do not silently resurrect it without considering the current request |

The plan action names describe work, not automatic edits:

- `create`: the requested target is absent
- `reconcile`: an existing target is unmanaged, differs from its recorded bytes, or has changed architecture references to review
- `update`: the managed artifact is unchanged but the observed source changed
- `noop`: both recorded source and artifact bytes agree

`noop` is scoped to the observed inputs and reported exclusions. Changes in external deployment, unobserved services or excluded files still need fresh evidence when the user asks about them. Stable code cannot certify stable production state.

Preserve component IDs, anchors, navigation and human-written explanations where they remain useful. Correct unsupported claims with source evidence. Do not choose between conflicting Markdown and HTML claims based on which file is newer. Do not rebuild the presentation merely because the factual model changed.

## Record reviewed outputs

Keep scratch snapshots outside the target repository so they do not enter their own input inventory. After reading source, capture an inspection baseline. Review any later drift before replacing that baseline.

```sh
python3 <skill-dir>/scripts/architecture.py inspect --repo <repo> > /tmp/architecture-baseline.json
```

If output uses custom names, include their `--artifact` paths during inspection as well as planning and recording so they are excluded consistently from source inputs.

After producing and verifying the artifacts, record their exact bytes:

```sh
python3 <skill-dir>/scripts/architecture.py record --repo <repo> \
  --baseline /tmp/architecture-baseline.json \
  --artifact AS-BUILT-ARCHITECTURE.md \
  --artifact AS-BUILT-ARCHITECTURE.html
```

This writes only `.as-built-architecture.json`. Include that supporting file in the stated plan. A format choice such as HTML-only does not create a Markdown companion; a stricter instruction such as “change only this HTML file” also excludes the manifest. Under that strict scope, skip recording and report that automatic drift tracking was not established.

The command refuses a changed source fingerprint and malformed or unknown existing state. Identical records are not rewritten. Include the record with the documentation when the user requests a commit within that scope.

An intentional README link or other source edit after the baseline changes the fingerprint. Read the reported delta, confirm the change's effect on the explanation, then capture a reviewed final baseline. Do not automatically retry recording with a new snapshot after an unexplained mismatch.

Recording artifact hashes is not evidence the agent checked their claims. Perform source and browser verification before recording. Do not use `record` to silence a stale-output warning.

## Check later drift

```sh
python3 <skill-dir>/scripts/architecture.py check --repo <repo>
```

The result separates added, changed and deleted source paths, managed artifacts and observed architecture references. Reference hashes detect manual changes without making those files managed or authorizing edits. A changed Git HEAD alone need not mean source changed, such as a commit that only records architecture outputs.

Treat exit 0 as success, exit 1 as reported drift or findings, and exit 2 as invalid input or an execution error; check each command's result rather than discarding nonzero output. The plan reports ambiguity explicitly. None of these commands commits, pushes, starts a product service or rewrites Markdown/HTML.
