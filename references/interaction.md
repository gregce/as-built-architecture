# Guided architecture workflow

Make the interaction feel like working with a knowledgeable colleague. Show findings before asking the user to choose. Use short input dialogs at real decision points, and keep the code-reading work moving.

## Dialog mechanism

Use the active harness's structured input tool. In Codex this may be `request_user_input_async`; in another harness it may be `AskUserQuestion` or an equivalent. Do not switch execution modes just to expose a dialog. When no dialog tool is available, ask a concise question in chat.

Keep dialogs self-contained. Include the relevant discovered paths and the consequence of each choice. Offer 2 or 3 distinct options and put the recommendation first. Ask one question when possible; bundle at most 3 closely related questions. Do not include an “Other” option when the interface supplies free text automatically.

For asynchronous questions, continue independent inspection while awaiting the reply. Give the user reasonable time to answer, normally at least 60 seconds for a simple optional choice. Then state a conservative assumption if needed. Time passing is never approval for a destructive or external action.

Reconcile user steering into the active task. A question about status is not a new objective, and a requested format or path should not be asked again.

## Start from what is already known

Run discovery first when the repository is available. Then use a brief opening such as:

> I found `docs/AS-BUILT-ARCHITECTURE.md` and a root HTML explorer. The Markdown has edits since the last recorded snapshot. I’ll trace the current entrypoints before reconciling them.

Useful first questions, only when unanswered:

| Missing decision | Example dialog | Suggested options |
| --- | --- | --- |
| Reader's job | What should this help you understand first? | Full workflow; operation and recovery; components and data flow |
| Deliverable | Which architecture artifacts should I create or refresh? | Markdown and HTML; HTML only; Markdown only |
| Existing design | How should I treat the existing explorer? | Refresh in place; preserve it and create a separate view; rebuild its presentation |

The exact request wins over these examples. If the user asks for an HTML explorer like a named prior session, the format and explanatory pattern are already known.

State that normal output includes a small `.as-built-architecture.json` manifest for later refreshes. This is supporting metadata, not another reader format. Respect an explicit restriction to named files by skipping it, without another permission dialog.

## Existing files need context, not a generic overwrite question

Present the actual inventory and what the helper can establish:

- exact paths, requested versus reference-only files
- unmanaged versus recorded files
- source drift versus artifact edits
- ambiguity, such as two HTML candidates in different documentation directories

Then ask only the unresolved decision. For example:

> I found `AS-BUILT-ARCHITECTURE.html` and `docs/archive/AS-BUILT-ARCHITECTURE.html`. Which should this update target?

Offer those actual paths with short descriptions after inspecting both. Do not rank by modification time. If the user already named a target, use it and keep other files as references.

Updating an existing file is implied by “refresh this architecture”; no extra permission checkpoint is needed. Preserve its useful explanatory structure and manual edits while correcting facts. Replacing its entire presentation is a separate choice unless the request already authorizes that.

## Make the first review concrete

After tracing the source, show a small model preview: component names grouped by execution location, the main input-to-result journey and one or two findings that materially change the picture. Do not ask the user to approve a vague plan before there is something useful to assess.

For a broad brief, an optional refinement dialog can ask:

> The map currently covers browser, command service, worker and artifact store. The worker supports retry, but its production launcher does not enable it. Where should I add the most detail?

Suggested options might be “Keep the balanced overview”, “Expand failure and recovery” and “Expand component interfaces”. Derive these from the actual source. If the user's scope is already precise, state the model and proceed without another dialog.

The preview is a factual review opportunity. Do not demand human approval of every component or treat an optional response as the only way to finish authorized work.

## Let the reader try the result

When there is a rendered artifact, open it through the available browser or provide its direct local link. Suggest a short path through the result:

1. select the entry component and read its contract
2. follow the main journey to the returned result
3. choose a failure case and see where execution stops

If another preference question would help, point to the actual artifact and ask a narrow question such as “Is the recovery view detailed enough for your team?” Do not add a final permission request merely to end the turn. Complete verification and deliver the result when the requested scope is satisfied.

## Refreshes should feel incremental

On a later invocation, begin with what changed, not the entire initial interview. Use remembered artifact paths and current repository evidence. Example:

> The last record covered both files. Four source files changed, and the HTML has one unrecorded edit. I’ll preserve that edit and update the affected workflow and recovery explanations.

If neither source nor artifacts changed, say so and offer a specific optional improvement only when useful. Do not manufacture a new date, a rewritten introduction or a new layout to make the refresh appear productive.
