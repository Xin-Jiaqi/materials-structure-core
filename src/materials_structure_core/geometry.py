"""Metric-aware geometry for a two-periodic row-vector lattice, in Angstrom."""
from __future__ import annotations

import itertools
import numpy as np


def reduced_plane_basis(lattice):
    """Return Gauss-reduced rows B and integer map U, B = U @ lattice[:2]."""
    cell = np.asarray(lattice, dtype=float)
    if cell.shape not in ((2, 3), (3, 3)) or not np.isfinite(cell).all():
        raise ValueError("lattice must contain two or three finite Cartesian rows")
    basis = cell[:2].copy()
    sv = np.linalg.svd(basis, compute_uv=False)
    if sv[-1] <= 1e-12 * sv[0]:
        raise ValueError("in-plane lattice is singular or numerically ill-conditioned")
    transform = np.eye(2, dtype=np.int64)
    for _ in range(128):
        if np.dot(basis[1], basis[1]) < np.dot(basis[0], basis[0]):
            basis = basis[[1, 0]]
            transform = transform[[1, 0]]
        multiple = int(np.rint(np.dot(basis[0], basis[1]) / np.dot(basis[0], basis[0])))
        if multiple == 0:
            return basis, transform
        if abs(multiple) > 10**9 or np.max(np.abs(transform)) > 10**12:
            raise ValueError("lattice reduction exceeds integer safety limit")
        basis[1] -= multiple * basis[0]
        transform[1] -= multiple * transform[0]
    raise ValueError("in-plane lattice reduction did not converge")


def minimum_image_in_plane(vectors, lattice, *, block_size=4096):
    """Return shortest vectors and integer images in the ORIGINAL a,b basis.

    out = vectors - images @ lattice[:2]. The third direction is never wrapped.
    A singular-value bound guarantees the finite search covers every improving
    image; reduction keeps this bound small. Tied images are deterministic.
    """
    value = np.asarray(vectors, dtype=float)
    if value.ndim < 1 or value.shape[-1] != 3 or not np.isfinite(value).all():
        raise ValueError("vectors must be finite with final dimension three")
    if not isinstance(block_size, int) or block_size < 1:
        raise ValueError("block_size must be a positive integer")
    basis, transform = reduced_plane_basis(lattice)
    inverse = np.linalg.pinv(basis)
    smin = np.linalg.svd(basis, compute_uv=False)[-1]
    flat = value.reshape(-1, 3)
    output = np.empty_like(flat)
    images = np.empty((len(flat), 2), dtype=np.int64)
    for start in range(0, len(flat), block_size):
        v = flat[start:start+block_size]
        q = v @ inverse
        if np.max(np.abs(q)) > 10**12:
            raise ValueError("periodic displacement exceeds integer safety limit")
        nearest = np.rint(q).astype(np.int64)
        fractional = q - nearest
        # Only the planar residual affects which image is closest.
        planar = fractional @ basis
        radius = np.linalg.norm(planar, axis=1) / smin + 1e-10
        lo = np.ceil(np.min(fractional - radius[:, None], axis=0)).astype(int)
        hi = np.floor(np.max(fractional + radius[:, None], axis=0)).astype(int)
        if np.prod(hi-lo+1) > 10000:
            raise ValueError("minimum-image search exceeds certified search budget")
        candidates = np.array(list(itertools.product(range(lo[0],hi[0]+1), range(lo[1],hi[1]+1))))
        residual = planar[:, None, :] - candidates @ basis
        best = np.argmin(np.sum(residual**2, axis=2), axis=1)
        selected = nearest + candidates[best]
        output[start:start+len(v)] = v - selected @ basis
        images[start:start+len(v)] = selected @ transform
    return output.reshape(value.shape), images.reshape(value.shape[:-1]+(2,))


def plane_frame(lattice):
    """Columns are orthonormal (e1,e2,normal), tied to the a,b plane."""
    cell = np.asarray(lattice, dtype=float)
    reduced_plane_basis(cell)  # validation
    e1 = cell[0] / np.linalg.norm(cell[0])
    normal = np.cross(cell[0], cell[1])
    normal /= np.linalg.norm(normal)
    if len(cell) == 3 and np.dot(normal, cell[2]) < 0:
        normal = -normal
    return np.column_stack((e1, np.cross(normal, e1), normal))
