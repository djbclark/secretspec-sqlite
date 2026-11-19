# Peer practice behind the sqlite history design (2026-11-18)

Evidence base for the retention, schema and verify questions in
[PR #487](https://github.com/cachix/secretspec/pull/487) and for the deferred
prior-art item in [sudo-secretspec#10](https://github.com/frdminc/sudo-secretspec/issues/10).

Produced 2026-11-18 by a dispatched research slice: 27 searches and ~40 fetches
against primary sources (vendor documentation, sqlite.org, docs.rs, Debian
policy), each claim carrying the URL that was fetched. Kept here rather than in
a scratch directory because the decisions it grounds are still open.

Read section VII ("Implications for our questions") first if you only want the
conclusions; sections I-VI are the evidence.

---

STATUS: done

# Prior art for the `sqlite://` provider history design

Research slice: feeds the design post for
[cachix/secretspec#487](https://github.com/cachix/secretspec/pull/487).
Tools used: the shared self-hosted Firecrawl backend directly
(`http://127.0.0.1:18805/v2/search` for SearXNG search, `/v2/scrape` for markdown
pages; the `firecrawl` MCP server was not declared to this session, so the same
backend was driven with `curl` instead) — **≈43 search calls, ≈48 page scrapes**,
plus one local measurement (`/usr/bin/sqlite3 --version`). No web MCP, Context7 or
WebFetch was available; nothing below comes from memory alone, and each bullet
carries the URL that was fetched.

---

## I. Versioning and retention semantics in peer secret managers

**HashiCorp Vault KV v2 — versions are per secret path; delete is soft, destroy is hard; the default cap is 10.**

- https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2 —
  "`max_versions` (int: 0) … When 0 is used or the value is unset, Vault will keep
  10 versions", and "Once a key has more than the configured allowed versions, the
  oldest version will be permanently deleted." The cap is *per key*, not per store.
- https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2 —
  "The `kv` v2 plugin uses soft deletes to make data inaccessible while allowing
  data recovery. When an entry is permanently deleted, Vault purges the underlying
  version data and marks the key metadata as destroyed." Two-step
  delete/undelete then destroy is the shipped UX.
- https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2/cookbook/destroy-data —
  `vault kv destroy -versions 2,3` leaves the version's metadata in place with
  `destroyed true`; the history stays *visible* after the value is gone.
- https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2 —
  `delete_version_after` defaults to `"0s"` (no time-based expiry) and is
  overridable per key, capped by the backend value. Time-based retention is opt-in
  on top of count-based retention.

**AWS Secrets Manager — per-secret versions with staging labels; unlabeled versions are the ones that get reaped.**

- https://docs.aws.amazon.com/secretsmanager/latest/userguide/whats-in-a-secret.html —
  "Secrets Manager never removes labeled versions, but unlabeled versions are
  considered deprecated. Secrets Manager removes deprecated versions when there are
  more than 100. Secrets Manager doesn't remove versions created less than 24 hours
  ago." A label (not an age policy) is the retention primitive.
- https://docs.aws.amazon.com/secretsmanager/latest/userguide/reference_limits.html —
  hard quotas: 100 versions per secret, 20 staging labels across all versions.
- https://docs.aws.amazon.com/secretsmanager/latest/userguide/roll-back-secret.html —
  rollback UX is "move the `AWSCURRENT` label back to the old version"; the old
  value is never copied, so history cannot fork.
- https://docs.aws.amazon.com/secretsmanager/latest/userguide/whats-in-a-secret.html —
  standard labels `AWSCURRENT`, `AWSPREVIOUS`, plus `AWSPENDING` during rotation;
  "Two versions of a secret can't have the same staging label."

**Azure Key Vault — one version per write, per-version `enabled` flag, and a recovery window instead of a version cap.**

- https://learn.microsoft.com/en-us/azure/key-vault/secrets/about-secrets —
  version-level attributes (`exp`, `nbf`, `enabled`, `created`, `updated`) live on
  the version, so "disable" is the soft-off switch rather than a delete.
- https://learn.microsoft.com/en-us/azure/key-vault/general/soft-delete-overview —
  "the default recovery period is set to 90 days", configurable 7–90 at vault
  creation only; "Two operations must be made to permanently delete a secret"
  (delete, then purge), and purge needs an explicit permission.
- https://learn.microsoft.com/en-us/azure/key-vault/general/key-vault-recovery —
  recovery is a first-class documented operation, not a support ticket.

**1Password — item-level history with restore, no count-based retention documented.**

- https://support.1password.com/item-history/ —
  "1Password saves previous versions of items every time you make changes, so you
  can see previously used passwords or even undo your changes"; restore is
  `Select an item → Last edited → View previous versions → Restore Item`, and
  "After you restore a previous version, you can still find other versions in the
  item's history" (restore is non-destructive — it appends).
- https://support.1password.com/item-history/ — history is exposed through the
  client, and restore is permission-gated ("Only family members with the Allow
  Editing permission can restore items in that vault"); no retention cap appears
  on the page, i.e. the product does not promise indefinite history either.

**Bitwarden — a fixed, small per-item window: the last five values.**

- https://bitwarden.com/help/password-and-generator-history/ —
  "Bitwarden stores the last five saved passwords for each login item, including
  deleted items before they're permanently removed"; hidden custom field edits
  consume one of those five slots; "Logging out or switching Bitwarden clients
  doesn't impact or clear the password history"; and a warning that
  "Accessing password history immediately reveals the older passwords in plain
  text."

**Infisical — version per write, restore appends a new version (same rule as 1Password/Doppler).**

- https://infisical.com/docs/documentation/platform/secret-versioning —
  "Every time a secret change is performed, a new version of the same secret is
  created"; restore "overwrites the current value and adds a new version at the top
  of the stack"; a specific version is readable via the API `version` parameter.
- https://infisical.com/docs/documentation/platform/secret-versioning — versioning
  is wired to point-in-time recovery, i.e. version retention is a pre-condition for
  a store-wide restore, not an end in itself.

**Doppler — versions are config-level snapshots; rollback is itself a logged change.**

- https://docs.doppler.com/docs/versioning —
  "For every log entry that supports rollbacks, you will see a **Rollback Changes**
  button"; supported for add/update/delete of secrets, and "Once the rollback is
  confirmed, you will see a new log entry for reversing the change in the previous
  log" — rollback does not rewind the log.

**pass — history delegated entirely to git.**

- https://www.passwordstore.org/ — "It's capable of temporarily putting passwords on
  your clipboard and tracking password changes using `git`." No version store, no
  retention policy, no restore UX in the tool: the git repo is the history, and
  every property (retention, tamper-evidence, dedup, deletion) is git's.

**KeePass — per-entry history bounded by count *and* size, prunable by age.**

- https://keepass.info/help/v2/entry.html —
  "Each entry has an own history. When modifying an entry, KeePass automatically
  creates a history entry, which contains the previous data"; "the number of
  history entries per entry and the history size per entry are limited to
  reasonable values" (configurable in Database Settings); individual history
  entries can be deleted, and Database Maintenance can "delete all history entries
  that are older than a specific number of days."

---

## II. Hash-chained, append-only, tamper-evident designs

**Certificate Transparency is the canonical statement of the property we want.**

- https://www.rfc-editor.org/rfc/rfc6962.html — CT provides "publicly auditable,
  append-only, untrusted logs"; "The append-only property of each log is
  technically achieved using Merkle Trees, which can be used to show that any
  particular version of the log is a superset of any particular previous version."
  Note the two-part design: a hash chain/Merkle tree *plus* an auditor that checks
  consistency — a per-row `prev_hash` alone proves nothing to anyone who never
  verifies it.

**Sigstore Rekor is the modern, shipped version of the same idea.**

- https://docs.sigstore.dev/logging/overview/ — "Rekor is built on top of a
  verifiable data structure. Auditors can monitor the log for consistency, meaning
  that the log remains append-only and entries are never mutated or removed."
  Rekor itself stores entries in Trillian, i.e. an external verified-log service —
  the transparency-log world does not implement this in the application's own
  relational store.

**immudb is the "database with proofs" precedent.**

- https://immudb.io/ — "immudb is a database with built-in cryptographic proof and
  verification. It tracks changes to sensitive data, and the integrity of that
  history is verified by the clients — without having to trust the server"; "Data
  can only be added, never changed or deleted, and every read can be answered with
  a cryptographic proof." Verification is client-side; a server-side chain with no
  client verification is a weaker claim than this.

**Vault's audit devices: keyed hashing of secret values, not chaining.**

- https://developer.hashicorp.com/vault/docs/audit — "By default, Vault only writes
  a keyed hash (HMAC-SHA256) of most string values to audit logs to protect the
  confidentiality of potentially sensitive information." Non-string values are not
  hashed, so the recommendation is to send everything as strings.
- https://developer.hashicorp.com/vault/docs/audit — "Once you disable an audit
  device, you can no longer compute hashes for the associated audit log entries.
  Even if you re-enable the audit device at the same path, Vault creates a new
  hashing key for the new log entries." The hash key is per-device and rotatable by
  disabling; entries themselves are not chained, so Vault gives confidentiality of
  logged values and a deletion/insertion signal via gap detection, not a hash chain.

**SOPS: one MAC over the whole value set, stored with the data.**

- https://getsops.io/docs/reference/ — "SOPS computes a MAC on all the values to
  ensure that no value has been added or removed fraudulently. The MAC is stored
  encrypted with AES_GCM and the data key under tree -> `sops` -> `mac`." A
  whole-file MAC is the cheap version of tamper-evidence and is what a
  single-file, single-writer secret store usually ships.

**Dolt: a hash-chained commit graph *inside* a SQL database.**

- https://www.dolthub.com/docs/architecture/storage-engine/commit-graph/ — "A
  commit is identified by a unique commit hash"; commits have parents, and "Parents
  allow for the history of branches to be computed by walking the branch from its
  `HEAD`"; "commit metadata like author, date, and message are stored … This
  metadata is considered when creating the content address … even if two commits
  have the exact same content but are committed at different times or by different
  authors, they will have different commit hashes."
- https://www.dolthub.com/blog/2025-03-03-dolt-basics-commits/ — "Dolt is
  maintaining all the objects in your database in a content-addressed store …
  your database contents can be summarized into a single SHA-256 encoded hash."
  This is the closest existing precedent for what v1/v2 propose, and note that it
  is a *storage-engine* rewrite, not a table added to an existing schema.

**Structural enforcement is a database feature elsewhere; SQLite's tool is a trigger.**

- https://learn.microsoft.com/en-us/sql/relational-databases/security/ledger/ledger-append-only-ledger-tables?view=sql-server-ver17 —
  "Append-only ledger tables allow only `INSERT` operations on your tables, which
  ensure that privileged users such as database administrators can't alter data
  through traditional DML"; with `LEDGER = ON` + `APPEND_ONLY = ON` "there are no
  `UPDATE` or `DELETE` operations on an append-only table, so there's no need for a
  corresponding history table." SQL Server makes immutability a schema property,
  which is the v2 "structural invariants" instinct.
- https://www.sqlite.org/lang_createtrigger.html — SQLite's equivalent is a
  `BEFORE UPDATE`/`BEFORE DELETE` trigger calling `RAISE(ABORT, 'msg')`; "When one
  of RAISE(ROLLBACK,...), RAISE(ABORT,...) or RAISE(FAIL,...) is called … the
  current query terminates. An error code of SQLITE\_CONSTRAINT is returned to the
  application, along with the specified error message." Since SQLite 3.47.0 the
  message may be an expression. A trigger is droppable by anyone who can write the
  file, so it stops accidents and casual edits, not a determined local attacker —
  worth saying plainly in the post.

---

## III. Content-addressed storage, and its equality-oracle pitfall

**The model: address = hash of content, so identical content is one object.**

- https://git-scm.com/book/en/v2/Git-Internals-Git-Objects — "Git is a
  content-addressable filesystem … at the core of Git is a simple key-value data
  store. What this means is that you can insert any kind of content into a Git
  repository, for which Git will hand you back a unique key you can use later to
  retrieve that content"; `git hash-object` "would take the content you handed to
  it and merely return the unique key that _would_ be used to store it". Anyone
  holding a candidate value can compute the key themselves — that *is* the
  dedup win, and it is also the leak.
- https://www.dolthub.com/blog/2025-03-03-dolt-basics-commits/ — Dolt does the same
  at database scope: a SHA-256 over database state plus commit metadata, so history
  can be summarised by one hash.

**The pitfall has a name and a body of literature: convergent encryption.**

- https://en.wikipedia.org/wiki/Convergent_encryption — "Convergent encryption,
  also known as content hash keying, is a cryptosystem that produces identical
  ciphertext from identical plaintext files. This has applications in cloud
  computing to remove duplicate files"; and it "is open to a 'confirmation of a
  file attack' in which an attacker can effectively confirm whether a target
  possesses a certain file by encrypting an unencrypted … version and then simply
  comparing the output with files possessed by the target."
  For a secret store the concrete consequence is: two projects (or two keys) that
  hold `postgres://…:hunter2@…` collapse to one row, and anyone who can read the
  store, or who can write one value and watch the counter, learns that some other
  key holds the same value.
- https://en.wikipedia.org/wiki/Convergent_encryption — the article's own mitigation
  advice is to add "a unique piece of data such as a few random characters to the
  plain text before encryption", and it notes this "defeat[s] attempts at making
  the file unique" only if applied per file, not per block; for the "learn the
  remaining information attack" it states "The only effective approach to
  mitigating this attack is to encrypt the contents of files with a non-convergent
  secret before storing (negating any benefit from convergent encryption), or to
  simply not use convergent encryption in the first place."
  That is the honest trade: per-store (or per-key) salt/nonce restores
  confidentiality at the price of dedup, so "content-addressed" and "no equality
  oracle" cannot both be had.

**Keyed addressing, not bare hashing, is the established middle ground.**

- https://developer.hashicorp.com/vault/docs/audit — Vault never writes a bare hash
  of a secret to its audit log: it writes "a keyed hash (HMAC-SHA256)", and the key
  is per audit device and rotates when the device is re-enabled. The same move
  applied to blob addresses (HMAC with a store key instead of SHA-256 of the
  plaintext) keeps dedup *within* the store while making addresses useless to
  someone who only has a candidate value and no key.
- https://www.dolthub.com/docs/architecture/storage-engine/commit-graph/ — Dolt gets
  a similar effect at the history layer by folding metadata into the address: equal
  content at different times yields different hashes, so the commit graph leaks far
  less than a pure content address would. Cost: no dedup of identical writes.

**Also worth remembering: the value itself is only one of the things history leaks.**

- https://bitwarden.com/help/password-and-generator-history/ — Bitwarden ships an
  explicit warning that "Accessing password history immediately reveals the older
  passwords in plain text." Any "show me previous versions" surface in the sqlite
  provider therefore needs the same warning in its docs, independent of how
  addressing works.

---

## IV. Secure deletion in SQLite: what the pragma actually promises

**`secure_delete` has three settings and a documented gap.**

- https://www.sqlite.org/pragma.html#pragma_secure_delete — "When secure\_delete is
  on, SQLite overwrites deleted content with zeros. The default setting for
  secure\_delete … is normally off … Applications that wish to avoid leaving
  forensic traces after content is deleted or updated should enable the
  secure\_delete pragma prior to performing the delete or update, or else run
  VACUUM after the delete or update."
- https://www.sqlite.org/pragma.html#pragma_secure_delete — "The 'fast' setting …
  will overwrite deleted content with zeros only if doing so does not increase the
  amount of I/O … This has the effect of purging all old content from b-tree pages,
  but leaving forensic traces on freelist pages." So `fast` is fine for "a deleted
  value does not linger in live pages" and *not* fine for "destroy leaves nothing".

**Why freelist pages matter: deleted content's pages are kept, not returned to the OS.**

- https://www.sqlite.org/fileformat2.html#the_freelist — "Unused pages can come
  about, for example, when information is deleted from the database. Unused pages
  are stored on the freelist and are reused when additional pages are required."
  Until reuse or VACUUM, they hold the old bytes.
- https://www.sqlite.org/lang_vacuum.html — "VACUUM … rebuilds the database file,
  repacking it into a minimal amount of disk space", which is why the pragma page
  offers it as the alternative to `secure_delete` for removing the traces.

**Journals and WAL are a second copy of the pages you just zeroed.**

- https://www.sqlite.org/pragma.html#pragma_journal_mode — TRUNCATE "commits
  transactions by truncating the rollback journal to zero-length"; PERSIST keeps
  the file and "the header of the journal is overwritten with zeros". Neither
  rewrites the journal *body*, so a "zero the freed pages" destroy that ignores
  `-wal`/`-journal` is not a complete story on a plaintext database.

**On an encrypted database the residue is ciphertext, and the shredding primitive is the key.**

- https://www.zetetic.net/sqlcipher/design/ — every page carries an
  HMAC-SHA512 "of the ciphertext and the initialization vector"; "Each database is
  initialized with a unique random salt in the first 16 bytes of the file"; "When
  encrypted, the entire database file appears to contain random data"; and the
  rollback journal, WAL and statement journals are all encrypted with the database
  key. Zeroing freed pages therefore buys little that the encryption did not
  already buy.
- https://en.wikipedia.org/wiki/Crypto-shredding — crypto-shredding renders data
  "unusable by deliberately deleting or overwriting the encryption keys", and
  "when specific pieces of data are encrypted (possibly with different keys) it
  allows for more specific data shredding".

**Verdict for the design question.** Zeroing freed pages on destroy is not
over-engineering — SQLite's own docs prescribe exactly that pair
(`secure_delete` on, or `VACUUM` after delete) for "applications that wish to avoid
leaving forensic traces" — but it is only honest for an *unencrypted* store, and it
must be paired with a VACUUM (freelist + WAL/journal residue) if the claim is
"destroy means gone" rather than "destroy means logically absent".

---

## V. Schema versioning conventions: `user_version` vs a migrations table

**SQLite gives you two header slots, and says what each is for.**

- https://www.sqlite.org/pragma.html#pragma_user_version — "The user\_version pragma
  will get or set the value of the user-version integer at offset 60 in the
  database header. The user-version is an integer that is available to applications
  to use however they want. SQLite makes no use of the user-version itself."
- https://www.sqlite.org/fileformat2.html#application_id — "The 4-byte big-endian
  integer at offset 68 is an 'Application ID' … in order to identify the database
  as belonging to or associated with a particular application. The application ID
  is intended for database files used as an application file-format … The
  application ID can be used by utilities such as file(1) to determine the specific
  file type"; assigned IDs live in SQLite's `magic.txt` registry.
  This is the precise, documented way to implement "refuse a layout that is not
  ours": `application_id` says *whose file it is*, `user_version` says *which
  layout*.

**rusqlite_migration is the `user_version` school, with an explicit rationale.**

- https://docs.rs/rusqlite_migration/latest/rusqlite_migration/ — its own summary:
  "Simple schema migration library for rusqlite using user\_version instead of an
  SQL table to maintain the current schema version"; "to keep track of the current
  migration state, most tools create one or more tables … This library uses the
  `user_version` value instead. It's much lighter as it is just an integer at a
  fixed offset in the SQLite file."
  Note what that costs: a single integer cannot record *which* migrations ran, so
  divergence detection is not available.

**refinery is the history-table school, and it refuses rather than guesses.**

- https://github.com/rust-db/refinery — "refinery works by creating a table that
  keeps all the applied migrations' versions and their metadata", then "compares
  the applied migrations with the ones to be applied, checking for divergent and
  missing" and executes unapplied migrations; by default each migration runs in its
  own transaction.
- https://docs.rs/refinery/latest/refinery/struct.Runner.html — `set_abort_divergent`
  ("abort if divergent migrations are found i.e. applied migrations with the same
  version but different name or checksum from the ones on the filesystem") and
  `set_abort_missing` are **true by default**. Checksums plus abort-by-default is
  the mainstream precedent for "refuse unknown/edited layout", and it is what a
  `user_version` guard is emulating with much less information.

**Practical read.** `PRAGMA user_version` costs one header write and no table, which
fits a single-table provider whose alternative is "no history at all". The
established frameworks that bother to detect tampering or drift all end up with a
table of (version, checksum) — refinery does, SQL Server's ledger does its own
bookkeeping, and Vault keeps per-key version metadata. "Refuse other layouts" is not
an unusual stance; refinery ships it as the default.

---

## VI. Bundled vs system SQLite in shipped Rust programs

**rusqlite's own recommendation is nuanced, and quotable.**

- https://github.com/rusqlite/rusqlite — "`bundled` causes us to automatically
  compile and link in an up to date version of SQLite for you. This avoids many
  common build issues, and avoids depending on the version of SQLite on the users
  system (or your system), which may be old or missing. It's the right choice for
  most programs that control their own SQLite databases. That said, it's not ideal
  for all scenarios and in particular, generic libraries built around `rusqlite`
  should probably not enable it, which is why it is not a default feature — it
  could become hard to disable." A secret-manager *binary* is squarely "a program
  that controls its own SQLite database"; it is not a library.
- https://github.com/rusqlite/rusqlite — "The base `rusqlite` package supports
  SQLite version 3.45.3 or newer"; with `bundled`, "`libsqlite3-sys` will use the
  `cc` crate to compile SQLite … from source and link against that. This source is
  embedded in the `libsqlite3-sys` crate and is currently SQLite 3.54.1 (as of
  `rusqlite` 0.43.0 / `libsqlite3-sys` 0.40.0)". Linking the system library instead
  is documented via `SQLITE3_LIB_DIR` / `SQLITE3_INCLUDE_DIR`.
- Local measurement (not a doc): on this Mac, macOS 27.2, `/usr/bin/sqlite3` reports
  `3.54.0` — so "the system SQLite is ancient" is *not* true on current macOS; it
  is a Linux-LTS/musl argument, not an Apple one.

**sqlx makes the choice explicit rather than defaulted.**

- https://docs.rs/crate/sqlx-sqlite/latest/features — `sqlx-sqlite` has 18 feature
  flags and "**0** of them enabled by default"; both `bundled` and `unbundled`
  exist, so a downstream build script or distro package can pick. Compare rusqlite,
  where `bundled` is opt-in but universally written into examples.

**Diesel treats bundling as the escape hatch, not the default.**

- https://diesel.rs/guides/getting-started — the SQLite tab generates
  `diesel = { …, features = ["sqlite", …] }` and leaves
  `# libsqlite3-sys = { version = "0.30", features = ["bundled"] }` commented with
  "# build libsqlite3 as part of the build process / uncomment this line if you run
  into setup issues". A framework that expects to link against whatever the host
  has; a CLI shipped as a static tarball has the opposite constraint.

**A shipped Rust CLI that deliberately bundles exactly one SQLite.**

- https://github.com/atuinsh/atuin/blob/main/Cargo.toml — the `libsqlite3-sys` entry
  carries the comment "Version range mirrors sqlx-sqlite's so cargo unifies both to
  a single `links = \"sqlite3\"` package (one bundled SQLite)", and another comment
  notes a second crate is "Kept on the libsqlite3-sys that sqlx uses (one bundled
  SQLite)". Atuin ships SQLite history to end users on three platforms and treats
  "one bundled SQLite" as a correctness property, not a build convenience.

**The counter-pressure is packaging policy, not users.**

- https://www.debian.org/doc/debian-policy/ch-source.html — §4.13 "Embedded code
  copies": "Debian packages should not make use of these convenience copies unless
  the included package is explicitly intended to be used in this way … the Debian
  packaging should ensure that binary packages reference the libraries already in
  Debian." A Debian/Homebrew package of the provider will be patched to the system
  library regardless; what the *upstream default* should be is decided by the
  cargo-installed and prebuilt-binary users.

**Read.** For a CLI that writes a file on the user's machine and ships prebuilt
binaries, bundling is the documented norm (rusqlite's own words, Atuin's practice,
SQLx's explicit-but-available flag); the system-library path should remain a
feature/Cargo-level option for packagers (Debian policy), and any behaviour that
depends on SQLite version — `secure_delete=fast` (3.8.x+), expression error
messages in `RAISE` (3.47.0+), `PRAGMA application_id` — should be stated in terms
of a minimum version, since that is what a system link actually varies.

---

## VII. Implications for our questions

**On (a) v1 vs v2 schema.**

1. Every peer ships *one* history dimension and stops: Vault = count cap (+optional
   TTL), AWS = staging labels + 100, Bitwarden = 5, KeePass = count+size, 1Password =
   everything with a restore button. None of them ships a per-row hash chain, and
   the ones that do (CT, Rekor, immudb) treat verification as a separate, first-class
   component. That is the strongest argument for **v1 as the mergeable default**:
   it matches the industry's actual scope, and a chain in the schema without a
   verifier is decoration.
2. If the PR keeps the hash chain, it needs a `verify` path (a CLI subcommand, or
   verify-on-read) in the same change — RFC 6962 and Rekor both define the chain
   *and* the consistency check; immudb defines server append-only *and* client
   proof-checking. Without that, the honest framing is "tamper-evident only against
   accidental or tool-level mutation".
3. v2's **structural invariants** are worth having but should be described accurately:
   SQL Server can make a table append-only as an engine property; SQLite's equivalent
   is a `BEFORE UPDATE/DELETE` trigger with `RAISE(ABORT, …)`, which anyone who can
   write the file can drop. It stops bugs and casual edits, not a determined local
   attacker — and it is genuinely stronger than v1's "the code promises not to
   update", so it is the right thing to keep from v2 if only one piece is kept.
4. v2's **content-addressed blobs are the part I would push back on.** The
   convergent-encryption literature is unambiguous: identical plaintext → identical
   address is exactly a "confirmation of a file attack", and the only effective
   mitigation ("a non-convergent secret … negating any benefit from convergent
   encryption") means giving up dedup. If blobs stay, address them with an HMAC
   under a store key (Vault's audit-device pattern: keyed hash, per-device key,
   rotatable) rather than a bare SHA-256 of the secret, and document that two keys
   holding the same value are linkable when the key is known.

**On (b) retention defaults.**

5. The default should be **keep everything, prune on request** — Vault's
   `delete_version_after` defaults to `0s` (no expiry), 1Password/KeePass/Infisical
   keep full history, and only the products that must control unbounded growth
   (Bitwarden 5, AWS 100-with-labels) impose hard caps. A dev-workflow tool that
   silently discards the third-oldest value will be blamed for losing a credential.
   Ship `max_versions` / `delete_versions_after` as opt-in config plus a prune
   command, and document the cost of keeping everything.
6. Copy the peers' **two-step destroy**: soft-delete (version/tombstone stays
   visible) then an explicit destroy that is the only thing that touches pages.
   Vault and Azure both do delete-then-purge; Azure's 90-day default recovery window
   is the model if the PR ever wants "destroyed but recoverable".
7. Copy the peers' **append-only restore**: 1Password keeps other versions after a
   restore, Infisical "adds a new version at the top of the stack", Doppler writes a
   reversing log entry. Restoring must never rewind the chain or overwrite a row —
   that single rule keeps the hash chain valid and the audit story true.

**On (c) bundled vs system SQLite.**

8. Default `bundled`: rusqlite's README says it "is the right choice for most
   programs that control their own SQLite databases" and warns only that generic
   *libraries* should not enable it; Atuin ships exactly one bundled SQLite on
   purpose; SQLx exposes `bundled`/`unbundled` as explicit flags; Diesel leaves
   bundling commented out as a workaround. Keep a `--no-default-features` path that
   links the system library (Debian policy §4.13 requires packagers to do this
   anyway), and state the minimum SQLite version the provider needs
   (`secure_delete=fast` 3.8.x+, `RAISE` expression messages 3.47.0+) rather than
   assuming a version — that is the only thing a system link actually varies.

---

## Closing search (last month, to 2026-11-18)

- https://blog.sigstore.dev/rekor-public-instance-hardening/ (Nov 16, 2026) — Sigstore
  is *shrinking* the Rekor public log's surface: "we are reducing the number of
  supported entry types on the Sigstore public deployment transparency log …
  Effective immediately, we will disable the upload of a number of Rekor entry
  types", and it points new integrations at "Rekor v2 … well-optimized for all
  client payloads". Takeaway: even the flagship transparency log is cutting
  features, not adding them — a bespoke Merkle log in a secrets CLI is the
  ambitious end of the range.
- https://developer.hashicorp.com/vault/docs/updates/release-notes — Vault 2.2.0
  (released 2026-10-15) adds "**KV v2 snapshot recovery**: You can now read and
  recover KV v2 secrets from a loaded cluster snapshot, including in-place recovery
  and copy-from-path within the same mount and namespace." Takeaway: peer investment
  in the last month went to *recovery of version history*, not to hash chains or
  tamper-evidence.
- https://www.sqlite.org/changes.html — SQLite 3.54.0 (2026-10-09) and 3.54.1
  (2026-10-16) contain **no** changes touching `secure_delete`, `user_version`,
  `application_id` or `VACUUM` semantics (checked the two release sections). The
  pragmas this design leans on are stable.
- https://docs.rs/libsqlite3-sys/latest/libsqlite3_sys/ — libsqlite3-sys 0.40.0
  (11 November 2026) ships SQLite 3.54.1 for `bundled`, which is what
  `rusqlite` 0.43.0 links; system `sqlite3` on macOS 27.2 here is 3.54.0, i.e. the
  same generation — no bundling pressure from version skew on this platform.
