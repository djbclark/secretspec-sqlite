# GitHub Linux CI (ci/base)

Linux cargo CI for this fork runs on free GitHub-hosted runners via the
`ci/base` + `ci/run/**` overlay pattern (not on the default branch).

1. Workflow: `.github/workflows/linux-ci.yml` on branch `ci/base`
2. Wrapper: `scripts/github-ci-run [REF]` — builds a commit = REF's tree + the
   `ci/base` overlay (and deletes every other `.github/workflows/*` file),
   force-pushes it to `ci/run/<slug>-<sha8>`, and watches the Actions run.
3. Invocation: from a checkout, `scripts/github-ci-run` or
   `scripts/github-ci-run --no-wait HEAD`.
4. The private Forgejo duplicate (`forgejo.mit.edu/djbclark/secretspec-sqlite`)
   remains until the GitHub path is confirmed; do not delete it from here.
