"""Create Windows-native icon assets from the project PNG logo."""

from pathlib import Path

from PIL import Image


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "logo.png"
    target_dir = root / "data"
    target = target_dir / "bbs.ico"
    target_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGBA").save(
            target,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
