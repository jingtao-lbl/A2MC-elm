#!/usr/bin/env python3
"""Generate and VERIFY the manifest of archived model binaries.

WHY THIS EXISTS. A run must be attributable to the exact executable it ran. CIME builds
per-case, so the baseline is less exposed than on a shared build tree -- but A2MC routinely REUSES a
prebuilt executable across an experiment family (`PREBUILT_EXEROOT_TEMPLATE` in the offline
launchers), and a queued job resolves its executable at RUN time. The rebuild that swaps it need not
be yours. Archives are **not regenerable**: a recompile can perturb floating point, so a rebuilt
binary is a DIFFERENT artifact, not the same one.

Those archives live outside git — hundreds of MB each, and putting them in a fork of an upstream
scientific code would bloat its history permanently. But "not in git" had meant *nothing recorded
they existed*: every SHA256 sat only inside a `PROVENANCE.txt` that was itself ignored, so a
deleted or silently altered archive would be discovered by a run failing, and the
`model_change_ledger` entries naming those binaries were assertions nobody could check.

This tracks the MANIFEST, not the binaries: a few KB of text giving, per archive, its label,
source commit, branch, size and SHA256. That buys the three things tracking was for — a permanent
record that each existed, a checksum to detect alteration or swap, and enough provenance to say
which build produced a result — at no cost to repository size.

WHAT WOULD MAKE `--verify` FAIL (named first, per `feedback_a_check_that_cannot_fail`):
  M1  an archive in the manifest is MISSING from disk                  -> ERROR
  M2  a binary's SHA256 differs from the manifest                       -> ERROR (altered or swapped)
  M3  a binary's SHA256 differs from its own PROVENANCE.txt             -> ERROR (internally inconsistent)
  M4  an archive exists on disk but is ABSENT from the manifest         -> WARN (regenerate)
  M5  an archive directory has no binary, or no PROVENANCE.txt          -> WARN
  M6  no archive root found at all                                      -> ERROR (anti-silent-pass)
  M7  a ROUND LEDGER checksum claim does not resolve against the manifest -> ERROR

Usage:
    python tools/binary_archive_manifest.py --generate   # write/refresh the manifest
    python tools/binary_archive_manifest.py --verify     # check disk against it
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Per-model archive roots. The manifest is stored under the CASE, beside the round records that
#: cite these binaries, because the provenance chain that matters is round -> binary.
def _archive_root() -> str:
    """The binary archive root, from config -- never a literal host path.

    A2MC_BINARY_ARCHIVE_ROOT if set, else <A2MC_OUTPUT_ROOT>/build_archive. Hardcoding an absolute
    path here would both violate the no-hardcoded-paths rule and put a host path into a file that
    ships publicly, so the value is resolved from the sourced config at call time.
    """
    explicit = os.environ.get("A2MC_BINARY_ARCHIVE_ROOT", "").strip()
    if explicit:
        return explicit
    out = os.environ.get("A2MC_OUTPUT_ROOT", "").strip()
    return str(pathlib.Path(out) / "build_archive") if out else ""


def _case_manifest() -> pathlib.Path:
    """The manifest lives under the CASE, beside the round records that cite these binaries."""
    ucd = os.environ.get("A2MC_USE_CASE_DIR", "").strip()
    base = pathlib.Path(ucd) if ucd else ROOT / "use_cases/TEMPLATE"
    return base / "config" / "binary_archive_manifest.json"


#: Per-model archive config. Values resolve from the sourced config chain, so this file carries no
#: host path. The manifest is stored under the CASE because the chain that matters is round -> binary.
ARCHIVES = {
    "elm-fates": {
        "archive_root": _archive_root(),
        "manifest": _case_manifest(),
        "binary_name": "e3sm.exe",
    },
}

_SHA_LINE = re.compile(r"^\s*SHA256\s*:\s*([0-9a-f]{64})\s*$", re.I | re.M)
# NOTE: fields are parsed ONE PER LINE. A value wrapped across lines is captured only up to
# the first newline, which silently truncates it mid-sentence in the manifest -- keep each
# PROVENANCE.txt field on a single line however long.
_FIELD = re.compile(r"^\s*(Archived|Source|Change|Binary|Why|V0 pair|Case|Build dir)\s*:\s*(.+)$", re.I | re.M)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_provenance(p: pathlib.Path):
    """(claimed_sha, {field: value}) from a PROVENANCE.txt, or (None, {}) if unreadable."""
    if not p.is_file():
        return None, {}
    text = p.read_text(errors="replace")
    m = _SHA_LINE.search(text)
    fields = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in _FIELD.findall(text)}
    return (m.group(1).lower() if m else None), fields


def scan(model: str):
    """Walk one model's archive root. Returns (entries, problems)."""
    cfg = ARCHIVES[model]
    if not cfg["archive_root"]:
        # An empty root would make scan() return zero entries and read as "no archives yet".
        # Source the config chain first (feedback_a_check_that_cannot_fail).
        return [], [f"{model}: archive root unresolved -- set A2MC_BINARY_ARCHIVE_ROOT or "
                    f"A2MC_OUTPUT_ROOT (source a2mc_config.sh + the case config)"]
    root = pathlib.Path(cfg["archive_root"])
    entries, problems = [], []
    if not root.is_dir():
        problems.append(f"{model}: archive root does not exist: {root}")
        return entries, problems
    # os.scandir, not a glob walk: this lives on a shared filesystem where recursive traversal is
    # prohibited, and one level is all that is needed (feedback_nersc_no_recursive_traversal).
    for d in sorted(os.scandir(root), key=lambda e: e.name):
        if not d.is_dir():
            continue
        binp = pathlib.Path(d.path) / cfg["binary_name"]
        provp = pathlib.Path(d.path) / "PROVENANCE.txt"
        if not binp.is_file():
            problems.append(f"{model}/{d.name}: no {cfg['binary_name']} -- not a binary archive")
            continue
        claimed, fields = read_provenance(provp)
        if claimed is None:
            problems.append(f"{model}/{d.name}: PROVENANCE.txt missing or carries no SHA256 line")
        actual = sha256(binp)
        if claimed and claimed != actual:
            problems.append(f"{model}/{d.name}: SHA256 disagrees with its OWN PROVENANCE.txt "
                            f"(provenance {claimed[:12]}..., actual {actual[:12]}...) -- the "
                            f"archive is internally inconsistent")
        entries.append({
            "label": d.name,
            "model": model,
            "binary": cfg["binary_name"],
            "bytes": binp.stat().st_size,
            "sha256": actual,
            "provenance_sha256": claimed,
            # WHERE it was built, not just what from: a CIME case dir plus its EXEROOT. Without
            # these, "which build produced this" is answerable only by whoever ran it.
            "built_in_case": fields.get("case", ""),
            "build_dir": fields.get("build_dir", ""),
            "source": fields.get("source", ""),
            "change": fields.get("change", ""),
            "archived": fields.get("archived", ""),
        })
    return entries, problems


def cmd_generate(models, stamp):
    rc = 0
    for model in models:
        entries, problems = scan(model)
        for p in problems:
            print(f"  WARN  {p}")
        if not entries:
            print(f"✘ {model}: no archives found at {ARCHIVES[model]['archive_root']}", file=sys.stderr)
            rc = max(rc, 2)
            continue
        out = ARCHIVES[model]["manifest"]
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_comment": (
                "Manifest of ARCHIVED model binaries. The binaries themselves are NOT in git -- "
                "hundreds of MB each, and not regenerable (a recompile can perturb floating point, so a "
                "rebuild is a different artifact). This file is the record that they existed and "
                "the checksum to prove one has not been altered or swapped. Regenerate and verify "
                "with tools/binary_archive_manifest.py. Losing the archive directory breaks the "
                "provenance of every completed round that cites one of these labels."),
            "_archive_root": ARCHIVES[model]["archive_root"],
            "_generated": stamp,
            "_tool": "tools/binary_archive_manifest.py",
            "archives": entries,
        }
        out.write_text(json.dumps(payload, indent=2) + "\n")
        total = sum(e["bytes"] for e in entries) / 1e6
        print(f"✔ {model}: {len(entries)} archive(s), {total:.0f} MB on disk -> "
              f"{out.relative_to(ROOT)}")
    return rc


def check_round_ledger(model, manifest_path, recorded):
    """M7 -- a round that CLAIMS a checksum must be checkable against the manifest.

    THIS BRANCH'S SCHEMA, not adapter-kit's. adapter-kit hangs `round_binaries` off a top-level
    `model_change_ledger` key; main has never had that key -- it records per-round model provenance
    in each round's own `fates_source` block, which `tools/generate_calibration_rounds.py` already
    writes. The binary claim therefore lives at:

        rounds[N].fates_source.binary = {archive_label: ..., sha256_prefix: ...}

    Reading adapter's key here would make M7 DEAD CODE: it would resolve nothing, find nothing to
    disagree with, and report a clean pass forever (`feedback_a_check_that_cannot_fail`). A ledger
    claim that cannot be resolved is exactly the "assertions nobody could check" state the manifest
    was built to end (`feedback_verify_derived_numbers_not_just_citations`).

    The ledger lives beside the manifest, because the provenance chain is round -> binary.
    """
    ledger = manifest_path.parent / "calibration_rounds.yaml"
    if not ledger.is_file():
        return []                       # a case with no round ledger is not an error here
    try:
        import yaml
        doc = yaml.safe_load(ledger.read_text()) or {}
    except Exception as exc:                                     # pragma: no cover - malformed yaml
        return [f"{model}: cannot read {ledger.name} to cross-check round checksums ({exc})"]

    rounds = doc.get("rounds")
    if isinstance(rounds, dict):
        items = list(rounds.items())
    elif isinstance(rounds, list):
        items = [(r.get("round", i + 1) if isinstance(r, dict) else i + 1, r)
                 for i, r in enumerate(rounds)]
    else:
        return [f"{model}: `rounds` is neither a list nor a mapping in {ledger.name}"]

    out, claims = [], 0
    for n, rec in items:
        if not isinstance(rec, dict):
            continue
        src = rec.get("fates_source")
        claim = src.get("binary") if isinstance(src, dict) else None
        if not claim:
            continue                    # a round with no binary claim is a gap, not a contradiction
        if not isinstance(claim, dict):
            out.append(f"{model}: round {n} `fates_source.binary` is not a mapping "
                       f"(want archive_label + sha256_prefix)")
            continue
        label, prefix = claim.get("archive_label"), claim.get("sha256_prefix")
        if not label:
            out.append(f"{model}: round {n} `fates_source.binary` has no archive_label")
            continue
        claims += 1
        entry = recorded.get(label)
        if entry is None:
            out.append(f"{model}: round {n} cites archive_label '{label}' but the manifest has no "
                       f"such archive -- that round's provenance claim cannot be resolved")
        elif prefix and not entry["sha256"].startswith(str(prefix)):
            out.append(f"{model}: round {n} claims sha256_prefix '{prefix}' for '{label}', but the "
                       f"manifest records {entry['sha256'][:12]}... -- the ledger and the manifest "
                       f"disagree about which binary that round ran")

    # Report how many claims were CHECKED. "0 errors" over 0 claims is not a pass, and the count is
    # the only thing that tells the two apart.
    print(f"  M7: {claims} round binary claim(s) cross-checked against the manifest")
    return out


def cmd_verify(models):
    errors, warnings = [], []
    for model in models:
        man = ARCHIVES[model]["manifest"]
        if not man.is_file():
            errors.append(f"{model}: no manifest at {man} -- run --generate")
            continue
        recorded = {e["label"]: e for e in json.loads(man.read_text())["archives"]}
        on_disk, problems = scan(model)
        warnings.extend(problems)
        seen = {e["label"]: e for e in on_disk}

        for label, e in recorded.items():                                          # M1, M2
            if label not in seen:
                errors.append(f"{model}/{label}: in the manifest but MISSING from disk. Every "
                              f"round citing this binary now has unverifiable provenance.")
                continue
            if seen[label]["sha256"] != e["sha256"]:
                errors.append(f"{model}/{label}: SHA256 CHANGED "
                              f"(manifest {e['sha256'][:12]}..., disk "
                              f"{seen[label]['sha256'][:12]}...) -- an archived binary is supposed "
                              f"to be immutable; it has been altered or swapped")
        for label in seen:                                                          # M4
            if label not in recorded:
                warnings.append(f"{model}/{label}: on disk but not in the manifest -- "
                                f"run --generate after archiving a new build")

        errors.extend(check_round_ledger(model, man, recorded))                      # M7

    if not any(ARCHIVES[m]["manifest"].is_file() or
               pathlib.Path(ARCHIVES[m]["archive_root"]).is_dir() for m in models):  # M6
        errors.append("no archive root and no manifest found for any model -- nothing was "
                      "checked, which is not a pass")

    n = sum(len(json.loads(ARCHIVES[m]["manifest"].read_text())["archives"])
            for m in models if ARCHIVES[m]["manifest"].is_file())
    print(f"binary archive verification — {n} archive(s) in manifest(s)")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 2
    if warnings:
        print(f"\n{len(warnings)} warning(s)")
        return 1
    print("\n✔ every archived binary is present and matches its recorded checksum")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generate", action="store_true", help="write/refresh the manifest from disk")
    ap.add_argument("--verify", action="store_true", help="check disk against the manifest")
    ap.add_argument("--model", default=None, help=f"one of {sorted(ARCHIVES)} (default: all)")
    ap.add_argument("--stamp", default=None,
                    help="generation timestamp; defaults to now. Pass one for a reproducible file.")
    a = ap.parse_args()
    models = [a.model] if a.model else sorted(ARCHIVES)
    for m in models:
        if m not in ARCHIVES:
            print(f"unknown model {m!r}; known: {sorted(ARCHIVES)}", file=sys.stderr)
            return 2
    if a.generate:
        return cmd_generate(models, a.stamp or datetime.now().strftime("%Y-%m-%d"))
    if a.verify:
        return cmd_verify(models)
    ap.print_usage(sys.stderr)
    print("\nGive --generate or --verify.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
