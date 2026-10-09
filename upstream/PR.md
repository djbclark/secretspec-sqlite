# Pull request text for cachix/secretspec

Base: `cachix/secretspec` `main` at `3d1c9ae` ("Warn about ignored unknown
fields in secret declarations (#485)", version 0.21.1). Patches:
`0001-Add-a-sqlite-provider-with-opt-in-history.patch`,
`0002-Document-the-sqlite-provider.patch` in this directory.

---

## Title

Add a sqlite provider with opt-in history (0.22+)

## Body

### Summary

This adds a `sqlite` provider: one row per secret in a local SQLite database
file, keyed by the `{project}/{profile}/{key}` convention or a native
`ref.item`. It is the local-file sibling of `file` and `kdbx`: no service, no
credential, filesystem permissions are the whole access control.

```text
sqlite:./secrets.db                 # beside secretspec.toml
sqlite:///var/lib/app/secrets.db    # absolute
sqlite:./secrets.db?history=true    # also keep an append-only history
```

Appending `?history=true` turns on an append-only, hash-chained ledger inside
the same file. Every `set` and every effective `delete` appends one entry that
snapshots the live key set by SHA-256 digest; the bytes behind each digest are
stored once per key; triggers and foreign keys make snapshot rows undeletable
and tombstones write-once. History is off by default: a plain `sqlite:PATH`
store has only the `secrets` table.

### What is in the change

- `secretspec/src/provider/sqlite.rs`: the provider and its unit tests
  (32 tests: URI parsing, bytes round trip, profile isolation, idempotent
  delete, `secure_delete` leaving no plaintext in the file, 0600/0700 modes,
  batch reads, concurrent writers, native coordinates, and the history
  invariants: foreign keys enforced per connection, append-only rows,
  write-once tombstones, no resurrection after the value returns, blob
  dedup, schema version refusal both ways, and a full hash-chain
  verification, and reading a `TEXT` cell planted by another tool as bytes).
- Feature `sqlite = ["dep:rusqlite"]`, on by default like `kdbx`, registered
  through `catalog.rs`/`disabled.rs` so a build without the feature still
  names it in the error. `rusqlite` 0.40 with `bundled`, so no system SQLite
  is needed on any CI target (Windows included). `sha2` is already a
  non-optional dependency.
- The generic provider suite accepts `sqlite` and `sqlite-history` in
  `SECRETSPEC_TEST_PROVIDERS`; the standalone feature job in `test.yml`
  checks `sqlite`.
- Docs: provider page, sidebar and llms description, available-providers
  table, providers reference section and security table, landing page
  metadata and hero, quick start, README, and a changelog entry. Every
  mention carries `0.22+`.

### Design notes

**Why in-tree and feature-gated rather than an external provider.** 0.21
made out-of-tree providers possible over IPC, and that is the right answer
for stores that talk to a service. A local database file is the opposite
case: asking users to run a sidecar process to read a file on disk would
undo the point of the provider, which is the same argument that keeps `file`,
`dotenv`, and `kdbx` in-tree. The feature gate keeps the SQLite build out of
anyone who does not want it.

**Why history lives in the same provider instead of a second scheme or a
later PR.** History is a write-side policy on the same rows: a `?history=true`
alias and a plain alias naming one path read and write the same `secrets`
table, and `storage_identity()` ignores the flag so cache planning sees one
store. Splitting it off would mean either a second scheme that duplicates the
whole provider or a query parameter the first version rejects and the second
accepts, which is a compatibility trap for anyone who configured it in
between. The ledger is about 300 lines of SQL and one function.

**No public history API, no `rusqlite` in the public surface.** The chain
append is a private function invoked inside the provider's own write
transaction. Nothing re-exports `rusqlite`, so a future `rusqlite` major bump
is not a `secretspec` breaking change. Tooling that wants to tombstone a
captured value opens the file itself; the schema is documented on the
provider page and the triggers make the safe operations the only ones that
succeed.

**Values are `BLOB`.** The `secrets.value` column is `BLOB NOT NULL` in a
`STRICT` table, matching the 0.21 arbitrary-bytes provider contract. Reads
return the bytes exactly.

**No in-place migration of an older history layout.** The history tables are
created with `CREATE TABLE IF NOT EXISTS`, which is silent about a table that
already exists in another shape. The provider stamps `PRAGMA user_version`
and refuses a database that reports a different layout, in either direction,
with a message that says what to do. There is no older layout in any
released SecretSpec, so this is a guard, not a migration.

**Security posture.** Parent directories are created `0700`, the file is set
to `0600` and re-asserted on every open, `secure_delete=ON` so a deleted row's
bytes are overwritten on the freed page rather than left readable (there is
a test that scans the raw file for a canary before and after delete),
`trusted_schema=OFF`, `synchronous=FULL`, `journal_mode=DELETE`, and a 5 s
busy timeout for concurrent writers. The URI accepts no user information and
no query parameter other than `history`, so `every_scheme_rejects_a_userinfo_password`
passes without special-casing.

**Windows.** The URI parser strips the leading slash from `/C:/...` paths the
same way `file.rs` does. The unit tests that touch permissions are
`cfg(unix)`.

**Revision metadata (#440).** Not wired in this change. With history on, the
ledger sequence at which a key's blob last changed would satisfy the
`ProviderRevision` contract (non-secret, stable across clients, derived from
backend generation rather than from secret bytes). That is a small follow-up
once the first provider revisions have settled; without history there is no
generation to report, so plain stores would stay `None` either way.

### Testing

Run against `main` at `3d1c9ae` with the patches applied, on macOS
(aarch64, Rust 1.92.0):

```text
cargo fmt --all -- --check                                              ok
cargo clippy --package secretspec --tests                               ok, no warnings in sqlite.rs (30 pre-existing elsewhere)
cargo check --package secretspec --no-default-features --features sqlite ok
SECRETSPEC_TEST_PROVIDERS=sqlite,sqlite-history \
  cargo test --package secretspec -- provider::sqlite provider::tests provider::disabled
                                                                        108 passed, 0 failed (32 in provider::sqlite)
cargo test --workspace --exclude secretspec-php-native                  see below
```

Workspace suite result (`--exclude secretspec-ipc-conformance --no-fail-fast
-- --skip provider::sops`, see below): 55 test binaries ok, 2,027 tests passed
including the full `secretspec` lib suite (`1732 passed; 0 failed; 4 ignored`),
every `tests/*.rs` integration binary, `secretspec-ipc`, `libsecretspec`, and
doc tests. Three failures, all environmental and present before this change:
`secretspec-derive` `compile_tests` (trybuild path normalization, because the
build used a shared `CARGO_TARGET_DIR` outside the workspace so `$WORK` is
not substituted), the 21 `provider::sops` tests (the `sops` CLI is not
installed on the build machine; CI downloads it), and the
`secretspec-ipc-conformance` build script (needs the `yyjson` C library,
which CI installs with `scripts/install-yyjson.sh`). None touch the provider.

Not run: the Astro docs build (`npm` was not run in the checkout). The new
page follows `file.mdx` and `setec.mdx` exactly in front matter, imports, and
the `VersionCompatibility` component, and the sidebar entry mirrors `file`.

### Checklist (AGENTS.md "Adding Provider Documentation")

- [x] `docs/src/content/docs/providers/sqlite.mdx` with a 0.22 notice
- [x] `docs/astro.config.ts` sidebar and llms sentence
- [x] `docs/src/content/docs/concepts/providers.mdx` table row
- [x] `docs/src/content/docs/reference/providers.mdx` section and security row
- [x] `docs/src/pages/index.astro` metadata array and hero line
- [x] `docs/src/content/docs/quick-start.mdx` config init output
- [x] `README.md` providers list and config init output
- [x] `CHANGELOG.md` entry under Unreleased
- [ ] `docs/src/data/provider-credentials.json`: not applicable, the provider
      declares no `credential_names`
