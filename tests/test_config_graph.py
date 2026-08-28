"""tools/config_graph.py — the repo's own A2MC_* config graph.

Adopted from adapter-kit v2.270 (re-authored, per adopt-from-adapter-kit).

The classification logic is the whole value of this tool, so it is tested on synthetic content
rather than on the live repo: a test that asserts against main's actual tree passes for the wrong
reason the moment someone adds a variable. The two live-tree tests at the end assert only
invariants that cannot drift.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import config_graph as cg  # noqa: E402


def _scan(tmp_path, files: dict) -> dict:
    """Scan synthetic files by pointing cg.REPO at a tmp tree."""
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    orig = cg.REPO
    cg.REPO = tmp_path
    try:
        return cg.scan(list(files))
    finally:
        cg.REPO = orig


# --------------------------------------------------------------------------- shell


def test_shell_export_is_a_set(tmp_path):
    g = _scan(tmp_path, {"a2mc_config.sh": "export A2MC_FOO=3\n"})
    assert len(g["A2MC_FOO"]["set"]) == 1
    assert g["A2MC_FOO"]["read"] == []


def test_shell_default_counts_as_set_not_read(tmp_path):
    """`FOO=${FOO:-x}` both sets and reads FOO; the SET is what matters.

    If this regressed to counting a read, every defaulted variable in a2mc_config.sh would
    appear in --orphans as read-but-never-set -- i.e. the orphan list would be noise.
    """
    g = _scan(tmp_path, {"a2mc_config.sh": "export A2MC_FOO=${A2MC_FOO:-9}\n"})
    assert len(g["A2MC_FOO"]["set"]) == 1
    assert g["A2MC_FOO"]["read"] == []


def test_shell_dollar_reference_is_a_read(tmp_path):
    g = _scan(tmp_path, {"tools/x.sh": 'echo "$A2MC_FOO ${A2MC_BAR}"\n'})
    assert len(g["A2MC_FOO"]["read"]) == 1
    assert len(g["A2MC_BAR"]["read"]) == 1
    assert g["A2MC_FOO"]["set"] == []


# --------------------------------------------------------------------------- python


@pytest.mark.parametrize("line", [
    "x = os.environ.get('A2MC_FOO', '1')",
    'x = os.environ["A2MC_FOO"]',
    "x = os.getenv('A2MC_FOO')",
])
def test_python_reads(tmp_path, line):
    g = _scan(tmp_path, {"tools/x.py": line + "\n"})
    assert len(g["A2MC_FOO"]["read"]) == 1, line
    assert g["A2MC_FOO"]["set"] == []


@pytest.mark.parametrize("line", [
    "os.environ['A2MC_FOO'] = '1'",
    "os.environ.setdefault('A2MC_FOO', '1')",
])
def test_python_writes(tmp_path, line):
    g = _scan(tmp_path, {"tools/x.py": line + "\n"})
    assert len(g["A2MC_FOO"]["set"]) == 1, line


# --------------------------------------------------------------------------- record vs code


def test_dev_log_mention_is_a_record_not_a_consumer(tmp_path):
    """A log quoting a variable is not a reader.

    Without this split, a well-travelled variable drowns in its own history: on main a name has
    more mentions under memory/ than occurrences in code.
    """
    g = _scan(tmp_path, {"memory/dev_logs/20260822a_x.md": "we set A2MC_FOO=3 yesterday\n"})
    assert g["A2MC_FOO"]["set"] == []
    assert g["A2MC_FOO"]["read"] == []
    assert len(g["A2MC_FOO"]["record"]) == 1


def test_site_config_sh_is_code_but_experiment_script_is_record(tmp_path):
    """The `/config/` carve-out: the site config layer is a real setter."""
    g = _scan(tmp_path, {
        "use_cases/S/config/s_config.sh": "export A2MC_FOO=1\n",
        "use_cases/S/memory/phase_results/x/run.sh": "export A2MC_BAR=1\n",
    })
    assert len(g["A2MC_FOO"]["set"]) == 1, "site config must count as code"
    assert g["A2MC_BAR"]["set"] == [], "an experiment script under use_cases/ is a record"
    assert len(g["A2MC_BAR"]["record"]) == 1


# --------------------------------------------------------------------------- orphan shapes


def test_orphan_shapes_are_distinguished(tmp_path):
    g = _scan(tmp_path, {
        "a2mc_config.sh": "export A2MC_SET_ONLY=1\n",
        "tools/x.py": "y = os.environ.get('A2MC_READ_ONLY')\n",
    })
    unset = [v for v, e in g.items() if e["read"] and not e["set"]]
    unread = [v for v, e in g.items() if e["set"] and not e["read"]]
    assert unset == ["A2MC_READ_ONLY"]
    assert unread == ["A2MC_SET_ONLY"]


# --------------------------------------------------------------------------- CLI contract


def _run(*args):
    return subprocess.run([sys.executable, str(REPO / "tools" / "config_graph.py"), *args],
                          capture_output=True, text=True, cwd=REPO)


def test_missing_var_exits_nonzero():
    """A query for a variable that does not exist must FAIL, not print an empty success."""
    r = _run("--var", "A2MC_DEFINITELY_NOT_A_REAL_VARIABLE")
    assert r.returncode == 1


def test_like_with_no_match_exits_nonzero():
    assert _run("--like", "ZZZZ_NO_SUCH_SUBSTRING").returncode == 1


def test_live_tree_finds_the_sobol_flag_set_once_and_read_thrice():
    """Invariant, not a snapshot: A2MC_SOBOL_SECOND_ORDER must stay set-once/read-many.

    It is the variable v2.269 introduced across three surfaces (a2mc_config.sh, tools/config.py,
    create_parameter_sample.py). If it ever becomes read-but-never-set, the orphan the adoption
    was careful to avoid has been reintroduced.
    """
    r = _run("--var", "A2MC_SOBOL_SECOND_ORDER", "--quiet")
    assert r.returncode == 0
    assert "SET BY (1)" in r.stdout
    assert "READ BY (3)" in r.stdout
    assert "READ but never SET" not in r.stdout
