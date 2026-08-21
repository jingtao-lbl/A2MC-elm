#!/usr/bin/env python3
"""
Derived-parameter transforms for the A2MC parameter list (scoping: dev_logs/20260710a).

A **derived-parameter group** lets the Morris sampler vary *virtual coordinates* that map,
by a transform applied at parameter-file-write time, to one or more *native* FATES params —
so a set of constrained natives can be sampled without infeasible box corners and WITHOUT any
model-source change. Each virtual coordinate is still one param-list row = one Morris column
(the docs/37 invariant holds); the transform expands it into native writes in the generator.

First (and motivating) group: **seed_repro_split** — FATES requires
`fates_recruit_seed_alloc + fates_recruit_seed_alloc_mature <= 1` per PFT
(`PRTParamsFATESMod.F90:722`, fatal). Sampling the two natives independently produces
`sum > 1` corners (→ FATES ENDRUN, or the silent code clamp we reverted). Instead sample:

    seed_repro_fraction  in [T_lo, T_hi] subset of [0,1]   # mature-plant total repro fraction (= model repro_fraction)
    seed_alloc_fraction  in [0, 1]                          # share of the total that is the base allocation

and derive, at write time:

    fates_recruit_seed_alloc        = seed_alloc_fraction        * seed_repro_fraction
    fates_recruit_seed_alloc_mature = (1 - seed_alloc_fraction)  * seed_repro_fraction

Both natives are then >= 0 and sum to `seed_repro_fraction <= 1` for the WHOLE Morris box —
feasible *by construction* (see `certify_bounds`), so the FATES fatal check is statically
unreachable from A2MC sampling.

Conventions
-----------
- A virtual coordinate name does NOT carry the `fates_` prefix (real params always do);
  membership in a registered group is the authoritative test (`is_virtual_coord`).
- Native write targets ARE real `fates_` names; they must NOT also appear as their own
  param-list rows (the validator enforces this).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

_TOL = 1e-9


@dataclass(frozen=True)
class DerivedTransform:
    """One derived-parameter group: virtual coords -> native FATES writes."""
    group: str
    coords: Tuple[str, ...]                                   # virtual sampling-coordinate names (doc order)
    writes: Dict[str, Callable[[Dict[str, float]], float]]    # native fates_name -> f(coord_values) -> value
    inverse: Callable[[Dict[str, float]], Dict[str, float]]   # native values -> coord values (for authoring defaults)
    certify_bounds: Callable[[Dict[str, float], Dict[str, float]], Tuple[bool, str]]  # (lo, hi) -> (all-points-feasible?, msg)
    point_feasible: Callable[[Dict[str, float]], Tuple[bool, str]]                    # native values -> (feasible?, msg)
    description: str = ""

    def native_names(self) -> Tuple[str, ...]:
        return tuple(self.writes.keys())

    def apply(self, coord_values: Dict[str, float], *, validate: bool = True) -> Dict[str, float]:
        """Compute the native param values from the sampled coord values.
        Raises ValueError if a coord is missing or (validate) the output is infeasible."""
        missing = [c for c in self.coords if c not in coord_values]
        if missing:
            raise ValueError(f"{self.group}: missing coord value(s) {missing}; have {sorted(coord_values)}")
        out = {name: float(fn(coord_values)) for name, fn in self.writes.items()}
        if validate:
            ok, msg = self.point_feasible(out)
            if not ok:
                raise ValueError(f"{self.group}: infeasible transform output ({msg}) from {coord_values}")
        return out

    def coord_defaults(self, native_values: Dict[str, float]) -> Dict[str, float]:
        """Virtual-coord defaults that reproduce the given native (base-file) values."""
        return self.inverse(native_values)


# --------------------------------------------------------------------------- #
# Group: seed_repro_split
# --------------------------------------------------------------------------- #
_SEED_ALLOC = "fates_recruit_seed_alloc"
_SEED_ALLOC_MATURE = "fates_recruit_seed_alloc_mature"
_REPRO = "seed_repro_fraction"
_SHARE = "seed_alloc_fraction"


def _seed_inverse(n: Dict[str, float]) -> Dict[str, float]:
    sa, sam = n[_SEED_ALLOC], n[_SEED_ALLOC_MATURE]
    total = sa + sam
    share = (sa / total) if total > 0.0 else 0.0   # guard: total == 0 -> share 0 (both natives 0)
    return {_REPRO: total, _SHARE: share}


def _seed_certify_bounds(lo: Dict[str, float], hi: Dict[str, float]) -> Tuple[bool, str]:
    """Static certificate: if every sampled point stays feasible, `sum <= 1` can never trip."""
    reasons = []
    if not (lo[_SHARE] >= -_TOL and hi[_SHARE] <= 1.0 + _TOL):
        reasons.append(f"{_SHARE} bounds must be within [0,1] (got [{lo[_SHARE]}, {hi[_SHARE]}])")
    if not (lo[_REPRO] >= -_TOL and hi[_REPRO] <= 1.0 + _TOL):
        reasons.append(f"{_REPRO} bounds must be within [0,1] (got [{lo[_REPRO]}, {hi[_REPRO]}])")
    if reasons:
        return False, "; ".join(reasons)
    return True, f"sum({_SEED_ALLOC}, {_SEED_ALLOC_MATURE}) <= 1 guaranteed for all sampled points"


def _seed_point_feasible(n: Dict[str, float]) -> Tuple[bool, str]:
    vals = list(n.values())
    if any(v < -_TOL for v in vals):
        return False, "a component < 0"
    s = sum(vals)
    if s > 1.0 + _TOL:
        return False, f"sum={s:.6f} > 1"
    return True, "ok"


_SEED_REPRO_SPLIT = DerivedTransform(
    group="seed_repro_split",
    coords=(_REPRO, _SHARE),
    writes={
        _SEED_ALLOC:        lambda c: c[_SHARE] * c[_REPRO],
        _SEED_ALLOC_MATURE: lambda c: (1.0 - c[_SHARE]) * c[_REPRO],
    },
    inverse=_seed_inverse,
    certify_bounds=_seed_certify_bounds,
    point_feasible=_seed_point_feasible,
    description=("Split the mature-plant reproductive fraction (seed_repro_fraction) into the base "
                "fates_recruit_seed_alloc and the mature bonus fates_recruit_seed_alloc_mature; "
                "feasible (sum<=1) by construction."),
)


# --------------------------------------------------------------------------- #
# Registry + lookups
# --------------------------------------------------------------------------- #
DERIVED_TRANSFORMS: Dict[str, DerivedTransform] = {
    _SEED_REPRO_SPLIT.group: _SEED_REPRO_SPLIT,
}

COORD_TO_GROUP: Dict[str, str] = {c: g for g, t in DERIVED_TRANSFORMS.items() for c in t.coords}
NATIVE_TO_GROUP: Dict[str, str] = {n: g for g, t in DERIVED_TRANSFORMS.items() for n in t.native_names()}

# Registry integrity: coords and native targets must be disjoint, and each unique across groups.
_seen_c: Dict[str, str] = {}
for _g, _t in DERIVED_TRANSFORMS.items():
    for _c in _t.coords:
        if _c in _seen_c:
            raise ValueError(f"virtual coord {_c!r} claimed by both {_seen_c[_c]!r} and {_g!r}")
        _seen_c[_c] = _g
_seen_n: Dict[str, str] = {}
for _g, _t in DERIVED_TRANSFORMS.items():
    for _n in _t.native_names():
        if _n in _seen_n:
            raise ValueError(f"native target {_n!r} written by both {_seen_n[_n]!r} and {_g!r}")
        _seen_n[_n] = _g
_overlap = set(COORD_TO_GROUP) & set(NATIVE_TO_GROUP)
if _overlap:
    raise ValueError(f"name(s) are both virtual coord and native target: {sorted(_overlap)}")


def is_virtual_coord(name: str) -> bool:
    """True iff `name` is a registered virtual sampling coordinate."""
    return name in COORD_TO_GROUP


def group_for_coord(name: str) -> Optional[str]:
    return COORD_TO_GROUP.get(name)


def transform_for_coord(name: str) -> Optional[DerivedTransform]:
    g = COORD_TO_GROUP.get(name)
    return DERIVED_TRANSFORMS[g] if g else None


def virtual_coords() -> set:
    return set(COORD_TO_GROUP)


def native_targets() -> set:
    return set(NATIVE_TO_GROUP)


if __name__ == "__main__":
    for g, t in DERIVED_TRANSFORMS.items():
        print(f"[{g}] coords={t.coords} -> natives={t.native_names()}")
        print(f"    {t.description}")
