"""UV measurements on triangle arrays. numpy only, so tests run it outside Blender.

Texel density is texture pixels per unit of surface. Measured here per pixel of texture width,
it scales with the texture: density = `density` * sqrt(width * height).
"""

import numpy as np
from numpy.typing import NDArray

COVERAGE_GRID = 512

type Floats = NDArray[np.float64]


def triangle_areas(points: Floats) -> Floats:
    """Areas of (n, 3, 3) triangles."""
    return 0.5 * np.linalg.norm(
        np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]), axis=1
    )


def uv_areas(uvs: Floats) -> Floats:
    """Areas of (n, 3, 2) UV triangles."""
    d1, d2 = uvs[:, 1] - uvs[:, 0], uvs[:, 2] - uvs[:, 0]
    return 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])


def coverage(uvs: Floats, grid: int = COVERAGE_GRID) -> float:
    """The share of the 0-1 UV square the triangles cover, sampled at grid cell centres."""
    covered = np.zeros((grid, grid), bool)
    for a, b, c in uvs * grid:
        lo = np.maximum(np.floor(np.minimum(np.minimum(a, b), c)).astype(int), 0)
        hi = np.minimum(np.ceil(np.maximum(np.maximum(a, b), c)).astype(int), grid)
        if (hi <= lo).any():
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l1 + l2 <= 1 + 1e-6)
        covered[lo[1] : hi[1], lo[0] : hi[0]] |= inside
    return float(covered.mean())


def weighted_percentile(values: Floats, weights: Floats, share: float) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order]) / weights.sum()
    return float(values[order][min(np.searchsorted(cumulative, share), len(values) - 1)])


def fill(uvs: Floats) -> tuple[float, float]:
    """An atlas's coverage of the 0-1 square, and its UV area over that: above 1 means
    islands overlap, such as mirrored or stacked parts."""
    covered = coverage(uvs)
    return covered, float(uv_areas(uvs).sum() / max(covered, 1e-9))


def summarize(points: Floats, uvs: Floats) -> dict[str, float | int | bool]:
    """Density and spread for one material's triangles on one part.

    Density figures are per pixel of texture width and area-weighted: p10 and p90 bound the
    middle 80% of the surface. UVs inside the 0-1 square are an `atlas`, whose fill is measured
    across every part sharing it; tiling UVs report their `span` in repeats instead.
    """
    area = triangle_areas(points)
    area_uv = uv_areas(uvs)
    total = float(area.sum())
    solid = area > 1e-3
    per_face = np.sqrt(area_uv[solid] / area[solid])
    lo, hi = uvs.reshape(-1, 2).min(0), uvs.reshape(-1, 2).max(0)
    atlas = bool(lo.min() > -0.01 and hi.max() < 1.01)
    return {
        "triangles": len(points),
        "area": total,
        "density": float(np.sqrt(area_uv.sum() / total)) if total else 0.0,
        "p10": weighted_percentile(per_face, area[solid], 0.1) if solid.any() else 0.0,
        "p90": weighted_percentile(per_face, area[solid], 0.9) if solid.any() else 0.0,
        "zero_share": float(area[solid][per_face < 1e-6].sum() / total) if total else 0.0,
        "atlas": atlas,
        "span": float((hi - lo).max()),
    }
