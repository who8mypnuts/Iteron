# SPDX-License-Identifier: MIT
"""Mesh and point files: binary PLY (positions, optional normals and 8-bit colours, quads and triangles as they
are) and Wavefront OBJ (positions with colours, normals, faces)."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def write(path: Path, vertices: np.ndarray, faces: list[np.ndarray], colours: np.ndarray | None = None,
          normals: np.ndarray | None = None) -> Path:
    """Write by the file's suffix (`.ply` or `.obj`); `faces` are index arrays (quads, triangles…)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".ply":
        write_ply(path, vertices, faces, colours, normals)
    elif suffix == ".obj":
        write_obj(path, vertices, faces, colours, normals)
    else:
        raise ValueError(f"unknown mesh format {suffix!r} (use .ply or .obj)")
    return path


def _usable(normals: np.ndarray | None, count: int) -> np.ndarray | None:
    if normals is None or len(normals) != count or not np.isfinite(normals).all():
        return None
    return normals


def write_ply(path: Path, vertices, faces, colours=None, normals=None) -> None:
    vertices = np.asarray(vertices, dtype=np.float32)
    normals = _usable(normals, len(vertices))
    fields = [("x", "f4"), ("y", "f4"), ("z", "f4")]
    if normals is not None:
        fields += [("nx", "f4"), ("ny", "f4"), ("nz", "f4")]
    if colours is not None:
        fields += [("red", "u1"), ("green", "u1"), ("blue", "u1")]
    data = np.empty(len(vertices), dtype=np.dtype([(n, "<" + t) for n, t in fields]))
    data["x"], data["y"], data["z"] = vertices.T
    if normals is not None:
        data["nx"], data["ny"], data["nz"] = np.asarray(normals, dtype=np.float32).T
    if colours is not None:
        rgb = np.clip(np.asarray(colours)[:, :3] * 255.0 + 0.5, 0, 255).astype(np.uint8)
        data["red"], data["green"], data["blue"] = rgb.T
    faces = [np.asarray(f, dtype=np.int32) for f in faces if len(f)]
    types = {"f4": "float", "u1": "uchar"}
    header = ["ply", "format binary_little_endian 1.0", "comment made by Iteron", f"element vertex {len(vertices)}"]
    header += [f"property {types[t]} {n}" for n, t in fields]
    header += [f"element face {sum(len(f) for f in faces)}", "property list uchar int vertex_indices", "end_header"]
    with open(path, "wb") as out:
        out.write(("\n".join(header) + "\n").encode("ascii"))
        out.write(data.tobytes())
        for block in faces:
            rows = np.empty(len(block), dtype=np.dtype([("n", "u1"), ("i", "<i4", (block.shape[1],))]))
            rows["n"], rows["i"] = block.shape[1], block
            out.write(rows.tobytes())


def write_obj(path: Path, vertices, faces, colours=None, normals=None) -> None:
    vertices = np.asarray(vertices, dtype=np.float64)
    normals = _usable(normals, len(vertices))
    with open(path, "w", encoding="ascii") as out:
        out.write("# made by Iteron\n")
        table = np.hstack([vertices, np.asarray(colours)[:, :3]]) if colours is not None else vertices
        np.savetxt(out, table, fmt="v" + " %.6g" * table.shape[1])
        if normals is not None:
            np.savetxt(out, normals, fmt="vn %.5f %.5f %.5f")
        for block in faces:
            if len(block):
                ids = np.asarray(block, dtype=np.int64) + 1
                pattern = " ".join(["%d//%d" if normals is not None else "%d"] * ids.shape[1])
                columns = np.repeat(ids, 2, axis=1) if normals is not None else ids
                np.savetxt(out, columns, fmt="f " + pattern)


def read_ply_header(path: Path) -> dict[str, int]:
    """`{element: count}` from a PLY header (for tests and quick checks)."""
    counts = {}
    with open(path, "rb") as source:
        for raw in source:
            line = raw.decode("ascii").strip()
            if line.startswith("element"):
                _kw, name, count = line.split()
                counts[name] = int(count)
            if line == "end_header":
                break
    return counts
