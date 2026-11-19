#!/usr/bin/env python3
"""Exercise scripts/github-ci-run's ci/base selection against a throwaway repo.

The trap this covers (2026-11-18): a stale local ci/base silently builds an old
workflow, which reads as "CI failed for a reason unrelated to your change".
Four states, each asserted on what the overlay actually contains:

    equal     local == remote          -> local, no warning
    behind    local ancestor of remote -> REMOTE, warning naming the fetch
    ahead     remote ancestor of local -> local (deliberate local work)
    diverged  neither is an ancestor   -> exit 2, nothing pushed

Usage: python3 scripts/github-ci-run.test.py [--keep]
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "github-ci-run"


def run(argv, cwd, check=True, env=None):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        sys.exit(
            f"harness: {' '.join(argv)} failed ({result.returncode})\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


def git(cwd, *args, check=True):
    return run(["git", *args], cwd, check=check)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def commit(repo, message):
    git(repo, "add", "-A")
    git(
        repo,
        "-c", "user.name=harness",
        "-c", "user.email=harness@example.invalid",
        "commit", "-q", "-m", message,
    )
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def workflow(repo, marker):
    write(repo / ".github/workflows/linux-ci.yml", f"name: harness\nmarker: {marker}\n")


def build(root):
    """A bare remote plus a working clone; ci/base carries a marked workflow."""
    remote = root / "remote.git"
    work = root / "work"
    git(root, "init", "-q", "--bare", "-b", "main", str(remote))
    git(root, "init", "-q", "-b", "main", str(work))
    git(work, "remote", "add", "origin", str(remote))

    write(work / "README.md", "harness\n")
    commit(work, "base")

    git(work, "checkout", "-q", "-b", "ci/base")
    workflow(work, "one")
    write(work / "docs/ci-github.md", "harness ci doc\n")
    (work / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, work / "scripts/github-ci-run")
    commit(work, "ci/base: one")

    git(work, "checkout", "-q", "main")
    write(work / "src.txt", "target\n")
    commit(work, "target")

    git(work, "push", "-q", "origin", "main", "ci/base")
    git(work, "fetch", "-q", "origin")
    return remote, work


def overlay_branch(work):
    short = git(work, "rev-parse", "--short=8", "HEAD").stdout.strip()
    return f"ci/run/HEAD-{short}"


def overlay_marker(remote, branch):
    """The marker the pushed overlay carries, or None if it was not pushed."""
    if git(remote, "rev-parse", "--verify", branch, check=False).returncode != 0:
        return None
    blob = git(remote, "show", f"{branch}:.github/workflows/linux-ci.yml", check=False)
    if blob.returncode != 0:
        return "missing"
    for line in blob.stdout.splitlines():
        if line.startswith("marker:"):
            return line.split(":", 1)[1].strip()
    return "unmarked"


def advance_remote(work, marker):
    """Add a commit on top of the REMOTE ci/base, publish it, return to main.

    Built from the remote tip, not the local branch, so the two can be made to
    diverge deliberately.
    """
    git(work, "checkout", "-q", "-B", "remote-side", "refs/remotes/origin/ci/base")
    workflow(work, marker)
    commit(work, f"remote ci/base: {marker}")
    git(work, "push", "-q", "origin", "remote-side:ci/base")
    git(work, "fetch", "-q", "origin")
    git(work, "checkout", "-q", "main")


def advance_local(work, marker):
    """Add a commit on top of the LOCAL ci/base, return to main.

    The local branch is fast-forwarded to the remote tip first, so "ahead" means
    a superset of the remote (work committed on top of a refreshed ci/base)
    rather than an accidental divergence.
    """
    git(work, "checkout", "-q", "ci/base")
    git(work, "merge", "-q", "--ff-only", "refs/remotes/origin/ci/base", check=False)
    workflow(work, marker)
    commit(work, f"local ci/base: {marker}")
    git(work, "checkout", "-q", "main")


def overlay(work, remote):
    """Run the script for the target commit and return (result, marker)."""
    branch = overlay_branch(work)
    result = run(
        ["bash", str(SCRIPT), "--no-wait", "HEAD"],
        work,
        check=False,
        env={**os.environ, "GITHUB_CI_REMOTE": "origin"},
    )
    return result, overlay_marker(remote, branch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="keep the scratch repo")
    args = parser.parse_args()

    root = Path(tempfile.mkdtemp(prefix="github-ci-run-test-"))
    failures = []

    def check(name, condition, detail=""):
        print(f"  {'ok' if condition else 'FAIL':4} {name}" + ("" if condition else f" — {detail}"))
        if not condition:
            failures.append(name)

    try:
        remote, work = build(root)

        print("equal: local == remote")
        result, marker = overlay(work, remote)
        check("uses the ci/base content", marker == "one", f"marker={marker}")
        check("no staleness warning", "is behind" not in result.stderr, result.stderr.strip())

        print("behind: local is an ancestor of remote")
        advance_remote(work, "two")
        result, marker = overlay(work, remote)
        check("uses the REMOTE content", marker == "two", f"marker={marker}")
        check(
            "warns and names the fetch",
            "is behind" in result.stderr and "git fetch" in result.stderr,
            result.stderr.strip(),
        )

        print("ahead: remote is an ancestor of local")
        advance_local(work, "three")
        result, marker = overlay(work, remote)
        check("keeps the local content", marker == "three", f"marker={marker}")
        check("no warning", "is behind" not in result.stderr, result.stderr.strip())

        print("diverged: neither is an ancestor")
        # Branch the local side off the remote tip's parent so the two share no
        # tip: advance_remote() then moves the remote past it independently.
        git(work, "checkout", "-q", "-B", "ci/base", "refs/remotes/origin/ci/base~1")
        workflow(work, "local-only")
        commit(work, "local ci/base: local-only")
        git(work, "checkout", "-q", "main")
        advance_remote(work, "remote-only")
        branch = overlay_branch(work)
        before = overlay_marker(remote, branch)
        result, marker = overlay(work, remote)
        check("refuses with exit 2", result.returncode == 2, f"rc={result.returncode}")
        check("says it diverged", "diverged" in result.stderr, result.stderr.strip())
        check("pushes nothing", marker == before, f"marker={marker} before={before}")
    finally:
        if args.keep:
            print(f"kept: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
