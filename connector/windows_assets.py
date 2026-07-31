"""Create tightly framed Windows-native icon assets from the project logo."""

from math import ceil
from pathlib import Path

from PIL import Image

ICON_SIZES = (16, 20, 24, 32, 48, 256)
VISIBLE_WIDTH_RATIO = 0.94


def prepare_icon(image: Image.Image) -> Image.Image:
    """Crop transparent padding and center the artwork on a square canvas."""
    rgba = image.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("The Windows icon source contains no visible pixels.")

    artwork = rgba.crop(bounds)
    canvas_size = ceil(max(artwork.size) / VISIBLE_WIDTH_RATIO)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    position = (
        (canvas_size - artwork.width) // 2,
        (canvas_size - artwork.height) // 2,
    )
    canvas.alpha_composite(artwork, position)
    return canvas


def write_windows_icons(
    source: Path,
    target_ico: Path,
    target_png: Path,
) -> None:
    target_ico.parent.mkdir(parents=True, exist_ok=True)
    target_png.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        prepared = prepare_icon(image)
    prepared.save(target_png, format="PNG", optimize=True)
    prepared.save(
        target_ico,
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "assets" / "bbs-icon.png"
    target_dir = root / "data"
    target_ico = target_dir / "bbs.ico"
    target_png = target_dir / "bbs-icon.png"
    write_windows_icons(source, target_ico, target_png)
    print(target_ico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
