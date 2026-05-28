# Changesets

This directory holds changesets — small files describing the version bump and
release notes for the npm packages in this repo (currently just
`@vibewarz/game-ui`).

## When you need a changeset

Any PR that changes code in `packages/*` should include a changeset. Run:

```bash
pnpm changeset
```

and follow the prompts (patch / minor / major + a one-line summary). The PR will
include the new `*.md` file in this directory.

## How releases happen

On merge to `main`:

1. The `release` GitHub Action runs `changeset version`, which consumes any
   pending changesets, bumps `package.json` versions, and updates
   `CHANGELOG.md`s. It opens a PR titled "Version Packages" with these
   changes.
2. When that PR is merged, the same workflow runs `changeset publish`, which
   publishes the bumped packages to npm.

You do **not** publish manually.
