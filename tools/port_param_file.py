#!/usr/bin/env python3
"""Port a calibrated parameter file across model (e.g. FATES API) versions.

Version-agnostic and format-agnostic: reads a SOURCE param file (an established, site-tuned
prior-version file) and a TARGET TEMPLATE (the new version's default), and writes a new file
in the target's format+structure carrying the source's tuned values for every parameter that
exists in both — with per-PFT (or any per-entity) parameters remapped by **functional identity**,
never by raw index/position.

WHY (doctrine — do not restate here, read the memory): building a new-version base file by
porting site-tuned prior values (not the generic upstream default) is the rule, and the sharp
edge is NON-calibrated params. See auto-memory `feedback_port_tuned_base_param_file_across_versions`
and `feedback_verify_pft_identity_across_versions`. This tool is only the mechanics.

Genericity:
  * No hardcoded versions, PFT indices, or parameter lists.
  * Formats auto-detected (`.nc`/`.nc4`/`.cdf` netCDF, `.json` FATES JSON) via detect_format().
    Output format = the TARGET template's format. (For `.cdl` text, `ncgen -o x.nc x.cdl` first.)
  * The per-entity identity map is DERIVED by matching the identity variable's names
    (default `fates_pftname`) between source and target, then OVERRIDDEN by an explicit
    `--map` for repurposed slots (e.g. api-31 repurposed generic extratrop-shrub slots for
    arctic shrubs, so name-matching is wrong there — you MUST pass --map for those).
  * The entity dimension to remap (`--pft-dim`, default `fates_pft`) and the identity name
    variable (`--id-var`, default `fates_pftname`) are configurable, so as the model evolves
    (or for a different model) you retarget without editing the tool.

Usage:
  # inspect the identity map that WOULD be used (always do this first)
  python tools/port_param_file.py identity --source OLD --target NEW [--map 7:10,9:11,10:12]

  # port (writes NEW-format file carrying OLD's tuned values)
  python tools/port_param_file.py port --source OLD --target NEW --out PORTED \
      --map 7:10,9:11,10:12 [--params-file names.txt]

  # verify the remapped entity slots in PORTED equal the source
  python tools/port_param_file.py verify --source OLD --ported PORTED --map 7:10,9:11,10:12
"""
import sys, os, json, argparse, shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modify_fates_parameters import detect_format  # 'json' | 'netcdf', by ext + magic bytes


# ----------------------------------------------------------------------------- readers
def _decode_names(char_var):
    """Decode a netCDF char-matrix name variable (n_entity x strlen), masked-safe."""
    out = []
    for row in char_var:
        s = ""
        for c in row:
            if np.ma.is_masked(c):
                continue
            s += c.decode() if isinstance(c, (bytes, np.bytes_)) else str(c)
        out.append(s.strip())
    return out


def load_params(path):
    """Return (fmt, P) where P maps name -> {'dims': [...], 'arr': np.ndarray|scalar,
    'numeric': bool}. fmt is 'json' or 'netcdf'."""
    fmt = detect_format(path)
    P = {}
    if fmt == "json":
        doc = json.load(open(path))
        for name, node in doc["parameters"].items():
            dims = node.get("dims", [])
            data = node.get("data")
            try:
                arr = np.array(data, dtype=float)
                numeric = True
            except (ValueError, TypeError):
                arr = np.array(data, dtype=object)
                numeric = False
            P[name] = {"dims": list(dims), "arr": arr, "numeric": numeric}
    else:
        import netCDF4 as nc
        ds = nc.Dataset(path)
        for name, var in ds.variables.items():
            dims = list(var.dimensions)
            if var.dtype.kind in ("S", "U"):
                P[name] = {"dims": dims, "arr": np.array(var[:], dtype=object), "numeric": False}
            else:
                P[name] = {"dims": dims, "arr": np.array(var[:], dtype=float), "numeric": True}
        ds.close()
    return fmt, P


def load_names(path, id_var):
    """Read the identity name list (e.g. fates_pftname) from either format."""
    fmt = detect_format(path)
    if fmt == "json":
        return list(json.load(open(path))["parameters"][id_var]["data"])
    import netCDF4 as nc
    ds = nc.Dataset(path)
    names = _decode_names(ds.variables[id_var][:])
    ds.close()
    return names


# ------------------------------------------------------------------- identity mapping
def build_identity_map(src_names, tgt_names, override=None):
    """Return (map0, report) where map0 = {src_idx0: tgt_idx0}. Auto-match by exact name,
    then apply the 1-based `override` string 's1:t1,s2:t2' (override wins). Report lists each
    pair + how it was resolved so a human can eyeball the functional correctness."""
    auto = {}
    tgt_by_name = {}
    for j, n in enumerate(tgt_names):
        tgt_by_name.setdefault(n, j)
    for i, n in enumerate(src_names):
        if n in tgt_by_name:
            auto[i] = tgt_by_name[n]
    ov = {}
    if override:
        for pair in override.split(","):
            s, t = pair.split(":")
            ov[int(s) - 1] = int(t) - 1  # user-facing 1-based -> 0-based
    m = dict(auto)
    m.update(ov)  # override wins
    lines = []
    for s in sorted(m):
        t = m[s]
        how = "OVERRIDE" if s in ov else ("name-match" if auto.get(s) == t else "?")
        sn = src_names[s] if s < len(src_names) else "?"
        tn = tgt_names[t] if t < len(tgt_names) else "?"
        flag = "" if (how == "OVERRIDE" or sn == tn) else "  <-- NAME MISMATCH, confirm functional intent"
        lines.append(f"  src[{s+1:2d}] {sn:38s} -> tgt[{t+1:2d}] {tn:38s} [{how}]{flag}")
    return m, "\n".join(lines)


# -------------------------------------------------------------------------- port core
def _move_last(arr, dims, dim):
    return np.moveaxis(arr, dims.index(dim), -1)


def port(source, target, out, pft_dim, id_var, override, params_file=None, verbose=True):
    sfmt, S = load_params(source)
    tfmt, T = load_params(target)
    src_names, tgt_names = load_names(source, id_var), load_names(target, id_var)
    m0, report = build_identity_map(src_names, tgt_names, override)
    if verbose:
        print(f"[identity map] {id_var}  ({len(m0)} entities)\n{report}\n")

    restrict = None
    if params_file:
        restrict = set(l.strip() for l in open(params_file) if l.strip() and not l.startswith("#"))

    # start the output from the TARGET (its structure/defaults), overwrite transferred params
    new_arr = {}  # name -> np.ndarray to write back
    n_sc = n_pf = 0
    skipped, only_src, only_tgt = [], [], []
    for name, tnode in T.items():
        if name not in S:
            if tnode["numeric"]:
                only_tgt.append(name)
            continue
        if not (tnode["numeric"] and S[name]["numeric"]):
            continue
        if restrict is not None and name not in restrict:
            continue
        sdims, sarr = S[name]["dims"], S[name]["arr"]
        tdims, tarr = tnode["dims"], tnode["arr"].copy()
        if pft_dim in tdims and pft_dim in sdims:
            tl = _move_last(tarr, tdims, pft_dim)          # (..., n_tgt)
            sl = _move_last(sarr, sdims, pft_dim)          # (..., n_src)
            if tl.shape[:-1] != sl.shape[:-1]:
                skipped.append((name, f"non-entity shape {tl.shape[:-1]} != {sl.shape[:-1]}"))
                continue
            for s, t in m0.items():
                if s < sl.shape[-1] and t < tl.shape[-1]:
                    tl[..., t] = sl[..., s]
            new_arr[name] = np.moveaxis(tl, -1, tdims.index(pft_dim))
            n_pf += 1
        elif pft_dim in tdims or pft_dim in sdims:
            skipped.append((name, f"entity-dim only on one side (src={sdims}, tgt={tdims})"))
        elif np.asarray(sarr).size == np.asarray(tarr).size:
            # scalar / non-entity, same element count: copy source into the target's shape
            # (size-match, not shape-match, so nc's () and json's (1,) scalars agree)
            new_arr[name] = np.asarray(sarr, dtype=float).reshape(np.asarray(tarr).shape)
            n_sc += 1
        else:                                                # non-entity dim changed length: don't force
            skipped.append((name, f"non-entity size {np.asarray(sarr).size} != {np.asarray(tarr).size}"))
    only_src = [n for n in S if n not in T and S[n]["numeric"]]

    _write(target, tfmt, out, new_arr)
    if verbose:
        print(f"[port] transferred {n_sc} scalar/non-entity + {n_pf} per-{pft_dim} params")
        print(f"[port] kept TARGET default: {len(only_tgt)} target-only params (e.g. {sorted(only_tgt)[:5]})")
        print(f"[port] dropped: {len(only_src)} source-only params (e.g. {sorted(only_src)[:5]})")
        if skipped:
            print(f"[port] SKIPPED {len(skipped)} (shape/dim mismatch): {skipped[:5]}")
        print(f"[port] wrote {out} ({tfmt})")
    return {"scalar": n_sc, "per_entity": n_pf, "target_only": len(only_tgt),
            "source_only": len(only_src), "skipped": skipped}


def _write(target, tfmt, out, new_arr):
    if tfmt == "json":
        doc = json.load(open(target))
        for name, arr in new_arr.items():
            node = doc["parameters"][name]
            node["data"] = arr.tolist() if arr.ndim > 0 else float(arr)
        json.dump(doc, open(out, "w"), indent=1)
    else:
        import netCDF4 as nc
        shutil.copy2(target, out)
        ds = nc.Dataset(out, "r+")
        for name, arr in new_arr.items():
            ds.variables[name][...] = arr
        ds.close()


# ------------------------------------------------------------------------------ verify
def verify(source, ported, pft_dim, id_var, override, n_check=6, verbose=True):
    _, S = load_params(source)
    _, Pp = load_params(ported)
    src_names, prt_names = load_names(source, id_var), load_names(ported, id_var)
    m0, _ = build_identity_map(src_names, prt_names, override)
    checked = ok = 0
    fails = []
    for name in S:
        if checked >= n_check and not fails:
            break
        if name not in Pp or not (S[name]["numeric"] and Pp[name]["numeric"]):
            continue
        sdims, pdims = S[name]["dims"], Pp[name]["dims"]
        if pft_dim not in sdims or pft_dim not in pdims:
            continue
        sl = _move_last(S[name]["arr"], sdims, pft_dim)
        pl = _move_last(Pp[name]["arr"], pdims, pft_dim)
        if sl.shape[:-1] != pl.shape[:-1]:
            continue
        checked += 1
        for s, t in m0.items():
            if not np.allclose(np.asarray(sl[..., s], float), np.asarray(pl[..., t], float),
                               rtol=0, atol=1e-9, equal_nan=True):
                fails.append((name, s + 1, t + 1))
        ok += 1
    if verbose:
        if fails:
            print(f"[verify] FAIL — {len(fails)} mismatched slots: {fails[:8]}")
        else:
            print(f"[verify] OK — {ok} per-{pft_dim} params checked; all mapped slots equal source")
    return not fails


# -------------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Port a calibrated param file across model/API versions.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(argument_default=argparse.SUPPRESS, add_help=False)
    common.add_argument("--pft-dim", default="fates_pft", help="entity dim to remap (default fates_pft)")
    common.add_argument("--id-var", default="fates_pftname", help="identity name var (default fates_pftname)")
    common.add_argument("--map", dest="override", default=None,
                        help="1-based src:tgt overrides, comma-sep (e.g. 7:10,9:11,10:12)")

    pi = sub.add_parser("identity", parents=[common], help="print the identity map only")
    pi.add_argument("--source", required=True); pi.add_argument("--target", required=True)

    pp = sub.add_parser("port", parents=[common], help="port source values onto target template")
    pp.add_argument("--source", required=True); pp.add_argument("--target", required=True)
    pp.add_argument("--out", required=True)
    pp.add_argument("--params-file", default=None, help="restrict transfer to these param names (one/line)")

    pv = sub.add_parser("verify", parents=[common], help="verify remapped slots match source")
    pv.add_argument("--source", required=True); pv.add_argument("--ported", required=True)

    a = ap.parse_args()
    pft_dim = getattr(a, "pft_dim", "fates_pft")
    id_var = getattr(a, "id_var", "fates_pftname")
    override = getattr(a, "override", None)
    if a.cmd == "identity":
        m0, rep = build_identity_map(load_names(a.source, id_var), load_names(a.target, id_var), override)
        print(f"identity map on {id_var} ({len(m0)} entities):\n{rep}")
    elif a.cmd == "port":
        r = port(a.source, a.target, a.out, pft_dim, id_var, override, getattr(a, "params_file", None))
        sys.exit(0 if r["per_entity"] or r["scalar"] else 1)
    elif a.cmd == "verify":
        sys.exit(0 if verify(a.source, a.ported, pft_dim, id_var, override) else 2)


if __name__ == "__main__":
    main()
