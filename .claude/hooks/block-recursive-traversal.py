#!/usr/bin/env python3
"""PreToolUse(Bash) hook — enforce NERSC's "no recursive traversal of shared paths" rule.

The read-side sibling of `block-forbidden-writes.py`. NERSC issued a formal "Improper Use of
AI Agents on Shared Systems" warning (account suspension on repeat) after unbounded
`grep -r`/`find` calls against a model checkout on the CFS project store, then supplied a
required "## Filesystem discovery" block now reproduced verbatim in `~/.claude/CLAUDE.md`.
Its fifth bullet says not to bypass "an installed filesystem-traversal hook" — this is it.

Policy implemented (deliberately narrower than "block all recursion", so the hook stays
usable and nobody is tempted to disable it, which NERSC also forbids):

  1. A traversal rooted AT a shared top-level (`/`, `/global`, `/global/cfs`, `/pscratch`,
     `/usr`, ...) is DENIED outright. No depth flag rescues it — NERSC says "never".
  2. A traversal rooted DEEPER under a shared mount (a project or user dir) is allowed only
     with an explicit depth bound (`-maxdepth`, `--max-depth`, `-L`). Without one, denied
     with the bounded form suggested.
  3. Anything not naming an absolute shared path (relative paths, the workspace, `./tmp`) is
     ALLOWED — NERSC explicitly permits "a bounded root inside the current workspace".
  4. `git grep` / `git ls-files` are always allowed: index-based, not filesystem walks.

Limit: this reads the shell command text. It cannot see a traversal performed inside a
program it merely launches (`python foo.py` calling `os.walk('/global')`) unless the
traversal appears in the command line itself, which the inline-python patterns do catch.

Schema: reads the tool-call JSON on stdin; denies via
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", ...}}.
See ~/.claude/CLAUDE.md and .claude_memory/feedback_nersc_no_recursive_traversal.md.
"""
import sys, json, re, shlex, os

# ---------------------------------------------------------------------------
# ACTIVATION — this guard is for SHARED HPC FILESYSTEMS ONLY.
# ---------------------------------------------------------------------------
# `/usr`, `/opt`, `/etc`, `/var` are in NERSC's prohibited list AND are ordinary local system
# directories on a laptop -- Homebrew lives at `/opt/homebrew` or `/usr/local`. Without this
# gate the hook denies `find /usr/local/lib -name '*.dylib'` on a Mac, where there is no shared
# filesystem, no allocation and no AUP in play. Worse, `.claude/hooks/` and `.claude/settings.json`
# are on the public-sync INCLUDE list, so an ungated version would ship a NERSC-specific
# prohibition to every A2MC user and break searches on their own machines.
#
# `A2MC_TRAVERSAL_GUARD` overrides the autodetect: `on` (force -- use this at an HPC site whose
# markers are not listed below), `off` (disable), unset/anything else = autodetect.
_HPC_MARKER_DIRS = ("/global/cfs", "/global/homes", "/pscratch")
_HPC_MARKER_ENV = ("NERSC_HOST", "LMOD_SYSHOST", "CRAYPE_DIR", "SLURM_CLUSTER_NAME")


def guard_active():
    mode = os.environ.get("A2MC_TRAVERSAL_GUARD", "").strip().lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    if any(os.environ.get(v) for v in _HPC_MARKER_ENV):
        return True
    # os.path.isdir is a single stat, not a traversal.
    return any(os.path.isdir(d) for d in _HPC_MARKER_DIRS)

# Shared top-level roots. A traversal rooted at exactly one of these is never acceptable.
SHARED_TOPS = {
    "/", "/global", "/global/cfs", "/global/cfs/cdirs", "/global/homes", "/global/u1",
    "/pscratch", "/cfs", "/opt", "/usr", "/etc", "/var", "/proc", "/sys", "/dev",
}
# Any absolute path under one of these mounts is "on a shared filesystem".
SHARED_PREFIXES = ("/global/", "/pscratch/", "/cfs/", "/opt/", "/usr/")

# Commands that walk a tree. `du`/`ls` are only recursive with a flag, handled below.
def short_flag(letter):
    """Match `letter` anywhere inside a short-option CLUSTER: -r, -rn, -Hnr all count.

    Getting this wrong is not academic: the first version of this hook anchored with `\\b`
    right after the letter, so `-r` matched but `grep -rn` -- the literal form that drew the
    NERSC warning -- did NOT. Never anchor on the flag letter; anchor on the cluster.
    """
    return re.compile(rf"(?<![\w-])-[a-zA-Z]*{letter}[a-zA-Z]*(?![\w=])")


# COMMAND POSITION, not "anywhere a space precedes it". A bare `\s` prefix matches the word in
# ordinary PROSE: adapter-kit measured this hook denying a command whose only trigger was the
# English word "tree" inside `echo "=== main's working tree on those paths ==="`. A shell command
# name appears at the start of the string or a line, after a separator (`|`, `&`, `;`, `(`, `&&`,
# `||`), or behind a wrapper (`sudo`, `time`, `nohup`, `xargs`) -- nowhere else.
# Adopted from adapter-kit 1bd690ab; three prose-as-code false positives preceded it there (a
# commit message, an inline-python argument, and the echoed word "tree"), and main hit the same
# class four times on 2026-08-22 before this landed.
_CMD_POS = r"(?:^|\n|[|&;(]|&&|\|\||\b(?:sudo|time|nohup|xargs)\s+)\s*"

WALKERS = re.compile(_CMD_POS + r"(?:find|bfs|fd|fdfind|tree)\b")
GREP_CMD = re.compile(_CMD_POS + r"(?:grep|egrep|fgrep|zgrep)\b")
GREP_R_SHORT = short_flag("[rR]")
GREP_R_LONG = re.compile(r"--(?:recursive|dereference-recursive)\b")
RG_FILES = re.compile(_CMD_POS + r"rg\b[^|;&]*?--files\b")
RG_PLAIN = re.compile(_CMD_POS + r"rg\b")
LS_CMD = re.compile(_CMD_POS + r"ls\b")
LS_R_FLAG = short_flag("R")
DU_R = re.compile(_CMD_POS + r"du\b")
DU_SUMMARY = short_flag("s")
DU_DEPTH = re.compile(r"--max-depth[= ]\d|(?<![\w-])-d\s+\d")
GLOBSTAR = re.compile(r"/\*\*/")
PY_WALK = re.compile(r"\b(?:os\.walk|\.rglob\(|iglob\(|glob\([^)]*recursive\s*=\s*True|Path\([^)]*\)\.walk\()")

# Absolute shared-filesystem paths ANYWHERE in the command text -- including inside a quoted
# argument such as `python -c "... os.walk('/global/cfs/...')"`, which token-splitting misses
# because the whole script is one token that does not itself start with '/'.
EMBEDDED_PATH = re.compile(r"/(?:global|pscratch|cfs|opt|usr)(?:/[\w.\-]+)*")

# Depth bounds that make a deeper-rooted traversal acceptable.
DEPTH_FLAG = re.compile(r"\s-maxdepth\s+\d|\s--max-depth[= ]\d|\s-{1,2}d\s+\d|\s-L\s+\d")

# Index-based, not a filesystem walk — always fine.
GIT_SAFE = re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+(?:grep|ls-files|ls-tree)\b")


# A heredoc body is CODE only when an interpreter consumes it. Fed to anything else it is DATA --
# a commit message, a file being written, a log entry -- and may legitimately *describe* a
# traversal without performing one. On 2026-08-14 this hook denied its own fix's commit message,
# which quoted `os.walk('/global/cfs/...')` while explaining a regression test. Analysing prose as
# if it were code makes the guard unusable for documenting the very rule it enforces.
INTERPRETERS = ("python", "python3", "sh", "bash", "zsh", "perl", "ruby", "node", "awk", "xargs")
HEREDOC_START = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")


def strip_data_heredocs(cmd):
    """Remove heredoc bodies that are not fed to an interpreter."""
    out, pos = [], 0
    for m in HEREDOC_START.finditer(cmd):
        delim = m.group(1)
        # the command owning this heredoc: text back to the previous separator
        seg = cmd[:m.start()]
        seg = re.split(r"[;&|]|\n", seg)[-1].strip()
        head = seg.split()[0] if seg.split() else ""
        is_code = any(head == i or head.endswith("/" + i) for i in INTERPRETERS)
        body = re.search(rf"\n(.*?)\n{re.escape(delim)}\b", cmd[m.end():], re.S)
        if body and not is_code:
            out.append(cmd[pos:m.end() + body.start(1)])
            pos = m.end() + body.end(1)
    out.append(cmd[pos:])
    return "".join(out)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


def _norm(p):
    p = p.rstrip("/") or "/"
    return p


def shared_paths(cmd):
    """Absolute paths in the command that live on a shared filesystem.

    Returns (tops, deeper): paths that ARE a shared top-level, and paths under one.
    """
    try:
        toks = shlex.split(cmd, posix=True)
    except ValueError:                       # unbalanced quotes -> fall back to a crude split
        toks = cmd.split()
    candidates = [t.strip("\"'") for t in toks if t.strip("\"'").startswith("/")]
    # plus any shared path embedded inside a quoted argument (inline python, sh -c, ...)
    candidates += EMBEDDED_PATH.findall(cmd)

    tops, deeper = [], []
    for t in candidates:
        n = _norm(t)
        if n in SHARED_TOPS:
            tops.append(n)
        elif t.startswith(SHARED_PREFIXES):
            deeper.append(n)
    return tops, deeper


BOUNDED_HINT = (
    "Bound it first: root the search at a specific known subdirectory and add a depth limit "
    "(`find <dir> -maxdepth 2 -name '*.F90'`). Inside a git repo use `git grep <pat>` (or "
    "`git grep --recurse-submodules` across submodules) — index-based, not a filesystem walk. "
    "To locate a program use `command -v` / `type -a` / `module spider`. If no bounded root is "
    "known, STOP and ask the user (NERSC's wording). Do NOT re-run this as an equivalent broad "
    "scan through another command — that is itself a violation."
)


def main():
    if not guard_active():
        sys.exit(0)                          # laptop / non-HPC: this rule does not apply
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                          # unparseable -> don't block
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    if not cmd.strip():
        sys.exit(0)
    cmd = strip_data_heredocs(cmd)      # prose describing a traversal is not a traversal

    # `git grep`/`git ls-files` are index reads, never traversals.
    if GIT_SAFE.search(cmd):
        sys.exit(0)

    def _flagged(cmd_re, flag_re, long_re=None):
        """Does the flag appear in THIS command's own argument span?

        Scoped from the command word to the next separator, because searching the whole line
        associates a flag with a command it does not belong to. adapter-kit measured this denying
        `python plot.py --tape <path> | grep -E "..." ; rm -rf ./tmp/x` -- the `-r` came from
        `rm -rf` and made the unrelated `grep -E` look recursive.

        Adopted from adapter-kit 7e53e3ba (its 4th false positive in this hook, after a commit
        message, an inline-python argument, and the echoed word "tree").
        """
        for m in cmd_re.finditer(cmd):
            seg = re.split(r"[|&;\n]", cmd[m.end():])[0]
            if flag_re.search(seg) or (long_re and long_re.search(seg)):
                return True
        return False

    grep_recursive = _flagged(GREP_CMD, GREP_R_SHORT, GREP_R_LONG)
    ls_recursive = _flagged(LS_CMD, LS_R_FLAG)

    # An inline-python walk (os.walk / rglob) targets whatever path sits INSIDE its call. Pairing
    # it with any shared path elsewhere in the command is a false positive: `python - <<PY` that
    # rglob()s the in-repo wiki while calling `git diff` on a checkout under /global/cfs is safe,
    # and this hook denied exactly that on 2026-08-14. Require the shared path to appear near the
    # walk token instead. Shell walkers (find/grep -r) take the path as a positional argument, so
    # the whole-command check stays correct for them.
    py_walk_on_shared = any(
        EMBEDDED_PATH.search(cmd[m.end():m.end() + 160])
        for m in PY_WALK.finditer(cmd)
    )
    globstar_on_shared = any(
        cmd[max(0, m.start() - 160):m.start()].rstrip().endswith(tuple(SHARED_PREFIXES))
        or EMBEDDED_PATH.search(cmd[max(0, m.start() - 160):m.end()])
        for m in GLOBSTAR.finditer(cmd)
    )

    is_walk = bool(
        WALKERS.search(cmd) or grep_recursive or RG_FILES.search(cmd)
        or ls_recursive or py_walk_on_shared or globstar_on_shared
    )
    # `du` recurses by default; treat as a walk unless summarised (-s) or depth-bounded.
    if DU_R.search(cmd) and not (DU_SUMMARY.search(cmd) or DU_DEPTH.search(cmd)):
        is_walk = True
    # bare `rg` walks its path argument (defaults to cwd, which is fine)
    if RG_PLAIN.search(cmd):
        is_walk = True

    if not is_walk:
        sys.exit(0)

    tops, deeper = shared_paths(cmd)

    if tops:
        deny(
            f"NERSC HARD RULE: recursive traversal of a shared top-level directory "
            f"({', '.join(sorted(set(tops)))}) is prohibited on login AND compute nodes. "
            f"No depth flag makes this acceptable. " + BOUNDED_HINT
        )

    if deeper and not DEPTH_FLAG.search(cmd):
        deny(
            f"Unbounded recursive traversal of a shared filesystem path "
            f"({', '.join(sorted(set(deeper))[:3])}). NERSC: 'a compute allocation is not "
            f"permission for an unbounded traversal of a shared filesystem.' " + BOUNDED_HINT
        )

    sys.exit(0)


if __name__ == "__main__":
    # Guard added 2026-08-19: without it, importing this module RUNS the hook,
    # so it cannot be unit-tested in process. Enforced by
    # tests/test_hook_matcher_coverage.py::test_hooks_are_importable_without_running.
    main()
