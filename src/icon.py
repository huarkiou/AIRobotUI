"""Dynamic tray icon generation using Pillow."""

import os

from PIL import Image, ImageDraw

ICON_SIZE = 64
_STROKE = 6
_GLOW = 2


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    """Generate a modern hollow ring icon with subtle glow."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 6
    x1, y1 = margin, margin
    x2, y2 = ICON_SIZE - margin, ICON_SIZE - margin

    # Outer glow ring (larger, semi-transparent)
    glow_color = (*color, 60)
    draw.ellipse(
        [x1, y1, x2, y2],
        outline=glow_color,
        width=_STROKE + _GLOW,
    )

    # Main ring
    draw.ellipse(
        [x1, y1, x2, y2],
        outline=color,
        width=_STROKE,
    )

    # Inner highlight (top-left arc, lighter)
    r, g, b = color
    highlight = (min(r + 60, 255), min(g + 60, 255), min(b + 60, 255), 100)
    draw.arc(
        [x1 + 2, y1 + 2, x2 - 2, y2 - 2],
        start=200,
        end=340,
        fill=highlight,
        width=_STROKE,
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


def get_app_icon() -> Image.Image:
    """Return a blue app icon for window title bars (64x64)."""
    return _make_icon((33, 150, 243))


def save_ico(path: str) -> None:
    """Save the blue app icon as a multi-resolution .ico file for taskbar."""
    icon = get_app_icon()
    icon.save(path, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
