# SPDX-License-Identifier: MIT
"""A minimal triangle/quad mesh. Clean-up (welding, decimation, smoothing, hole filling) is deliberately not
reimplemented here — Blender's own Weld / Decimate / Smooth / Remesh modifiers do that (PLAN.md §2.3).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Mesh:
    vertices: np.ndarray                  # (N, 3) float32
    quads: np.ndarray                     # (M, 4) int32, each face wound counter-clockwise as seen from outside
    normals: np.ndarray | None = None     # (N, 3) float32, filled in by `compute_normals`

    @classmethod
    def empty(cls) -> "Mesh":
        return cls(np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int32))

    def __len__(self) -> int:
        return int(self.quads.shape[0])

    def triangles(self) -> np.ndarray:
        """Each quad split into two triangles — what Blender's `foreach_set` and every exporter ultimately want."""
        if len(self) == 0:
            return np.zeros((0, 3), np.int32)
        a, b, c, d = (self.quads[:, i] for i in range(4))
        return np.concatenate([np.stack([a, b, c], axis=1), np.stack([a, c, d], axis=1)])

    def signed_volume(self) -> float:
        tris = self.triangles()
        if len(tris) == 0:
            return 0.0
        v0, v1, v2 = self.vertices[tris[:, 0]], self.vertices[tris[:, 1]], self.vertices[tris[:, 2]]
        return float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0)

    def flipped(self) -> "Mesh":
        return Mesh(self.vertices, self.quads[:, ::-1].copy(), self.normals)

    def compute_normals(self) -> "Mesh":
        """Area-weighted face normals, averaged per vertex — smoothed further by Blender's own shading / modifiers."""
        normals = np.zeros_like(self.vertices)
        for tri in (self.quads[:, (0, 1, 2)], self.quads[:, (0, 2, 3)]):
            v0, v1, v2 = self.vertices[tri[:, 0]], self.vertices[tri[:, 1]], self.vertices[tri[:, 2]]
            face_normal = np.cross(v1 - v0, v2 - v0)
            for i in range(3):
                np.add.at(normals, tri[:, i], face_normal)
        lengths = np.linalg.norm(normals, axis=1)
        normals[lengths > 1e-20] /= lengths[lengths > 1e-20, None]
        self.normals = normals.astype(np.float32)
        return self
