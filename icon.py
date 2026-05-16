"""Dynamic tray icon generation using Pillow."""

from PIL import Image, ImageDraw


ICON_SIZE = 64


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    """Generate a solid-color circle icon."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=color,
    )
    return img


GREEN = (76, 175, 80)
YELLOW = (255, 193, 7)
RED = (244, 67, 54)


def get_green_icon() -> Image.Image:
    return _make_icon(GREEN)


def get_yellow_icon() -> Image.Image:
    return _make_icon(YELLOW)


def get_red_icon() -> Image.Image:
    return _make_icon(RED)
