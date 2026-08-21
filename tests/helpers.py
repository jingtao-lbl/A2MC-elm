"""Shared test helpers."""

# ---------------------------------------------------------------------------
# The ACTIVE parameter list — read the SAME authority production reads.
#
# Production never guesses: the site config exports A2MC_PARAM_LIST_FILE and
# every runtime path uses it. Tests used to guess instead — first a
# sorted-glob[0] (which silently picked the RETIRED para168), then a
# "newest paraNNN minus a blocklist" heuristic (which picked the in-progress
# para178_candidate on 2026-08-09 and killed collection for all 370 tests
# for ten days). A blocklist can only enumerate names already retired; it
# cannot anticipate _candidate, _draft, _wip. So don't guess — read the config.
# ---------------------------------------------------------------------------
def active_param_list(site: str = "Kougarok"):
    """Path to the active parameter list, resolved as the running system does.

    1. ``$A2MC_PARAM_LIST_FILE`` when set (what a sourced site config exports);
    2. else parse that same export out of the site config file.

    Raises rather than falling back to a guess — a wrong list silently changes
    the search space, which is worse than a missing one.
    """
    import os
    import re
    from pathlib import Path

    env = os.environ.get("A2MC_PARAM_LIST_FILE")
    if env and Path(env).is_file():
        return Path(env)

    repo = Path(__file__).resolve().parents[1]
    use_case_dir = repo / "use_cases" / site
    # DISCOVER the config rather than deriving its name from the case name: the
    # two need not match. `use_cases/ELM-FATES_Kougarok/` still holds
    # `kougarok_config.sh`, because the case was renamed to the {Model}_{Site}
    # convention while the file kept its original name. `*_config.sh` excludes
    # round wrappers, which end `_r4.sh` rather than `_config.sh`.
    cfgs = sorted((use_case_dir / "config").glob("*_config.sh"))
    if not cfgs:
        raise FileNotFoundError(f"no *_config.sh in {use_case_dir / 'config'}")
    if len(cfgs) > 1:
        raise ValueError(f"ambiguous site config in {use_case_dir / 'config'}: "
                         f"{[c.name for c in cfgs]} — name the one you mean")
    cfg = cfgs[0]

    m = re.search(r'^export\s+A2MC_PARAM_LIST_FILE=(.+)$', cfg.read_text(), re.M)
    if not m:
        raise ValueError(f"{cfg} does not export A2MC_PARAM_LIST_FILE")

    raw = m.group(1).strip().strip('"').strip("'")
    path = Path(raw.replace("${A2MC_USE_CASE_DIR}", str(use_case_dir)))
    if not path.is_file():
        raise FileNotFoundError(
            f"{cfg} points A2MC_PARAM_LIST_FILE at {path}, which does not exist")
    return path
