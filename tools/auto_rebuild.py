#!/usr/bin/env python3
"""
auto_rebuild.py - Tier-aware drift handler for the orchestrator alignment hook.

Implements docs/22 §3.1 in a single entry point, ``handle_drift()``, that
the orchestrator invokes when ``RAGSelection.rebuild_required`` is True.

Responsibility map (per docs/22 §3.1):

    | Tier / condition                | Action                                  | Flag-gated |
    |---------------------------------|-----------------------------------------|------------|
    | T1 (no drift, sha match)        | In-process metadata refresh             | No         |
    | T2 (same epoch, sha differs)    | Subprocess rebuild + validator gate     | Yes        |
    | T3 with epoch_distance ≤ N      | Subprocess rebuild + validator gate     | Yes        |
    | T3 with epoch_distance > N      | Emit prompt-pack + abort startup        | No (manual)|

Rebuild safety net:
    - Before T2 / T3-near rebuild, snapshot the profile to ``<profile>.previous/``
    - After rebuild, run ``run_all_validators(profile, include_smoke=False)``
    - Validators Green: delete snapshot, success
    - Validators Red: move broken to ``<profile>.failed_<ts>/``, restore snapshot,
      raise ``DriftHandlerError`` (orchestrator surfaces to the user)

Concurrency safety: a file lock at ``<rag_dir>/.bump.lock`` prevents two
orchestrator startups from racing on the same profile rebuild.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
import contextlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("a2mc.auto_rebuild")


# =============================================================================
# Errors
# =============================================================================

class DriftHandlerError(RuntimeError):
    """Raised when the drift handler cannot bring the RAG to a Green state.

    Orchestrator surfaces this as a startup error. The message includes
    the profile name and a hint about manual remediation.
    """


# =============================================================================
# Constants
# =============================================================================

DEFAULT_T3_AUTO_DISTANCE = 100  # one major api epoch step
REBUILD_TIMEOUT_SECONDS = 30 * 60  # subprocess hard cap
LOCK_WAIT_SECONDS = 60


# =============================================================================
# Public entry point
# =============================================================================

def handle_drift(
    selection,
    classification,
    *,
    model_path: Path,
    rag_dir: Path,
    repo_root: Path,
    auto_rebuild: bool,
) -> str:
    """Dispatch on tier per docs/22 §3.1.

    Args:
        selection: ``RAGSelection`` from ``rag_selector.select_rag()``.
        classification: ``BumpClassification`` from ``classify_bump_tier()``.
        model_path: User's E3SM checkout root.
        rag_dir: RAG storage root (``<repo>/rag``).
        repo_root: A2MC repo root (used to locate ``scripts/``).
        auto_rebuild: True when ``A2MC_RAG_AUTO_REBUILD`` is on.

    Returns:
        Human-readable status string for orchestrator logging.

    Raises:
        DriftHandlerError: rebuild failed or distant T3 + always-manual policy.
    """
    profile = selection.profile_name
    if not profile:
        raise DriftHandlerError(
            "Cannot handle drift: selection has no profile_name. "
            "Run `scripts/rag_match.py` to investigate."
        )

    tier = classification.tier
    epoch_distance = classification.epoch_distance
    threshold = _read_t3_threshold()

    # T1 always auto — sub-second metadata refresh, no flag gate.
    if tier == "T1":
        return _do_t1_refresh(profile, model_path, rag_dir, repo_root)

    # T3 distant — never auto, regardless of flag.
    if tier == "T3" and epoch_distance > threshold:
        return _emit_prompt_pack_and_abort(
            profile, model_path, epoch_distance, threshold, repo_root,
            rag_dir=rag_dir,
        )

    # T2 or T3-near — flag-gated.
    if not auto_rebuild:
        msg = (
            f"[RAG alignment] Drift detected (tier {tier}, "
            f"epoch_distance={epoch_distance}). Continuing anyway since "
            f"A2MC_RAG_AUTO_REBUILD is not set. To rebuild manually: "
            f"`python scripts/rag_bump.py --target-milestone {profile} "
            f"--mode auto`."
        )
        logger.warning(msg)
        return msg

    # Auto-rebuild path with snapshot + validator gate.
    return _auto_rebuild_with_gate(profile, model_path, rag_dir, repo_root)


# =============================================================================
# T1: in-process metadata refresh
# =============================================================================

def _do_t1_refresh(profile: str, model_path: Path, rag_dir: Path,
                   repo_root: Path) -> str:
    """T1: just refresh metadata. Mode-aware safe — no chunk changes."""
    from rag_refresh import refresh_metadata, RefreshError
    try:
        md = refresh_metadata(profile, model_path,
                              rag_dir=rag_dir, repo_root=repo_root)
    except RefreshError as e:
        raise DriftHandlerError(f"T1 metadata refresh failed: {e}") from e

    msg = (
        f"[RAG alignment] T1 metadata refresh complete for {profile} "
        f"(built_at={md.get('built_at', '?')})."
    )
    logger.info(msg)
    return msg


# =============================================================================
# T3 distant: emit prompt-pack and abort
# =============================================================================

def _emit_prompt_pack_and_abort(profile: str, model_path: Path,
                                epoch_distance: int, threshold: int,
                                repo_root: Path,
                                rag_dir: Optional[Path] = None) -> str:
    """T3 with epoch_distance > threshold: write prompt-pack, raise.

    Distant epoch jumps require human-supervised wiki regen (parameter file
    format may have changed, dim semantics may have shifted). Auto-rebuild
    is never safe here regardless of the flag.
    """
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "rag_bump.py"),
        "--target-milestone", profile,
        "--mode", "prompt-pack",
        "--model-path", str(model_path),
    ]
    if rag_dir is not None:
        cmd.extend(["--rag-dir", str(rag_dir)])
    logger.info(f"[RAG alignment] T3 (distance {epoch_distance} > {threshold}): "
                f"writing prompt-pack via {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, timeout=REBUILD_TIMEOUT_SECONDS,
                       cwd=str(repo_root))
    except subprocess.CalledProcessError as e:
        raise DriftHandlerError(
            f"T3 prompt-pack generation failed (exit {e.returncode}). "
            f"See `scripts/rag_match.py` for triage."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise DriftHandlerError(
            f"T3 prompt-pack generation timed out after "
            f"{REBUILD_TIMEOUT_SECONDS}s."
        ) from e

    raise DriftHandlerError(
        f"T3 bump required (epoch_distance={epoch_distance} exceeds "
        f"auto threshold {threshold}). Prompt-pack written under "
        f"Offline/bump_pack_{profile}/. Review the regenerated wiki, "
        f"build with `scripts/build_rag_index.py --rebuild`, then re-run."
    )


# =============================================================================
# T2 / T3-near: subprocess rebuild with snapshot + validator gate
# =============================================================================

def _auto_rebuild_with_gate(profile: str, model_path: Path, rag_dir: Path,
                            repo_root: Path) -> str:
    """Snapshot, rebuild, validate, restore-or-cleanup. File-locked."""
    with _bump_lock(rag_dir):
        snapshot_paths = _snapshot_profile(rag_dir, profile)
        try:
            _run_rebuild_subprocess(profile, model_path, repo_root,
                                    rag_dir=rag_dir)
            verdict = _run_validator_gate(profile, repo_root)
            if verdict["verdict"] != "Green":
                _rollback_profile(rag_dir, profile, snapshot_paths,
                                  reason="validators_red")
                raise DriftHandlerError(
                    f"Auto-rebuild of {profile} failed validator gate "
                    f"(verdict=Red). Profile rolled back from snapshot. "
                    f"Failed build moved to "
                    f"{rag_dir}/chroma_db/{profile}.failed_<ts>/ for forensics."
                )
        except subprocess.CalledProcessError as e:
            _rollback_profile(rag_dir, profile, snapshot_paths,
                              reason="subprocess_failed")
            raise DriftHandlerError(
                f"Auto-rebuild subprocess failed (exit {e.returncode}). "
                f"Profile rolled back from snapshot."
            ) from e
        except subprocess.TimeoutExpired as e:
            _rollback_profile(rag_dir, profile, snapshot_paths,
                              reason="subprocess_timeout")
            raise DriftHandlerError(
                f"Auto-rebuild timed out after {REBUILD_TIMEOUT_SECONDS}s. "
                f"Profile rolled back from snapshot."
            ) from e
        except DriftHandlerError:
            raise
        except Exception as e:
            _rollback_profile(rag_dir, profile, snapshot_paths,
                              reason="unexpected_error")
            raise DriftHandlerError(
                f"Auto-rebuild of {profile} hit unexpected error: {e}. "
                f"Profile rolled back from snapshot."
            ) from e
        else:
            _delete_snapshot(snapshot_paths)
            msg = f"[RAG alignment] Auto-rebuild of {profile} complete (Green)."
            logger.info(msg)
            return msg


def _run_rebuild_subprocess(profile: str, model_path: Path, repo_root: Path,
                            rag_dir: Optional[Path] = None):
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "rag_bump.py"),
        "--target-milestone", profile,
        "--mode", "auto",
        "--model-path", str(model_path),
    ]
    # Pass --rag-dir explicitly so the subprocess uses the same tree the
    # orchestrator snapshot/rollback operate on. rag_bump.py also reads
    # A2MC_RAG_DIR from inherited env, but the explicit flag is robust to
    # any future change in that default and to environments where the
    # variable doesn't propagate cleanly.
    if rag_dir is not None:
        cmd.extend(["--rag-dir", str(rag_dir)])
    logger.info(f"[RAG alignment] Running auto-rebuild: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, timeout=REBUILD_TIMEOUT_SECONDS,
                   cwd=str(repo_root))


def _run_validator_gate(profile: str, repo_root: Path) -> dict:
    """Import scripts/verify_mode_aware.py and run all validators.

    include_smoke=False: rebuild only changed profile content, so the
    code-level fixtures + smoke tests aren't load-bearing for the gate.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verify_mode_aware",
        repo_root / "scripts" / "verify_mode_aware.py",
    )
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    return harness.run_all_validators(profile, include_smoke=False)


# =============================================================================
# Snapshot / rollback / delete (mode-aware safe — paths only, no content reads)
# =============================================================================

def _snapshot_profile(rag_dir: Path, profile: str) -> dict:
    """Copy the three profile artifacts to .previous siblings.

    Returns the paths so rollback / delete can locate them. Idempotent:
    pre-existing .previous from a prior incomplete run is overwritten.
    """
    chroma_src = rag_dir / "chroma_db" / profile
    chroma_dst = rag_dir / "chroma_db" / f"{profile}.previous"
    graph_src = rag_dir / "graphs" / f"{profile}.json"
    graph_dst = rag_dir / "graphs" / f"{profile}.previous.json"
    md_src = rag_dir / "metadata" / f"{profile}.json"
    md_dst = rag_dir / "metadata" / f"{profile}.previous.json"

    if chroma_dst.exists():
        shutil.rmtree(chroma_dst)
    if chroma_src.exists():
        shutil.copytree(chroma_src, chroma_dst)
    if graph_src.exists():
        shutil.copy2(graph_src, graph_dst)
    if md_src.exists():
        shutil.copy2(md_src, md_dst)

    return {
        "chroma_src": chroma_src, "chroma_dst": chroma_dst,
        "graph_src": graph_src, "graph_dst": graph_dst,
        "md_src": md_src, "md_dst": md_dst,
    }


def _rollback_profile(rag_dir: Path, profile: str, snapshot_paths: dict,
                      *, reason: str) -> None:
    """Move broken artifacts to .failed_<ts>; restore snapshot to live paths."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    failed_chroma = rag_dir / "chroma_db" / f"{profile}.failed_{ts}"
    chroma_src = snapshot_paths["chroma_src"]
    chroma_dst = snapshot_paths["chroma_dst"]
    graph_src = snapshot_paths["graph_src"]
    graph_dst = snapshot_paths["graph_dst"]
    md_src = snapshot_paths["md_src"]
    md_dst = snapshot_paths["md_dst"]

    if chroma_src.exists():
        shutil.move(str(chroma_src), str(failed_chroma))
    if chroma_dst.exists():
        shutil.move(str(chroma_dst), str(chroma_src))
    if graph_dst.exists():
        # Move the broken live graph aside (best-effort)
        if graph_src.exists():
            shutil.move(str(graph_src),
                        str(rag_dir / "graphs" / f"{profile}.failed_{ts}.json"))
        shutil.move(str(graph_dst), str(graph_src))
    if md_dst.exists():
        if md_src.exists():
            shutil.move(str(md_src),
                        str(rag_dir / "metadata" / f"{profile}.failed_{ts}.json"))
        shutil.move(str(md_dst), str(md_src))

    logger.error(
        f"[RAG alignment] Rolled back {profile} (reason={reason}). "
        f"Failed artifacts at {failed_chroma}/ for forensics."
    )


def _delete_snapshot(snapshot_paths: dict) -> None:
    """Successful rebuild: discard the .previous backup."""
    if snapshot_paths["chroma_dst"].exists():
        shutil.rmtree(snapshot_paths["chroma_dst"])
    for p in (snapshot_paths["graph_dst"], snapshot_paths["md_dst"]):
        if p.exists():
            p.unlink()


# =============================================================================
# File-lock to prevent concurrent rebuilds
# =============================================================================

@contextlib.contextmanager
def _bump_lock(rag_dir: Path, *, wait_seconds: int = LOCK_WAIT_SECONDS):
    """Non-blocking flock with a polled wait (fcntl-only; macOS + Linux).

    On Windows the function falls back to a presence-check file (best-effort).
    """
    rag_dir.mkdir(parents=True, exist_ok=True)
    lock_path = rag_dir / ".bump.lock"
    try:
        import fcntl
        fp = open(lock_path, "w")
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    fp.close()
                    raise DriftHandlerError(
                        f"Another A2MC startup is already rebuilding the RAG "
                        f"(holding {lock_path}). Waited {wait_seconds}s. "
                        f"Either wait for it to finish or remove the lock file "
                        f"if no rebuild is actually running."
                    )
                time.sleep(0.5)
        try:
            yield
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            fp.close()
    except ImportError:
        # Windows fallback: presence-check file
        if lock_path.exists():
            raise DriftHandlerError(
                f"Lock file {lock_path} present (no fcntl on this platform). "
                f"Remove it if no rebuild is running."
            )
        lock_path.write_text(str(os.getpid()))
        try:
            yield
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


# =============================================================================
# Helpers
# =============================================================================

def _read_t3_threshold() -> int:
    """Read ``A2MC_RAG_T3_AUTO_DISTANCE`` env var, falling back to default."""
    raw = os.environ.get("A2MC_RAG_T3_AUTO_DISTANCE")
    if raw is None:
        return DEFAULT_T3_AUTO_DISTANCE
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            f"A2MC_RAG_T3_AUTO_DISTANCE={raw!r} is not an integer; "
            f"using default {DEFAULT_T3_AUTO_DISTANCE}."
        )
        return DEFAULT_T3_AUTO_DISTANCE
