<h1 align="center">As-built architecture</h1>

<p align="center"><strong>Understand the system your code actually builds.</strong></p>

<p align="center">
  <a href="https://github.com/gregce/as-built-architecture/actions/workflows/validate.yml"><img src="https://github.com/gregce/as-built-architecture/actions/workflows/validate.yml/badge.svg" alt="Validate skill"></a>
  <a href="https://skills.sh/gregce/as-built-architecture"><img src="https://skills.sh/b/gregce/as-built-architecture" alt="skills.sh installs"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/runtime_dependencies-0-brightgreen" alt="Zero third-party runtime dependencies">
</p>

<p align="center">
Turn a product repository into source-linked diagrams and an interactive architecture guide.<br>
Trace components, complete workflows, state, recovery and current limits.<br>
Refresh the explanation as the code changes, preserving useful existing documentation.
</p>

Built in the open [Agent Skills](https://agentskills.io) format. Install it for Claude Code,
Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Cline, Windsurf and other
[supported coding agents](https://github.com/vercel-labs/skills#supported-agents).

## Install

```sh
npx skills add gregce/as-built-architecture --skill as-built-architecture
```

In an interactive terminal, the installer lets you choose agents and installation options.
Installation defaults to the current project. Add `--global` to use it across projects,
or select agents explicitly:

```sh
npx skills add gregce/as-built-architecture --skill as-built-architecture --global \
  --agent claude-code codex cursor gemini-cli
```

Update an installation later:

```sh
npx skills update as-built-architecture
```

The current `skills` installer requires Node.js 22.20 or later. Running the skill's helpers
requires **Python 3.10 or later and Git**; they use only the Python standard library.
The helper code needs no API keys or network access. Installation downloads the public
repository. See the [installer reference](https://github.com/vercel-labs/skills#install-a-skill)
for additional agents, scopes and options.

## Get started

Open the product repository in your coding agent and ask:

```text
Use as-built-architecture to explain how this repository works.
```

The skill inspects the repo first, then guides you through any unanswered choices: who
the guide is for, Markdown or HTML, and which existing documents to refresh. Give a
specific brief to skip choices you have already made.

| Say | Get |
| --- | --- |
| `Explain this repository` | Guided discovery, a component map and complete workflows |
| `Create an offline HTML architecture explorer` | A standalone document with interactive views and source links |
| `Create Markdown with ASCII diagrams` | Architecture readable in a normal editor |
| `Focus on failures and recovery` | Guards, refusal paths, retries, persisted state and recovery limits |
| `Refresh docs/AS-BUILT-ARCHITECTURE.html; preserve the design and my notes` | An update in place, with existing edits reconciled against source |
| `Check what changed since the last architecture snapshot` | Source and document drift, when a recorded baseline exists |

Product squads and team assignments are included only when explicitly requested.

## What it produces

- a component map with execution locations, contracts and source links
- walkthroughs from installation or input to the useful result and its return path
- explanations of checks, failure paths, state and recovery
- clear evidence boundaries: implemented library, connected entrypoint, component test or accepted live behavior
- Markdown, an offline HTML explorer, or both
- a `.as-built-architecture.json` record for future refreshes, when the requested file scope permits it

The HTML explains the system without connecting to it or running its commands. Its
source links work when the repository accompanies the file. The agent chooses views
that fit the product and preserves an existing visual system where useful.

## How it works

```text
Inspect source and existing docs
             |
Clarify the reader's unanswered choices
             |
Trace components and complete workflows
             |
Create or refresh Markdown / HTML
             |
Verify claims, links and interactions
             |
Record the reviewed source and document fingerprints
```

**Deterministic helpers, architectural judgment from the agent.** File discovery,
hashing, comparisons and structural checks run in Python. The agent reads the source,
decides which boundaries matter and writes the explanation. This division follows
the approach used by [SpecStory Lore](https://github.com/specstoryai/getspecstory/tree/main/lore).

| Mechanism | What it establishes |
| --- | --- |
| Stable source fingerprint | Whether observed file contents, paths or executable status changed |
| Separate document fingerprints | Whether generated architecture or a reference document was edited |
| Refresh plan | Whether a selected document needs creation, updating, reconciliation or no change |
| Baseline check | Whether the source still matches the snapshot reviewed during writing |
| HTML checker | Whether static links, IDs, tab relationships and offline dependencies have findings |

Fingerprints ignore modification times and exclude recognized architecture outputs
from source inputs. An unchanged snapshot can avoid a needless rewrite. Changed
source or human edits give the agent concrete differences to review. The generated
prose and diagrams still involve model judgment; hashes do not establish correctness
or live deployment status.

## Built for multiple coding agents

Every installation uses the same `SKILL.md`, reference documents and Python helpers.
The workflow adapts to the tools the host provides: input dialogs when available,
concise chat questions otherwise; authorized subagents when useful, sequential source
inspection otherwise. Browser verification uses the host's browser tools and is
reported as unavailable when those tools cannot run.

| Agent | Installer name | Start the skill |
| --- | --- | --- |
| Claude Code | `claude-code` | `/as-built-architecture` |
| Codex | `codex` | `$as-built-architecture` |
| Cursor | `cursor` | Ask to use `as-built-architecture` |
| Gemini CLI | `gemini-cli` | Ask to use `as-built-architecture` and accept activation if prompted |
| GitHub Copilot | `github-copilot` | Ask to use `as-built-architecture` |
| OpenCode | `opencode` | Ask to use `as-built-architecture` |
| Cline | `cline` | Ask to use `as-built-architecture` |
| Windsurf | `windsurf` | Ask to use `as-built-architecture` |

For Windsurf project installs, the current CLI creates a link only when `.windsurf/`
already exists. Initialize the project in Windsurf first, or use `--global`.

Use an agent version that supports Agent Skills and allows repository reads, file edits
and command execution. Installation support and a full architecture run are separate
checks; available models, dialogs and browser tools affect the experience. See the
[Claude Code](https://code.claude.com/docs/en/skills),
[Codex](https://learn.chatgpt.com/docs/build-skills#how-chatgpt-and-codex-use-skills) and
[Gemini CLI](https://geminicli.com/docs/cli/skills/) skill documentation for host behavior.

## Existing documentation and repository scope

Existing `AS-BUILT-ARCHITECTURE.md` and `.html` files are discovered before new files
are planned. Custom paths can be selected explicitly. Ambiguous candidates prompt a
choice, and a missing companion follows the existing document's location.

An HTML-only refresh keeps Markdown as a reference. Manual notes, anchors and useful
presentation survive reconciliation. When documents disagree, the agent checks source
instead of choosing the newest file. An explicit restriction to one file also skips
the supporting baseline record.

The workflow applies to Git-based web apps, services, CLIs, native apps, libraries and
monorepos. The helper reports excluded files and uninspected submodules. Ignored files,
external services and live deployments need additional evidence when relevant.

## Distribution and skills.sh

| File | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | Standard skill metadata, requirements and agent instructions; the CLI discovers it at the repo root |
| [skills.sh.json](skills.sh.json) | Directory-page configuration using the official skills.sh schema |
| [agents/openai.yaml](agents/openai.yaml) | Optional Codex display metadata; other agents use the standard skill files |

[skills.sh lists skills through CLI installation telemetry](https://skills.sh/docs/faq#how-do-i-get-my-skill-listed-on-the-leaderboard).
The [directory configuration](https://skills.sh/docs/customize) controls presentation;
it does not register the skill or change installation behavior. Listing and page
updates can take time to appear. The repository itself is the distributable skill;
no npm package or agent-specific plugin is required.

## Developing

```sh
git clone https://github.com/gregce/as-built-architecture.git
cd as-built-architecture
python3 -m unittest discover -s tests -v
```

The tests use isolated temporary repositories. Keep the helper code dependency-free
and follow [AGENTS.md](AGENTS.md) when changing discovery, refresh behavior or validation.

For live development, link the clone into an agent's skills directory. For example,
Claude Code uses `~/.claude/skills/as-built-architecture` and Codex supports
`~/.codex/skills/as-built-architecture`. Inspect an existing installation before
replacing it. A link to the clone reflects edits immediately; a CLI-managed installation
uses downloaded files and needs `npx skills update` to follow remote changes.

## Documentation

| Document | Contents |
| --- | --- |
| [SKILL.md](SKILL.md) | The source-inspection and architecture-writing workflow |
| [Interaction](references/interaction.md) | Useful dialogs, model previews and incremental refresh conversations |
| [Discovery and refresh](references/refresh.md) | Input scope, existing files, fingerprints and baseline records |
| [HTML explorers](references/html-explorer.md) | Offline presentation, interaction behavior and verification |
| [AGENTS.md](AGENTS.md) | Development rules and required checks |

Licensed under [Apache-2.0](LICENSE).
