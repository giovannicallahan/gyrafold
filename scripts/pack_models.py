#!/usr/bin/env python3
"""Pack the atlas's 328 .glb models into two compressed files for fast loading.

Why: the brain page used to fetch 328 separate files (~54 MB). These packs hold the
same meshes in ~15 MB across two requests. The .glb files stay deployed as a
fallback for browsers that cannot decompress gzip streams.

Output (in viewer/public/models/):
  brain.<hash>.gfpk   models shown by default
  extras.<hash>.gfpk  skin and head/neck muscles (hidden until switched on)
  packs.json          which pack files to load, in order, with their sizes

Pack format, version 1 (the whole file is gzip-compressed):
  "GFPK" | uint32 version | uint32 json_length | json (UTF-8) | zero padding to 4 bytes
  json = {"models": [{"id", "v" (vertices), "i" (indices), "mn" [x,y,z], "sc" [x,y,z]}, ...]}
  then, for each model in order:
    positions: 3*v values, component-major (all x, then all y, then all z).
               Each is quantized to uint16 (value = mn + q*sc), delta-coded along
               the vertex order (mod 2^16), zigzag-coded, and stored as two byte
               planes: all low bytes, then all high bytes.
    indices:   i values, delta-coded, zigzag-coded as 32-bit, stored as four byte
               planes (lowest byte first).
Byte planes and delta coding make the data compress about 3.6x with plain gzip.
The decoder is parsePack() in viewer/public/atlas-viewer.html.

Run: python3 scripts/pack_models.py      (then bump VERSION in viewer/public/sw.js)
"""
import gzip
import hashlib
import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "viewer" / "public"
MODELS = PUBLIC / "models"


def read_glb(path):
    b = path.read_bytes()
    json_len = struct.unpack("<I", b[12:16])[0]
    gl = json.loads(b[20:20 + json_len])
    off = 20 + json_len
    bin_len = struct.unpack("<I", b[off:off + 4])[0]
    blob = b[off + 8:off + 8 + bin_len]
    assert len(gl["meshes"]) == 1 and len(gl["meshes"][0]["primitives"]) == 1, path
    prim = gl["meshes"][0]["primitives"][0]
    assert prim.get("mode", 4) == 4, path
    views = gl["bufferViews"]

    def accessor(i, dtype, width):
        a = gl["accessors"][i]
        v = views[a["bufferView"]]
        start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        return np.frombuffer(blob, dtype=dtype, count=a["count"] * width, offset=start)

    ia = gl["accessors"][prim["indices"]]
    idx_dtype = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32}[ia["componentType"]]
    idx = accessor(prim["indices"], idx_dtype, 1).astype(np.int64)
    pos = accessor(prim["attributes"]["POSITION"], np.float32, 3).reshape(-1, 3)
    return pos, idx


def zigzag(a, bits):
    a = a.astype(np.int64)
    return ((a << 1) ^ (a >> 63)) & ((1 << bits) - 1)


def planes(values, nbytes):
    raw = values.astype("<u%d" % nbytes).view(np.uint8).reshape(-1, nbytes)
    return b"".join(raw[:, k].tobytes() for k in range(nbytes))


def encode(pos, idx):
    mn = pos.min(axis=0).astype(np.float64)
    sc = np.maximum(pos.max(axis=0) - mn, 1e-6) / 65535.0
    q = np.clip(np.round((pos - mn) / sc), 0, 65535).astype(np.int64)   # (v, 3)
    body = []
    for c in range(3):
        d = np.diff(q[:, c], prepend=0)
        d = ((d + 32768) % 65536) - 32768           # wrap to int16
        body.append(zigzag(d, 16))
    body = planes(np.concatenate(body), 2)
    di = np.diff(idx, prepend=0)
    body += planes(zigzag(di, 32), 4)
    # what the decoder will rebuild, to check precision
    err = float(np.abs(q * sc + mn - pos).max())
    return body, mn.tolist(), sc.tolist(), err


def hidden_by_default(manifest):
    """Same rule as identifyHiddenModels() in atlas-viewer.html."""
    groups = {g["id"]: g for g in manifest.get("groups", [])}
    leafs = set()

    def collect(gid):
        g = groups.get(gid)
        if not g:
            leafs.add(gid)
            return
        for m in g.get("members", []):
            collect(m)

    collect("Head_and_Neck_Muscles")
    out = set()
    for mod in manifest["models"]:
        s0 = (mod.get("structures") or [None])[0]
        if s0 and (s0["atlas_id"] == "skin" or s0["atlas_id"] in leafs):
            out.add(mod["id"])
    return out


def build_pack(name, mods):
    header_models, chunks, worst = [], [], 0.0
    for mod in mods:
        pos, idx = read_glb(PUBLIC / mod["glb"])
        assert idx.max() < len(pos), mod["id"]
        body, mn, sc, err = encode(pos, idx)
        worst = max(worst, err)
        header_models.append({"id": mod["id"], "v": int(len(pos)), "i": int(len(idx)),
                              "mn": mn, "sc": sc})
        chunks.append(body)
    head = json.dumps({"models": header_models}, separators=(",", ":")).encode()
    head += b" " * (-len(head) % 4)
    raw = b"GFPK" + struct.pack("<II", 1, len(head)) + head + b"".join(chunks)
    data = gzip.compress(raw, compresslevel=9, mtime=0)
    digest = hashlib.sha256(data).hexdigest()[:10]
    fname = f"{name}.{digest}.gfpk"
    (MODELS / fname).write_bytes(data)
    return {"name": name, "url": f"./models/{fname}", "bytes": len(data),
            "models": len(mods)}, worst


def main():
    manifest = json.loads((PUBLIC / "atlas-manifest.json").read_text())
    hidden = hidden_by_default(manifest)
    brain = [m for m in manifest["models"] if m["id"] not in hidden]
    extras = [m for m in manifest["models"] if m["id"] in hidden]
    for old in MODELS.glob("*.gfpk"):
        old.unlink()
    packs, worst = [], 0.0
    for name, mods in (("brain", brain), ("extras", extras)):
        info, err = build_pack(name, mods)
        packs.append(info)
        worst = max(worst, err)
    (MODELS / "packs.json").write_text(json.dumps({"version": 1, "packs": packs}, indent=1) + "\n")
    total = sum(p["bytes"] for p in packs)
    for p in packs:
        print(f"{p['url']}: {p['models']} models, {p['bytes'] / 1e6:.1f} MB")
    print(f"total {total / 1e6:.1f} MB; largest position error {worst:.5f} (atlas units, mm)")


if __name__ == "__main__":
    main()
