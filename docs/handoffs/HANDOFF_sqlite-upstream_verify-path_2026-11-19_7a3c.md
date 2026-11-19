---
schema_version: 1
handoff_id: 7a3c
parent_handoff_ids: []
lineage: deterministic
chain: [sqlite-upstream]
repo: secretspec-sqlite
workspace: main
branch: main
head_sha: 58d6f8c7
created_at: 2026-11-19T11:25:00Z
writer: pi
---
# Handoff — sqlite provider upstreamed: rebase, verify path, and the questions to domenkozar

## The Goal

Get the `sqlite://` provider (with its opt-in hash-chained history ledger) into
`cachix/secretspec` as PR [#487](https://github.com/cachix/secretspec/pull/487),
and keep the downstream fork `frdminc/sudo-secretspec` in step with upstream.
Two secondary goals that came out of it: make the ledger's chain checkable
(a chain nobody can verify is decoration), and stop the fork's overlay CI from
being red for reasons unrelated to any change.

## Where We Are

- **PR #487 head is `ff442ce1`** on branch `sqlite-provider`, rebased onto
  upstream `main` @ `4e12489a` (which includes #552, redaction streams), and
  GitHub reports it **MERGEABLE**. `sqlite-provider-rebased` points at the same
  commit.
- **CI on that exact commit is running**:
  [44506181907](https://github.com/djbclark/secretspec-sqlite/actions/runs/44506181907)
  (overlay branch `ci/run/origin-sqlite-provider-ff442ce1`). CI was **green** on
  the previous head `c70b67aa` ([44356193202](https://github.com/djbclark/secretspec-sqlite/actions/runs/44356193202)),
  which differs only by upstream #552 and a CHANGELOG merge.
- **An earlier run of the same overlay hung** in `Run tests` for ~50 minutes
  where the same step took 6 minutes on the prior commit. It was cancelled, not
  diagnosed; the re-run above is the test of whether it was flake or real.
- **Fork `main` is `58d6f8c7`**, carrying `upstream/PEER-PRACTICE-2026-11.md`
  (the 33 KB peer-practice review) next to the existing submission artifacts.
- **`ci/base` is `5fe53c57`**: it now installs yyjson before any cargo step,
  checks the same 23 provider features upstream does (incl. `sqlite`), and its
  runner refuses a stale local `ci/base` instead of silently building an old
  workflow, pinned by `scripts/github-ci-run.test.py` (8 checks).
- Working tree: only another session's ` M .gitignore` and `?? .ignore` — not
  ours, left alone. No worktrees, no stale branches, no scratch artifacts.

## What We Tried

- **Hypothesis: the `[providers]` alias dropped `?history=true`.** Wrong. A
  diagnostic CI run showed the database *did* contain `CREATE TABLE entries`.
  The real cause was the decorators (below). Cost: two CI rounds. Lesson: put
  the diagnostic in the failing test and let CI answer, rather than reasoning
  from the CLI output.
- **Conflict resolution by taking the "parent" side of a diff3 hunk** dropped
  both CHANGELOG entries. Caught by reading the resolved file; redone by
  inserting both entries explicitly.
- **Tamper tests blocked by the ledger's own guards.** `captured_values.sequence
  REFERENCES entries(sequence)` plus a `BEFORE DELETE` trigger refused the
  test's `DELETE`. Fixed by defeating the guards the way a tamperer would
  (`PRAGMA foreign_keys = OFF`, drop the trigger, delete dependents first) —
  which is also evidence the guards work.
- **First push of the repointed head used `sqlite-provider-rebased` as a source
  ref** the shared checkout did not have, then a `FETCH_HEAD` refspec GitHub
  rejected. The working form: push the explicit sha with a full
  `refs/heads/…` lease.
- **My earlier absence check for the deletion-preflight fix grepped
  `provider/mod.rs`**, which upstream had split; the fix had been upstream since
  `04d3fa66`. That cost a whole dispatched slice, which correctly refuted me.

## Key Decisions

- **The "v1 vs v2 schema" question was withdrawn.** An earlier PR comment
  claimed the PR shipped a simpler layout than downstream; it does not — the
  branch already has `value_blobs` keyed by `(item, value_sha256)`,
  `AUTOINCREMENT` blob ids, a generated `live_blob_id` with `ON DELETE RESTRICT`,
  and `user_version` 2. The comment was corrected on the PR.
- **Verify is Shape A**: a defaulted `Provider::verify_history()` plus one
  provider-agnostic `secretspec verify-history` command, read-only, value-free.
- **Retention stays unimplemented** until domenkozar answers; it is the one place
  a wrong default silently destroys data.
- **The `TEXT`-cell tolerance is offered for removal** (it only serves databases
  the downstream fork created) and awaits his word.
- **The decorator trap is filed, not fixed**, as
  [#554](https://github.com/cachix/secretspec/issues/554) with three ranked
  routes; the completeness test is recommended.
- **Rejected:** a sqlite-only verify command (puts a provider name in the CLI
  surface); a bare `pub fn` (provider module is private, reaches nobody);
  content-addressed blobs keyed by digest alone (equality oracle across names,
  and destroy-by-name has no correct answer).

## Decisions

- [decision] verify path is a defaulted trait method plus one provider-agnostic command; rejected: sqlite-only command, bare pub fn; because a provider-agnostic capability is the only shape another provider can grow, and the module is private; in [PR 487](https://github.com/cachix/secretspec/pull/487).
- [decision] retention deferred to the maintainer; rejected: shipping an opt-in cap now; because a wrong default silently discards a credential, which is the failure the feature exists to prevent; in [PR 487](https://github.com/cachix/secretspec/pull/487).
- [decision] decorator forwarding bug filed as an issue with three ranked fixes; rejected: fixing the class inside the provider PR; because it is core plumbing and the maintainer may want a different shape; in [issue 554](https://github.com/cachix/secretspec/issues/554).
- [ruling] "1 plus link to it from 2" — commit the research report to the fork's upstream/ and link it from the issue comment (djbclark, 2026-11-19).
- [ruling] "Make new TL;DR comments on anything that needs input from domenkozar explaining exactly the feedback requested, giving context for the decision, ramifications, and your recommendations and alternatives" (djbclark, 2026-11-19).

## Relations

- decided_in [[HANDOFF_sqlite-upstream_verify-path_2026-11-19_7a3c]]

## Evidence & Data

- Chain format: `compute_entry_hash(previous_hash, entry)` hashes a canonical
  rendering of `(sequence, timestamp_ns, operation, [(item, value_sha256)…])`;
  `capture_history` appends inside the caller's transaction.
- Ledger tables: `entries`, `captured_values` (`sequence REFERENCES
  entries(sequence)`), `value_blobs`, `head`; `SCHEMA_VERSION = 2`.
- Trait/decorator sizes: `Provider` has 45 methods, 40 defaulted;
  `RetryingProvider` forwards 46, `PreflightGuard` 48 — hand-maintained lists,
  which is the trap in #554.
- `verify_history` failure vocabulary: `missing_entry`,
  `previous_hash_mismatch`, `entry_hash_mismatch`, `head_mismatch`,
  `schema_version_mismatch`.
- CI run ids: green `44356193202` (c70b67aa), hung-then-cancelled `44505334860`,
  current `44506181907` (ff442ce1).
- Green CI at `5fe53c57` proves the ci/base fix: 8/8 harness checks locally,
  full workspace suite in the overlay.

## Operator Feedback

- Chose: build the verify path pre-emptively; repoint the PR head now; wait on
  retention; file the decorator issue; identify the stray PR comment before
  acting; fix the `ci/base` script rather than document it; commit the research
  report and link it; handoff and continue (this document).
- Recurring correction he cares about: backticks inside double-quoted shell
  strings executed twice this session (mangled an issue comment and a commit
  message, both repaired). Use a file (`--body-file`, `-F`) or a heredoc.

## Where We're Going

1. **Read CI run [44506181907](https://github.com/djbclark/secretspec-sqlite/actions/runs/44506181907).**
   If green, post nothing (the thread already says the head is current) and stop.
   If red, read the failing step's log; the last two failures were the tamper-test
   guards (fixed) and a rustfmt nit (fixed); a third repeat means a real defect in
   the rebase onto #552, not flake.
2. **When domenkozar answers** ([TL;DR comment](https://github.com/cachix/secretspec/pull/487#issuecomment-7006500303)):
   apply it — most likely drop the `TEXT`-cell tolerance (one commit, `git
   revert`-able), keep or change the verify shape, and start retention as a
   follow-up PR against `sqlite-provider-rebased`.
3. **If he asks for a different verify shape**: Shape B is a sqlite-only command
   (delete the trait method and the `Arc`/`RetryingProvider`/`PreflightGuard`
   forwards, keep `verify_ledger`); Shape C is `pub fn` only (drop the CLI).
4. **Do not** merge upstream `main` into `sudo-main` without the operator's
   word; the 0.22 plan is recorded in frdminc/sudo-secretspec#11.

## Detached jobs

none

## Quick Start

```bash
cd ~/src/secretspec-sqlite
git fetch origin sqlite-provider && git log --oneline -1 origin/sqlite-provider   # expect ff442ce1
gh pr view 487 --repo cachix/secretspec --json mergeable,mergeStateStatus,headRefOid
gh run list --repo djbclark/secretspec-sqlite --branch ci/run/origin-sqlite-provider-ff442ce1 \
  --limit 1 --json status,conclusion,url
gh pr view 487 --repo cachix/secretspec --comments   # the TL;DR is the last comment
```

To re-run CI after a change (never local cargo here — this repo is CI-first):

```bash
cd ~/src/secretspec-sqlite && bash scripts/github-ci-run --no-wait origin/sqlite-provider
```

To change the PR head:

```bash
git worktree add -b pr-head /Users/djbclark/src/ssq-pr-wt origin/sqlite-provider
# edit, commit with git-commit-own, then:
git push --force-with-lease=refs/heads/sqlite-provider:<old-sha> origin <new-sha>:refs/heads/sqlite-provider
```
