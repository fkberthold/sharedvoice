# Install sharedvoice

> **Goal:** get sharedvoice on a development machine and verify
> the install.
>
> **Prerequisites:** a POSIX shell, `git`, [devbox](https://www.jetify.com/devbox)
> (which provisions the rest of the toolchain), and read access to
> https://github.com/fkberthold/sharedvoice.

## Steps

1. **Clone the repository.**

    ```bash
    git clone https://github.com/fkberthold/sharedvoice
    cd sharedvoice
    ```

2. **Enter the dev shell.** SharedVoice uses devbox to provision a
   reproducible environment (Python 3.12, ffmpeg, Node, pnpm). The
   first entry builds a virtualenv and installs the backend and docs
   dependencies, so it may take a minute:

    ```bash
    devbox shell
    ```

3. **Verify the install.** Run the test suite. It should exit zero and
   print a passing run:

    ```bash
    devbox run test
    ```

## Troubleshooting

- **`devbox: command not found`.** Install devbox first — see the
  [devbox install guide](https://www.jetify.com/devbox/docs/installing_devbox/),
  then re-run step 2.
- **First `devbox shell` fails while installing dependencies.** The
  init hook builds `.venv` and runs `pip install`. Delete the partial
  environment (`rm -rf .venv`) and re-enter the shell to rebuild it
  cleanly.
- **`devbox run test` reports no tests collected.** Confirm you are at
  the repository root; the test script activates `.venv` and runs
  `pytest` over the `backend/` suite.

## What to read next

- [Tutorial: Getting started](../tutorials/getting-started.md) — your
  first guided run-through after install.
- [Reference](../reference/index.md) — the catalogue of every
  sharedvoice surface.
