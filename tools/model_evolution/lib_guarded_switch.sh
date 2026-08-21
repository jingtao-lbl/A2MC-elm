#!/bin/bash
# =======================================================================================
# A2MC Model Evolution — guarded in-place branch-switch (sourceable library)
#
# A model-evolution V0-at-equality check needs a baseline build from a DIFFERENT commit
# than whatever the model checkout currently has checked out — but CIME compiles a
# component (ELM, FATES) from the ONE fixed in-tree path recorded at case-creation time;
# there is no per-case source override, and a `git worktree add` of the parent is never
# seen by the build (CIME resolves the real, non-worktree path). So the only way to build
# a same-env baseline is to switch the checkout itself, build, then switch back.
#
# This is exactly what a2mc_config.sh/CLAUDE.md's model-evolution skill (Step 5) documents
# as the guarded in-place branch-switch recipe: `trap restore EXIT` + `set -e` + a clean-tree
# hard gate + a "confirm-on-target" sanity check, wrapping whatever build command needs to
# run while switched.
#
# Usage (source this file, then call the function):
#   source tools/model_evolution/lib_guarded_switch.sh
#   guarded_switch_and_run <repo_path> <target_ref> <restore_ref> <verify_file> <verify_pattern> -- <cmd...>
#
# Arguments:
#   repo_path       Git checkout to switch — the E3SM root OR a submodule path
#                    (e.g. components/elm/src/external_models/fates). Must be a clean,
#                    committed checkout (untracked .ipynb_checkpoints/__pycache__ noise
#                    is tolerated; anything else aborts before touching the tree).
#   target_ref      Commit or branch to check out temporarily — the ref to BUILD from.
#   restore_ref     Branch to restore to on exit (normally whatever was checked out before
#                    calling — capture it with `git -C <repo_path> branch --show-current`
#                    before switching).
#   verify_file     Optional: a file to sanity-check after switching (pass "" to skip).
#   verify_pattern  Optional: an extended-regex pattern that must match in verify_file
#                    (pass "" to skip) — confirms the switch actually landed on the source
#                    state the caller expects, not just "some other ref."
#   cmd...          The command to run while switched (e.g. a case build). Restoration
#                    happens via `trap ... EXIT` regardless of whether cmd succeeds.
#
# Author: Jing Tao with Claude on Perlmutter
# =======================================================================================

guarded_switch_and_run() {
    local repo="$1" target="$2" restore="$3" vfile="$4" vpat="$5"
    shift 5

    if [ -z "$repo" ] || [ -z "$target" ] || [ -z "$restore" ]; then
        echo "ERROR: guarded_switch_and_run requires repo_path, target_ref, restore_ref" >&2
        return 1
    fi
    if [ ! -d "$repo/.git" ] && ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
        echo "ERROR: $repo is not a git checkout" >&2
        return 1
    fi

    # Clean-tree hard gate BEFORE touching anything — ignore known-benign untracked noise
    # (notebook checkpoints, __pycache__) so a normal working session doesn't false-positive.
    local dirty
    dirty="$(git -C "$repo" status --porcelain | grep -vE '\.ipynb_checkpoints|__pycache__')"
    if [ -n "$dirty" ]; then
        echo "ERROR: $repo has uncommitted changes — ABORT (would be silently mixed into the build)." >&2
        echo "$dirty" >&2
        return 1
    fi

    _gs_restore() {
        git -C "$repo" checkout "$restore" >/dev/null 2>&1
        echo "RESTORED $repo -> $(git -C "$repo" branch --show-current 2>/dev/null || git -C "$repo" rev-parse --short HEAD)"
    }
    trap _gs_restore EXIT
    set -e

    git -C "$repo" checkout "$target"
    echo "NOW ON: $repo @ $(git -C "$repo" rev-parse --short HEAD) (target_ref=$target)"

    if [ -n "$vfile" ] && [ -n "$vpat" ]; then
        if grep -qE "$vpat" "$vfile"; then
            echo "SANITY CHECK PASSED: '$vpat' found in $vfile"
        else
            echo "SANITY CHECK FAILED: '$vpat' NOT found in $vfile — this may not be the source state you expect." >&2
            return 1
        fi
    fi

    echo "RUNNING: $*"
    "$@"
}
