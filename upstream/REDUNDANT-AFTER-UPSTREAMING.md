# What becomes redundant once the sqlite provider is upstream

Written against the series in this directory (base `3d1c9ae`, target 0.22).

## In this repository (`djbclark/secretspec-sqlite`)

The fork exists for one purpose, developing the provider for merge (issue #1).
After the PR merges and a release ships it:

1. `upstream/` is historical. The patches, `PR.md` and this note stop being
   inputs to anything; keep them for the record or delete the directory.
2. Issue #1 can be closed with the upstream PR link.
3. The fork itself has no remaining job. Archive it, or keep it as a plain
   mirror of upstream `main` for future contributions. Its `main` is 292
   commits behind upstream and carries only two documentation commits of its
   own (`CLAUDE.md` symlink and `AGENTS.md` restore); nothing on it needs to
   survive.

## In `frdminc/sudo-secretspec` (the downstream user)

The downstream carries its own copy of the provider plus two seams. Once it
rebases onto a SecretSpec release that contains the provider:

1. `secretspec/src/provider/sqlite.rs` (1,416 lines) is replaced by the
   upstream file. Drop the downstream copy.
2. `secretspec/Cargo.toml`: the `sqlite = ["dep:rusqlite", "dep:sha2"]`
   feature, the pinned `rusqlite = "0.31"` and the `sha2` optional dependency
   go away; upstream provides `sqlite = ["dep:rusqlite"]` with `rusqlite`
   0.40 `bundled` from the workspace. The FORK-AI.md note about `bundled`
   hanging `libsqlite3-sys` on macOS should be re-tested: the upstream build
   with `bundled` compiled and passed here on macOS in about two minutes.
3. `secretspec/src/provider/mod.rs`: the `#[cfg(feature = "sqlite")] pub mod
   sqlite;` line is upstream's now.
4. `secretspec/src/lib.rs`: `pub use rusqlite;` and `pub mod sqlite_history`
   are the seams the issue said to remove. Upstream does not export either.

Two things do **not** disappear and need a downstream decision:

- **Schema: `value TEXT` becomes `value BLOB`.** The upstream `secrets`
  table is `value BLOB NOT NULL` in a `STRICT` table (the 0.21 bytes
  contract). A downstream database created by the 0.19-era provider has
  `value TEXT NOT NULL`, and a STRICT `TEXT` column refuses a BLOB insert, so
  the upstream provider cannot write to an existing downstream file without a
  one-time rebuild: create `secrets_new` with the upstream shape, `INSERT
  INTO secrets_new SELECT item, CAST(value AS BLOB) FROM secrets`, drop and
  rename. History is unaffected: `value_blobs.value_blob` was already `BLOB`,
  and the chain hashes the SHA-256 of the bytes, which is identical for the
  same UTF-8 text, so entry hashes and `head` stay valid. Reads from the
  upstream provider against a `TEXT` column work before the rebuild (the
  provider reads a cell as bytes whether SQLite holds it as `TEXT` or
  `BLOB`), so the rebuild can be done lazily before the first write, or
  once by a `doctor` step.
- **The broker's history append.** Downstream's `destroy` opens its own
  connection and calls `capture_history` so tombstones can reference a fresh
  entry. Upstream keeps that function private (the PR body explains why: no
  `rusqlite` type in the public API). Options, cheapest first:
  1. Keep a one-line downstream patch that changes `fn capture_history` to
     `pub fn capture_history` in the upstream file. It is a visibility change
     on a line upstream has no reason to touch, so it rebases cleanly.
  2. Re-implement the append in the broker. It is one function (about 100
     lines) over a documented schema; the hash input is `previous_hash +
     "\n" + canonical JSON` with the keys `operation`, `previous_hash`,
     `sequence`, `timestamp_ns`, `values` in that (BTreeMap) order.
  3. Propose a follow-up upstream once the tombstone workflow is public:
     a path-based `SqliteProvider::destroy_captured_value(...)` that does the
     tombstone and the chain append in one transaction, so no caller needs a
     connection type at all.

Everything else downstream (privilege separation, the broker, the audit
ledger) is out of scope for upstream by the issue's own decision and stays
where it is.
