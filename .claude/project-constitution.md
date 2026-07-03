---
# Project constitution — YAML front-matter
#
# Authoritative tooling profile for sharedvoice. Dispatched workers,
# hooks, and skills read this to stay aligned. Front-matter below was
# auto-detected + confirmed during /loom-adopt P5 (2026-07-02); the
# prose body is a [HUMAN AUTHOR] stub — fill it in.
#
# Leave keys as empty strings ("") / empty lists ([]) when they don't
# apply — don't delete keys.

shell:
  # No devbox.json / flake.nix / poetry env detected — plain host shell.
  enter: ""
  run_prefix: ""

# python defaults chosen at adoption; no lockfile/manifest present yet.
package_manager: pip

language:
  runtime: python
  # No version marker yet — pin when the runtime is fixed.
  version: ""

# Bash patterns the agent must NEVER run here (lock-in posture).
# Empty until a package_manager lock-in decision is authored.
forbidden: []

canonical_commands:
  build: ""
  test: "pytest"
  lint: "ruff check ."
  gen: ""
  dev: ""
  deploy: ""

# Escape hatches that bypass constitution enforcement. Use sparingly.
bypass_patterns: []

# Project-specific ARCHITECTURAL invariants (enforced across Bash +
# write-class tools). None yet — uncomment + adapt when one exists.
#
# invariants:
#   - id: <e.g. no-direct-file-io>
#     applies_to:
#       - Write
#       - Edit
#       - MultiEdit
#     deny_pattern: "<e.g. \\bopen\\( >"
#     message: "<e.g. reason this is forbidden>"
---

# sharedvoice — project constitution

> [HUMAN AUTHOR] TODO: One-paragraph statement of what this
> constitution is for and who reads it. Ground it in what sharedvoice
> actually is (the project has no source yet — describe the intended
> mission).

## Tooling choices

> [HUMAN AUTHOR] TODO: Explain *why* the front-matter values are what
> they are.

- **Shell**: [HUMAN AUTHOR] TODO — currently no shell wrapper; note if
  one is planned (devbox / nix / poetry).
- **Package manager**: [HUMAN AUTHOR] TODO — `pip` chosen at adoption;
  confirm or switch (uv / poetry) once dependencies exist.
- **Language**: [HUMAN AUTHOR] TODO — `python`; pin `language.version`
  when fixed.
- **Canonical commands**: [HUMAN AUTHOR] TODO — `test: pytest`,
  `lint: ruff check .` mirror `.beads/preflight.template`. Fill
  `build` / `gen` / `dev` / `deploy` as the project grows.

## Forbidden patterns

> [HUMAN AUTHOR] TODO: For each `forbidden:` entry, name the failure
> mode it guards against (e.g. lock in `pip` by forbidding `poetry
> install` / `uv pip install`). Currently empty.

## Bypass patterns

> [HUMAN AUTHOR] TODO: For each `bypass_patterns:` entry, name the
> legitimate use case. Currently empty.

## Lineage

> [HUMAN AUTHOR] TODO: Beads / decision drawers that informed these
> choices. Adoption context: captured by `/loom-adopt` P5 on
> 2026-07-02; tooling profile mirrors the P1 audit drawer
> `drawer_sharedvoice_decisions_281fc837258180ee634fcef0`.
