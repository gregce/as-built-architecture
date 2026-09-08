---
name: as-built-architecture
description: Create or refresh visual as-built architecture documentation from a repository's actual implementation, including ASCII Markdown guides and interactive offline HTML explorers. Use to explain built components, end-to-end workflows, execution gates, persistence, current gaps or architecture-based product areas. Includes guided input dialogs and deterministic handling of existing architecture files. Not for designing a future architecture or making a generic code summary.
license: Apache-2.0
---

# As-built architecture

Help a reader understand what exists, how it connects, what runs under which conditions, where results go, and what remains unfinished. Build around source-backed components and complete journeys, with diagrams doing part of the explaining.

The helper code discovers, fingerprints, compares and validates. The agent interprets the source, names components and writes explanations. A hash match establishes unchanged bytes, not architectural truth or live acceptance.

## Start with discovery and a useful conversation

Read [references/interaction.md](references/interaction.md) for the guided flow. Use the harness's input dialogs for meaningful choices, with concise context and a recommended option. Skip facts the user already supplied. Do not turn optional checkpoints into permission gates or pause useful independent work while awaiting an optional answer.

1. Identify the repository and read its instructions. If a previous session is supplied, recover its first task prompt, corrections and final artifact locations, then inspect those artifacts. Reuse their explanatory pattern, not their product claims or branding.
2. Run the read-only helper using the actual skill directory:

   ```sh
   python3 <skill-dir>/scripts/architecture.py inspect --repo <repo> --summary
   ```

3. Summarize the discovered architecture files, source revision and any recorded drift before asking about them. Resolve only missing choices: reader's purpose, Markdown/HTML/both, and how to treat pre-existing documents. For an unspecified new deliverable, recommend both. Respect an explicit HTML-only or Markdown-only request.
4. Run `plan --repo <repo> --format md|html|both --summary`, adding `--artifact <repo-relative-path>` when the user names files or discovery is ambiguous. Read [references/refresh.md](references/refresh.md) whenever existing files or a managed record are found. Use full output, without `--summary`, when saving a recording baseline.

The tools report scope and exclusions. Inspect those before claiming complete coverage. Resolve ambiguous candidates instead of selecting the newest file by modification time.

## Trace the current system

Record the inspection date, source revision and relevant working-tree scope. Separate committed source from an unfinished candidate. If another session changes the repository, name the inspected baseline instead of implying the document continuously follows it.

Start from executable composition, not folder names. Follow important actions from setup or input through execution, result and return path. Read the code that answers:

- what installs, initializes or launches the system, and which prerequisites can stop it
- which operations the UI, route and consumer actually expose
- which process, account, service, machine or client performs each step
- what crosses each boundary: intent, proof, command, lease, event, artifact, verdict or receipt
- which store owns intent, execution and evidence, and which views are derived or bounded
- what serializes work, which retries repeat transport, and which could repeat a side effect
- what proves success, how failure becomes visible and what recovery actually supports
- which checks are deterministic, agent-driven or human-driven, and when they are skipped or refused

Distinguish these evidence levels when they affect comprehension:

| Level | What can be claimed |
| --- | --- |
| Implemented library | Behavior exists, but a product entrypoint may not call it |
| Composed source | An entrypoint connects it, possibly behind a runtime gate |
| Component-tested | A named test or measurement establishes a limited property |
| Accepted live behavior | Dated evidence establishes actual operation |
| In progress or planned | Candidate work or intent with a missing connection |

Attribute old test totals to their checkpoint. A documentation review is not a fresh full test run, and a passing suite is not deployment evidence. Use narrow read-only measurements where needed; do not start services, install packages, authenticate accounts or mutate projects merely to illustrate documentation.

Pay particular attention to distinctions that easy summaries lose: production versus controlled-proof paths; network access versus application identity; controller versus credentialed worker; accepted versus answered; internal streaming versus displayed output; refresh versus restart; mirror versus restore; normal transitions versus exceptional recovery; and different method variants' repair behavior. Do not invent a shared approval step merely because several state machines contain gates.

If delegation is available and authorized, divide large read-only audits by bounded responsibility, such as runtime, browser/control, host/installation and evidence/method. Request actual call sites and limitations. Integrate reports into one model and resolve disagreements against code. Do not assign overlapping artifact edits.

## Model before rendering

Give components stable IDs based on their jobs. Split at execution or authority boundaries, not every directory. Each needs a job statement, concrete input/output, work performed, execution owner, state, current limit and source evidence.

Build journeys around real tasks, including the useful result's return to the browser or working directory. Show meaningful branches and current stops in the diagram itself. A conditional future step stays conditional. A project-neutral interface is not proof that every application type works; never import a check classifier from an exemplar without finding it in the target source.

Offer the reader a compact component map and one consequential finding before investing in the final rendering, as described in the interaction reference. When the brief is already precise, this can be an update rather than another question.

Propose product areas only when requested or established by the reader's job. Name responsibility, files, inputs, outputs, exclusions and neighbors. Label ownership as proposed. Shared schema and cross-process contracts still need coordinated changes.

## Create or refresh the artifacts

Use the requested paths. Typical names are `AS-BUILT-ARCHITECTURE.md` and `AS-BUILT-ARCHITECTURE.html`. Produce only requested formats. When both are requested, use one factual model and reconcile the outputs.

For Markdown, show the whole system, then component contracts, journeys, gates, state and current limits. Use ASCII boxes and labeled arrows when requested. Keep diagrams readable in a normal editor and explain specialized terms beside them.

For HTML, read [references/html-explorer.md](references/html-explorer.md). Default to a standalone offline document, relative source links and the repository's existing visual system. It does not need an application scaffold or deployment. Preserve established navigation, IDs and useful human-written content when refreshing existing files.

Use the helper's plan as evidence, not permission to overwrite. It never rewrites architecture documents. A `noop` action is an opportunity to avoid churn; do not refresh dates or re-render identical output merely to show activity. Source changes and human edits require agent reconciliation before recording a new baseline.

## Verify and record

1. Recheck important claims against call sites, guards and documented failure paths. Use an independent reviewer when it would materially help and delegation is authorized.
2. Run the HTML checker where applicable. It checks static structure and links, not JavaScript behavior or claim truth. Export rendered links for dynamically generated content, as the HTML reference explains.
3. Exercise the actual browser controls: views, components, journey branches, cases, cross-links, detailed URL reloads, retained selection and keyboard navigation. Inspect desktop/mobile and supported themes. Check promised print completeness. Report unavailable checks plainly.
4. Review the diff and source drift. If source changed during writing, examine the delta before taking a new baseline. An intentional README link also changes the input snapshot; record after reviewing that final change.
5. Follow [references/refresh.md](references/refresh.md) to record the reviewed source and exact artifact hashes in `.as-built-architecture.json`. Include this supporting file in the stated output plan. If the user restricts changes to specific files, honor that restriction and report recording skipped rather than adding the manifest. The record supports future drift checks; it is not an automatic architectural approval.

Link the outputs, state their evidence boundary and actual validation, and give a short reading path. Add a concise README link if useful. Creating the documentation does not itself authorize a commit, push or deployment; follow the user's requested actions.
