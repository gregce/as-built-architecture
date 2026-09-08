# Working on this skill

This repository contains the as-built-architecture skill. Editing it is different from invoking it against another project.

- Keep the helper code Python standard-library only. It may run fixed Git commands with argument arrays, but it must not execute repository code, read credentials, fetch networks or start product services.
- The engine establishes file facts, hashes, scope and structural validity. Architectural meaning and live acceptance remain agent judgments tied to evidence.
- Existing user documents are never rewritten by the helper. Ambiguity and unrecorded edits must remain visible.
- Deterministic output has no wall-clock timestamps or random IDs. The same observed repository state and arguments produce identical JSON. Content hashes do not depend on mtimes.
- Test meaningful behavior in isolated temporary repositories. Do not write state into personal projects during tests.
- Run `python3 -m unittest discover -s tests -v` after code changes. Keep schema versions explicit and reject unsupported records rather than silently reinterpreting them.
- Keep interaction guidance helpful and portable. Use structured questions for unresolved choices, not repeated approval rituals. Preserve the user's requested scope and earlier answers.
- Changes to discovery, exclusions or refresh behavior need documentation and fixtures. Do not automatically update a stale baseline to make a failing check pass.

Do not commit generated architecture examples from another project or private session data into this public repository.
