"""Validate the native Windows icon payload and visible artwork sizing."""

from pathlib import Path

from PIL import Image

from connector.windows_assets import ICON_SIZES, write_windows_icons


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "bbs-icon.png"


def test_windows_icon_source_is_square_transparent_and_visibly_large() -> None:
    assert SOURCE.is_file()

    with Image.open(SOURCE) as image:
        rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bounds = alpha.getbbox()

    assert rgba.width == rgba.height
    assert bounds is not None
    assert all(alpha.getpixel(point) == 0 for point in (
        (0, 0),
        (rgba.width - 1, 0),
        (0, rgba.height - 1),
        (rgba.width - 1, rgba.height - 1),
    ))
    visible_width = bounds[2] - bounds[0]
    visible_height = bounds[3] - bounds[1]
    assert visible_width / rgba.width >= 0.85
    assert visible_height / rgba.height >= 0.70


def test_generated_ico_contains_required_native_sizes(tmp_path: Path) -> None:
    target_ico = tmp_path / "bbs.ico"
    target_png = tmp_path / "bbs-icon.png"

    write_windows_icons(SOURCE, target_ico, target_png)

    assert target_ico.is_file()
    assert target_png.is_file()
    with Image.open(target_ico) as icon:
        assert set(ICON_SIZES).issubset(
            {width for width, height in icon.info["sizes"] if width == height}
        )
    with Image.open(target_png) as tray_image:
        alpha = tray_image.convert("RGBA").getchannel("A")
        bounds = alpha.getbbox()
        assert bounds is not None
        assert (bounds[2] - bounds[0]) / tray_image.width >= 0.90


def test_windows_tray_loads_the_generated_square_asset() -> None:
    tray = (ROOT / "connector" / "tray_windows.py").read_text(encoding="utf-8")
    assert 'ICON = ROOT / "data" / "bbs-icon.png"' in tray
    assert 'ICON_FALLBACK = ROOT / "assets" / "bbs-icon.png"' in tray
