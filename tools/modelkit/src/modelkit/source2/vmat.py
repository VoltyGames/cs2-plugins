"""csgo_complex .vmat materials: writing them and reading their keys."""

import os
import re

type FilePath = str | os.PathLike[str]

WHITE = "[1.000000 1.000000 1.000000 0.000000]"
DEFAULT_AO = "materials/default/default_ao.tga"
DEFAULT_NORMAL = "materials/default/default_normal.tga"
# A baked texture set's file suffix per channel: <stem>_<suffix>.png.
BAKED_SUFFIXES = {"color": "color", "normal": "normal", "roughness": "rough", "metalness": "metal"}


def write_vmat(
    path: FilePath,
    folder: str,
    color: str,
    rough: str,
    normal: str | None = None,
    metalness: float = 0.6,
    roughness: float = 0.55,
    glow_mask: str | None = None,
    glow: float = 1.0,
    opacity: float | None = None,
    cutout: str | None = None,
) -> FilePath:
    """Writes a material over textures in `folder`, e.g. "models/x/y/".

    `rough` is the addon path of a flat white roughness texture, scaled by `roughness`.
    `glow_mask` glows at `glow` times the colour where white; `opacity` makes it see-through
    glass; `cutout`, a mask, cuts holes where black and shows both faces, like a net.
    """
    flags, values = [], [("g_flMetalness", metalness), ("g_flRoughnessScaleFactor", roughness)]
    textures = {
        "TextureAmbientOcclusion": DEFAULT_AO,
        "TextureColor": folder + color,
        "TextureNormal": folder + normal if normal else DEFAULT_NORMAL,
        "TextureRoughness": rough,
    }
    if glow_mask:
        flags.append("F_SELF_ILLUM")
        values.append(("g_flSelfIllumScale", glow))
        textures["TextureSelfIllumMask"] = folder + glow_mask
    if opacity is not None:
        flags += ["F_TRANSLUCENT", "F_DO_NOT_CAST_SHADOWS"]
        values.append(("g_flOpacityScale", opacity))
        textures["TextureTranslucency"] = WHITE
    if cutout:
        flags += ["F_ALPHA_TEST", "F_RENDER_BACKFACES"]
        values.append(("g_flAlphaTestReference", 0.5))
        textures["TextureTranslucency"] = folder + cutout
    keys = [(flag, "1") for flag in flags] + [(k, f"{v:g}") for k, v in values]
    return write_layer(path, keys + [("g_vColorTint", WHITE), *sorted(textures.items())])


def write_baked_vmat(path: FilePath, folder: str, stem: str) -> FilePath:
    """Writes a material over the baked set <stem>_<suffix>.png in `folder`; no AO map, since
    the game shadows the model itself."""
    color, normal, rough, metal = (f"{folder}{stem}_{s}.png" for s in BAKED_SUFFIXES.values())
    keys = [
        ("F_METALNESS_TEXTURE", "1"),
        ("g_vColorTint", WHITE),
        ("TextureAmbientOcclusion", DEFAULT_AO),
        ("TextureColor", color),
        ("TextureMetalness", metal),
        ("TextureNormal", normal),
        ("TextureRoughness", rough),
    ]
    return write_layer(path, keys)


def write_layer(path: FilePath, keys: list[tuple[str, str]]) -> FilePath:
    body = "".join(f'\t"{k}"\t"{v}"\n' for k, v in [("shader", "csgo_complex.vfx"), *keys])
    with open(path, "w", newline="\n") as f:
        f.write(f'"Layer0"\n{{\n{body}}}\n')
    return path


def read_vmat(path: FilePath) -> dict[str, str]:
    """A .vmat's keys and values, such as {"TextureColor": "models/x/x_color.png"}."""
    with open(path, encoding="utf-8") as f:
        return dict(re.findall(r'^\s*"(\w+)"\s+"([^"]*)"', f.read(), re.MULTILINE))
