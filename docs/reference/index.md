# Reference

The austere catalogue of what the project ships. Pages list exact
paths, signatures, flags, and behaviour. They are consulted, not read
sequentially.

> **What reference is not.** It does not teach, instruct, or argue.
> Recipes belong in [How-to](../how-to/index.md). Rationale belongs
> in [Explanation](../explanation/index.md). Step-by-step belongs in
> [Tutorials](../tutorials/index.md).

## Reference pages

This project currently ships no loom-style primitive catalogues
(`skills/`, `commands/`, `agents/`, `hooks/`), so the auto-discovered
catalogue pages were omitted at scaffold time. If you later add any of
those primitive directories, re-run `/docs-scaffold` to surface the
matching `mkdocs-include-markdown` catalogue page and nav entry.

## Static reference pages

Add static reference pages here as the project grows: CLI surfaces,
configuration files, environment variables, schema definitions, etc.
Each gets its own page in this directory and an entry in the table
above (or in `mkdocs.yml`'s `nav` block).
