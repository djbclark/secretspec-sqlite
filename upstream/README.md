# Upstream submission for the sqlite provider

This directory holds everything needed to send the sqlite provider to
`cachix/secretspec` as one pull request. Nothing here has been sent; the
operator sends it.

## Contents

| File | What it is |
| --- | --- |
| `0001-Add-a-sqlite-provider-with-opt-in-history.patch` | Provider, registry wiring, feature flag, `Cargo.lock`, CI feature list, changelog |
| `0002-Document-the-sqlite-provider.patch` | Provider doc page and every listing the upstream `AGENTS.md` checklist names |
| `PR.md` | The pull request title and body, including design notes and testing evidence |
| `REDUNDANT-AFTER-UPSTREAMING.md` | What in this fork and in `frdminc/sudo-secretspec` becomes redundant once the PR merges |

## Base commit

The series applies on `cachix/secretspec` `main` at `3d1c9ae`
("Warn about ignored unknown fields in secret declarations (#485)",
`Cargo.toml` version 0.21.1). It targets the 0.22 release and every
user-visible mention is labeled `0.22+`.

## How to send it

The same two commits are already on this fork as branch `sqlite-provider`
(tip `50d3e2b`, base `3d1c9ae`), so the shortest path is:

```bash
gh pr create --repo cachix/secretspec --head djbclark:sqlite-provider \
  --title "$(sed -n '/^## Title/{n;n;p;}' ~/src/secretspec-sqlite/upstream/PR.md)" \
  --body-file <(sed -n '/^## Body/,$p' ~/src/secretspec-sqlite/upstream/PR.md | tail -n +2)
```

To rebuild the branch from the patches instead (for example after upstream
`main` moves):

```bash
git clone https://github.com/cachix/secretspec.git
cd secretspec
git checkout -b sqlite-provider 3d1c9ae      # or current main; rebase if it moved
git am ~/src/secretspec-sqlite/upstream/000*.patch
cargo test --package secretspec -- provider::sqlite provider::disabled
git push <your fork> sqlite-provider
gh pr create --repo cachix/secretspec --title "$(sed -n '/^## Title/{n;n;p;}' ~/src/secretspec-sqlite/upstream/PR.md)" --body-file <(sed -n '/^## Body/,$p' ~/src/secretspec-sqlite/upstream/PR.md | tail -n +2)
```

If `main` has moved and `git am` reports a conflict, the only files that
touch shared upstream lines are the listing edits (`catalog.rs`,
`disabled.rs`, `mod.rs`, `tests.rs`, `Cargo.toml`, `test.yml`, `CHANGELOG.md`
and the docs listings). `sqlite.rs` and `sqlite.mdx` are new files and never
conflict.

## How the series was produced

The provider was ported from `frdminc/sudo-secretspec`
(`secretspec/src/provider/sqlite.rs`, written against SecretSpec 0.19.1) onto
upstream `main` following the shape of the Tailscale Setec provider commit
(`16581eb`), which is the most recent provider addition upstream. The port
replaced `SecretString` with the 0.21 `SecretBytes` contract (the `value`
column is `BLOB`), moved registration to the shared catalog, made the history
chain append private so `rusqlite` is not part of the public API, and added
tests for the bytes contract, the history switch, and chain verification.

## Fork deltas (re-checked 2026-10-09 evening, ClaudeHelm)

`git diff upstream/main...main --stat` on this fork, with `upstream` =
`cachix/secretspec` at `3d1c9ae` (still the tip of upstream `main` on
2026-10-09, so the series needs no rebase):

| Delta | Kind | Conflicts with upstream? |
| --- | --- | --- |
| `upstream/` (this directory: two patches, `PR.md`, this file, the redundancy note) | Local only | Never; upstream has no such directory |
| `AGENTS.md` is the real file, `CLAUDE.md` a symlink to it | Local only (operator convention) | **Yes, on every merge of upstream `main`**: upstream has the pair the other way round (`CLAUDE.md` real, `AGENTS.md -> CLAUDE.md`), so both paths change type |
| `AGENTS.md` content | Local only | Refreshed to upstream's `CLAUDE.md` at `3d1c9ae` verbatim, so only the file/symlink swap remains |
| Provider code (`secretspec/src/provider/sqlite.rs`, feature wiring, docs, changelog) | **Upstream submission** | Lives only on branch `sqlite-provider` (based on `3d1c9ae`) and in the patches here; fork `main` carries none of it |

Fork `main` itself is based on upstream `cf48a7a` (292 commits behind
`3d1c9ae`). Nothing on it needs to reach upstream; the pull request is sent
from `sqlite-provider`, which has no fork-only commits underneath it.
