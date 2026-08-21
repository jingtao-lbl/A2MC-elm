"""The NERSC traversal guard must block real violations AND stay out of the way otherwise.

A hook that blocks too much gets disabled, and NERSC forbids disabling it — so the ALLOW half of
this suite is as load-bearing as the DENY half. Both directions are asserted; a guard that cannot
fail, or that fails on everything, is not a guard ([[feedback_a_check_that_cannot_fail]]).

Author: Jing Tao with Claude.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "block-recursive-traversal.py"


def run_hook(command: str, tool_name: str = "Bash", guard: str = "on"):
    """Returns the parsed hook decision, or None when the hook stays silent (allow).

    `guard` drives A2MC_TRAVERSAL_GUARD: "on" forces the guard (so the deny/allow assertions are
    reproducible on any machine, not only where the HPC autodetect fires), "off" simulates a
    laptop, "" exercises the autodetect.
    """
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    env = {**os.environ, "A2MC_TRAVERSAL_GUARD": guard}
    r = subprocess.run([sys.executable, str(HOOK)], input=payload, env=env,
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, f"hook crashed: {r.stderr}"
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_hook_exists_and_is_executable_python():
    assert HOOK.is_file(), f"missing hook: {HOOK}"


# ------------------------------------------------- LAPTOP / NON-HPC: the guard must NOT fire
# `.claude/hooks/` and `.claude/settings.json` ship to the PUBLIC repo, and /usr, /opt, /etc, /var
# are ordinary local directories on a Mac or Linux laptop (Homebrew lives in /opt/homebrew and
# /usr/local). An ungated guard would break every A2MC user's local searches to enforce a rule that
# only binds on a shared HPC filesystem. Regression for exactly that (2026-08-14).
@pytest.mark.parametrize("cmd", [
    "find /usr/local/lib -name '*.dylib'",
    "grep -rn 'foo' /opt/homebrew/include",
    "find /usr -name python3",
    "grep -rn 'x' /etc",
    # even the shared-top forms are none of our business off-HPC
    "find /global/cfs -name '*.nc'",
])
def test_guard_is_inert_off_hpc(cmd):
    assert run_hook(cmd, guard="off") is None, f"blocked a laptop command: {cmd}"


def test_guard_autodetects_on_this_machine():
    """Sanity: with no override, the guard should be ACTIVE here (Perlmutter) — otherwise the
    protection silently does nothing on the machine that actually needs it."""
    verdict = run_hook("find /global -name '*.nc'", guard="")
    assert verdict == "deny", (
        "autodetect did not activate the guard on this machine; check _HPC_MARKER_DIRS/_ENV")


# --------------------------------------------------------------------------- DENY
@pytest.mark.parametrize("cmd", [
    # the exact class of call that drew the NERSC warning
    "grep -rn 'EDPftvarcon' --include=*.F90 ~/E3SM_FATES_api43",
    "grep -rln 'phenology' ~/E3SM_FATES_api43/components/elm/src/",
    # rooted AT a shared top -- never acceptable, depth flag or not
    "find /global -name '*.nc'",
    "find /global/cfs -maxdepth 3 -name '*.nc'",
    "find / -name ecosim",
    "du -h /global/cfs",
    "ls -R /pscratch",
    "tree /usr",
    # deeper root but unbounded
    "find ~/EcoSIM -name '*.F90'",
    "fd F90 ~/EcoSIM",
    "rg --files ~",
    "python -c \"import os; [print(r) for r,d,f in os.walk('/global/cfs/cdirs/m5199')]\"",
    "ls /global/cfs/cdirs/m5199/**/*.nc",
])
def test_denies_prohibited_traversals(cmd):
    assert run_hook(cmd) == "deny", f"hook FAILED to block: {cmd}"


# --------------------------------------------------------------------------- ALLOW
@pytest.mark.parametrize("cmd", [
    # index-based: the sanctioned replacement, including across submodules
    "git grep -n 'EDPftvarcon' -- '*.F90'",
    "git -C ~/E3SM_FATES_api43 grep --recurse-submodules -n 'EDPftvarcon' -- '*.F90'",
    "git ls-files --cached --others --exclude-standard",
    # bounded root + depth limit on a shared path -- explicitly permitted by NERSC
    "find ~/EcoSIM -maxdepth 2 -name '*.F90'",
    "du -sh ~/EcoSIM",
    # workspace-relative: "a bounded root inside the current workspace"
    "grep -rn 'def sample_sobol' --include=*.py .",
    "find ./tmp -name '*.txt'",
    "rg 'LEAK_TOKENS'",
    # not traversals at all
    "ls -la ~/.claude/",
    "cat ~/EcoSIM/runfile.nml",
    "command -v python3",
    "module spider texlive",
    "sbatch ~/run.sh",
    # REGRESSION (2026-08-14): the hook denied this real command. The rglob() targets the IN-REPO
    # wiki; the shared path is only an argument to `git diff`, which is index-based. Pairing any
    # walk-token with any shared path anywhere in the command is too coarse.
    "python - <<'PY'\nimport subprocess,pathlib\n"
    "subprocess.run(['git','-C','~/E3SM_FATES_api43','diff','--name-only'])\n"
    "for p in pathlib.Path('docs/fates-knowledge-base').rglob('*.md'): print(p)\nPY",
])
def test_allows_legitimate_commands(cmd):
    assert run_hook(cmd) is None, f"hook WRONGLY blocked: {cmd}"


def test_prose_describing_a_traversal_is_not_a_traversal():
    """REGRESSION (2026-08-14): the hook denied its own fix's COMMIT MESSAGE, which quoted
    os.walk('/global/cfs/...') while explaining a regression test. A heredoc fed to `git commit -F -`
    is data, not code."""
    cmd = ("git commit -F - <<'EOF'\n"
           "Fix a traversal-hook false positive\n\n"
           "os.walk('~') -- where the walk's own argument IS the\n"
           "shared path -- must still DENY. Also `grep -rn x /global/cfs/...` stays blocked.\n"
           "EOF")
    assert run_hook(cmd) is None


def test_heredoc_fed_to_an_INTERPRETER_is_still_code():
    """The narrowing must not become a bypass: the same body fed to python IS executed."""
    cmd = ("python - <<'PY'\n"
           "import os\n"
           "[print(r) for r,d,f in os.walk('~')]\n"
           "PY")
    assert run_hook(cmd) == "deny"


def test_writing_a_file_about_traversal_is_allowed():
    cmd = ("cat > ./tmp/notes.md <<'EOF'\n"
           "Never run `find /global -name x` on a shared filesystem.\n"
           "EOF")
    assert run_hook(cmd) is None


def test_inline_python_walk_ON_a_shared_path_is_still_denied():
    """The narrowing above must not let the real case through: when the walk's OWN argument is the
    shared path, it is still a prohibited traversal."""
    cmd = ("python -c \"import os; [print(r) for r,d,f in "
           "os.walk('~')]\"")
    assert run_hook(cmd) == "deny"


# --------------------------------------------------------------------------- robustness
def test_ignores_non_bash_tools():
    assert run_hook("find /global -name x", tool_name="Read") is None


def test_survives_unbalanced_quotes():
    """A crash would fail-open silently on every later command; assert it degrades gracefully."""
    assert run_hook("""grep -rn "unclosed /global/cfs/cdirs/m2467""") in {None, "deny"}


def test_empty_command_is_allowed():
    assert run_hook("") is None


def test_denial_message_names_the_bounded_alternative():
    """The message has to teach the fix, or the next attempt is just a workaround."""
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "find /global -name '*.nc'"}})
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=20)
    reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "git grep" in reason
    assert "maxdepth" in reason
    assert "STOP and ask" in reason
    # NERSC forbids routing around the guard; the message must say so.
    assert "another command" in reason
