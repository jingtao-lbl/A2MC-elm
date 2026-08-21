#!/usr/bin/env bash
# setup_clone.sh — one-time per-clone setup for an A2MC clone.
#
# Git cannot carry these three things (they live outside the repo tree or are
# per-clone index flags), so every fresh clone / new machine needs them once.
# This script does all three, idempotently and safely (re-runnable):
#
#   1. Activate the repo's git hooks       (git config core.hooksPath .githooks)
#   2. Suppress chroma.sqlite3 read-churn   (git update-index --skip-worktree ...)
#   3. Wire the .claude_memory auto-memory bucket symlink (with backup)
#
# Step 3 only runs when this clone actually has a private .claude_memory/ bucket
# (so it is a no-op on a public clone or an adapter/demo clone with its own bucket).
#
# Usage:
#   scripts/setup_clone.sh              # do it
#   scripts/setup_clone.sh --dry-run    # preview, change nothing
#
# Rollback for step 3 is printed when it acts. Author: Jing Tao with Claude.

set -u

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# run a command, or just print it in --dry-run mode (no eval — safe with spaces)
do_or_echo() {
    if [ "$DRY" = 1 ]; then echo "    [dry-run] would run: $*"; else "$@"; fi
}

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: not inside a git repo." >&2; exit 1; }
cd "$ROOT" || exit 1

echo "== A2MC clone setup"
echo "   repo:   $ROOT"
echo "   branch: $(git branch --show-current 2>/dev/null)"
[ "$DRY" = 1 ] && echo "   MODE:   DRY-RUN (no changes will be made)"
echo

# ---------------------------------------------------------------- 1. git hooks
echo "[1/3] git hooks (core.hooksPath)"
CUR_HOOKS="$(git config --get core.hooksPath 2>/dev/null || true)"
if [ "$CUR_HOOKS" = ".githooks" ]; then
    echo "    already set: core.hooksPath = .githooks"
elif [ -d "$ROOT/.githooks" ]; then
    do_or_echo git config core.hooksPath .githooks
    echo "    set core.hooksPath = .githooks"
else
    echo "    skip: no .githooks/ directory in this repo"
fi
echo

# ---------------------------------------------------------------- 2. chroma skip-worktree
echo "[2/3] chroma.sqlite3 skip-worktree (RAG read-churn suppression)"
CHROMA="$(git ls-files rag/chroma_db 2>/dev/null | grep '/chroma\.sqlite3$' || true)"
if [ -z "$CHROMA" ]; then
    echo "    skip: no tracked chroma.sqlite3 files"
else
    for f in $CHROMA; do
        if git ls-files -v "$f" 2>/dev/null | grep -q '^S '; then
            echo "    already skip-worktree: $f"
        else
            do_or_echo git update-index --skip-worktree "$f"
            echo "    set skip-worktree: $f"
        fi
    done
    echo "    (to commit a rebuilt index later: git update-index --no-skip-worktree <file> first)"
fi
echo

# ---------------------------------------------------------------- 3. .claude_memory symlink
echo "[3/3] .claude_memory auto-memory bucket symlink"
if [ ! -d "$ROOT/.claude_memory" ]; then
    echo "    skip: no .claude_memory/ in this repo (public clone, or a clone without a private bucket)"
else
    # The harness reads memory from ~/.claude/projects/<cwd-key>/memory, where
    # <cwd-key> is the repo's absolute path with every '/' replaced by '-'.
    KEY="$(printf '%s' "$ROOT" | sed 's#/#-#g')"
    BUCKET="$HOME/.claude/projects/$KEY/memory"

    # If the derived bucket does not exist, a prior session may have used a
    # different path alias — try to discover an existing bucket for this repo.
    if [ ! -e "$BUCKET" ] && [ ! -L "$BUCKET" ]; then
        BASE="$(basename "$ROOT")"
        FOUND="$(find "$HOME/.claude/projects" -maxdepth 2 -type d -name memory -path "*${BASE}*" 2>/dev/null | head -1)"
        [ -n "$FOUND" ] && { echo "    note: derived path absent; using discovered bucket $FOUND"; BUCKET="$FOUND"; }
    fi

    if [ -L "$BUCKET" ]; then
        echo "    already symlinked: $BUCKET -> $(readlink "$BUCKET")"
    elif [ -d "$BUCKET" ]; then
        echo "    existing real bucket: $BUCKET"
        echo "    machine-only memories (present here but NOT in the repo) — review before they're shadowed:"
        ONLY="$(diff -rq "$BUCKET" "$ROOT/.claude_memory" 2>/dev/null | grep "^Only in $BUCKET" || true)"
        if [ -n "$ONLY" ]; then echo "$ONLY" | sed 's/^/      /'; echo "      ^ copy any you want to keep into $ROOT/.claude_memory (then commit) BEFORE proceeding."; else echo "      (none)"; fi
        do_or_echo mv "$BUCKET" "$BUCKET.pre-symlink-bak"
        do_or_echo ln -s "$ROOT/.claude_memory" "$BUCKET"
        echo "    backed up -> $BUCKET.pre-symlink-bak"
        echo "    symlinked  -> $ROOT/.claude_memory"
        echo "    ROLLBACK:  rm \"$BUCKET\" && mv \"$BUCKET.pre-symlink-bak\" \"$BUCKET\""
    else
        # no bucket yet (fresh clone, no session has run here)
        do_or_echo mkdir -p "$(dirname "$BUCKET")"
        do_or_echo ln -s "$ROOT/.claude_memory" "$BUCKET"
        echo "    created symlink: $BUCKET -> $ROOT/.claude_memory"
    fi

    if [ "$DRY" = 0 ] && [ -e "$BUCKET/MEMORY.md" ]; then
        echo "    verify: $(head -1 "$BUCKET/MEMORY.md")"
    fi
fi
echo
echo "== done.$([ "$DRY" = 1 ] && echo ' (dry-run — nothing changed)')"
