import numpy as np
import pytest
from numpy.typing import NDArray

from modelkit.blender import measure


def square(
    size: float, uv_max: tuple[float, float]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Two triangles covering a `size` square, mapped onto UVs (0, 0) to `uv_max`."""
    points = np.array(
        [[[0, 0, 0], [size, 0, 0], [size, size, 0]], [[0, 0, 0], [size, size, 0], [0, size, 0]]],
        dtype=float,
    )
    u, v = uv_max
    uvs = np.array([[[0, 0], [u, 0], [u, v]], [[0, 0], [u, v], [0, v]]], dtype=float)
    return points, uvs


def test_density_is_texels_per_unit_per_texture_pixel() -> None:
    points, uvs = square(64, (0.5, 0.5))
    # Half a 1024 texture over 64 units: 512 / 64 = 8 pixels a unit.
    assert measure.summarize(points, uvs)["density"] * 1024 == pytest.approx(8.0)


def test_fill_counts_stacked_islands_as_overlap() -> None:
    _, uvs = square(64, (0.5, 0.5))
    covered, overlap = measure.fill(np.concatenate([uvs, uvs]))
    assert covered == pytest.approx(0.25, abs=0.01)
    assert overlap == pytest.approx(2.0, abs=0.05)
