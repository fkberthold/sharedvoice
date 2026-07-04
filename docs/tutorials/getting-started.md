# Getting started

> **You will:** install sharedvoice on a fresh machine, run it
> against a small example, and confirm the result. About 10–20 minutes.
>
> **You will need:** devbox (which provisions the toolchain), a
> terminal, and read access to the sharedvoice repository at
> https://github.com/fkberthold/sharedvoice.

This is a *thin tutorial*: one path, one aha moment, no branches. If
you want to do something the tutorial doesn't show, finish it first
and then jump to the [how-to guides](../how-to/index.md).

## 1. Install

Follow the [Install how-to](../how-to/install.md) to get
sharedvoice on your machine. Come back here when the install
verification step passes.

## 2. Start the server and fetch the corpus

From inside `devbox shell`, start the API server:

```bash
cd backend
uvicorn sharedvoice.main:app
```

On first start the app seeds the affirmation corpus into a local
SQLite database (under `var/`) and begins serving it. Leave it
running and, in a second terminal, ask it for the affirmations:

```bash
curl http://localhost:8000/affirmations
```

You should see a JSON array of the sixteen daily affirmations, each
with its title and body text. If you get an empty array or a
connection error, the server didn't start — re-read step 1.

## 3. Read what came back

Look at the JSON from step 2. Each entry is one affirmation from the
sangha's daily practice, served in recitation order with its title
and body. That corpus — the same text every contributor recites — is
the spine the whole alignment-and-mix pipeline is built around. This
is the *aha moment*: the server is already holding the shared liturgy,
ready for voices to be recorded against it.

## What you have now

- A running SharedVoice server you can restart at will.
- The affirmation corpus served over a live API endpoint.
- Enough context to read the [how-to guides](../how-to/index.md)
  knowing which task each guide solves.

## What to read next

- [How-to: Install](../how-to/install.md) — re-installing, upgrading,
  or installing on a second machine.
- [Reference](../reference/index.md) — the catalogue of every
  sharedvoice surface you might want to consult.
- [Explanation: Mental model](../explanation/mental-model.md) — why
  sharedvoice is shaped the way it is.
