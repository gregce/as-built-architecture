# As-built architecture

Turn a repository's actual implementation into a visual architecture guide that a person can explore.

This skill guides a coding agent through source inspection, a short interactive brief, component mapping, workflow tracing and verification. It can create ASCII Markdown, an offline HTML explorer, or both. It also refreshes existing artifacts without assuming they should be replaced.

The deterministic helper discovers documents, fingerprints source inputs, plans updates and reports drift. The agent supplies architectural judgment. The distinction follows the approach used by [SpecStory Lore](https://github.com/specstoryai/getspecstory/tree/main/lore).

## Use the skill

Install the repository as a skill with a compatible Agent Skills installer, or clone it and link it into your agent's skill directory. For a local Codex installation:

```sh
git clone https://github.com/gregce/as-built-architecture.git
mkdir -p ~/.codex/skills
ln -s /absolute/path/to/as-built-architecture ~/.codex/skills/as-built-architecture
```

The target must not already contain a different installation. Inspect an existing target before replacing it.

In Codex, invoke:

```text
$as-built-architecture
```

Or supply the brief directly:

```text
Use $as-built-architecture to explain this repo from installation to the
returned result. Create Markdown and an offline HTML explorer, and suggest
product areas for dividing the work.
```

The skill uses the active harness's input dialogs when available. It asks about unanswered choices, shows findings before decisions and preserves instructions already given. Other skill-compatible harnesses can use their equivalent invocation and question tools.

## What the reader gets

- a component map with execution locations, contracts and source links
- walkthroughs from setup or intent to the useful result and its return path
- explanations of checks, refusals, failure paths and recovery
- a clear distinction between source, component tests and accepted live behavior
- optional proposed product area boundaries
- a record that makes later source drift and artifact edits visible

The HTML works offline by default. Its controls explain the system; they do not connect to it or run commands.

## Repository support

Use it with Git-based product repositories regardless of language or framework: web applications, services, CLIs, native apps, libraries and monorepos. The agent derives components and workflows from the target's entrypoints and contracts; it does not assume a particular stack or deployment model.

The helper reports its inspection scope. Ignored files and selected generated or history directories are excluded; submodules are listed as uninspected. Private services and live deployment behavior need separate evidence. Coverage of the available source is not a claim that every external system was inspected.

## Existing documentation

The skill discovers existing Markdown and HTML architecture documents before creating new files. It updates selected files in place, keeps unrequested formats as references, and asks when multiple candidates are ambiguous. A missing companion follows the existing document's location.

When prior hashes exist, it distinguishes changed source from human edits to a document. Unchanged source and artifacts can produce a no-op refresh. A clean fingerprint does not prove claims are correct or that an external deployment has not changed.

## Deterministic tools

Requires Python 3.10 or later and Git. There are no third-party runtime dependencies, API keys or network calls in the helpers.

```sh
python3 scripts/architecture.py inspect --repo /path/to/project --summary
python3 scripts/architecture.py plan --repo /path/to/project --format both --summary
python3 scripts/architecture.py check --repo /path/to/project --summary
python3 scripts/check_explorer.py /path/to/project/AS-BUILT-ARCHITECTURE.html
```

`inspect` reports source facts and artifacts. `plan` proposes create, reconcile, update or no-op actions without editing documents. `check` reports drift from `.as-built-architecture.json`. `record` writes that manifest only after its baseline matches the current source. See [refresh behavior](references/refresh.md) for recording and custom paths.

The HTML checker validates static structure, local references and offline dependencies. Export rendered links for generated content; browser interaction checks remain separate. See [HTML verification](references/html-explorer.md).

## Develop

```sh
python3 -m unittest discover -s tests -v
```

Tests use isolated temporary repositories and files. The helper code must remain deterministic and dependency-free. Its output reports observed facts and scope; it must not decide architectural truth or silently rewrite documentation.

The repository root is the installable skill directory. `SKILL.md` is the agent entrypoint; `references/` holds conditional guidance; `scripts/` contains the deterministic helpers; `tests/` covers their behavior.

Licensed under [Apache-2.0](LICENSE).
