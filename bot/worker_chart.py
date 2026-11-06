"""Dependency-free PNG line charts for the Python Cloudflare Worker."""

import math
import struct
import zlib
from datetime import datetime, timezone

FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "111", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    ".": ("000", "000", "000", "000", "010"),
    "-": ("000", "000", "111", "000", "000"),
    "/": ("001", "001", "010", "100", "100"),
    "(": ("001", "010", "010", "010", "001"),
    ")": ("100", "010", "010", "010", "100"),
}


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))


def render_chart(values, symbol="", period="", timestamps=()):
    prices = []
    for value in values:
        try:
            value = float(value)
            prices.append(value if math.isfinite(value) else None)
        except (TypeError, ValueError):
            prices.append(None)
    available = [value for value in prices if value is not None]
    if len(available) < 2:
        return None

    width, height = 640, 360
    left, right, top, bottom = 88, 620, 35, 320
    pixels = bytearray(bytes((15, 23, 42, 255)) * (width * height))

    def dot(x, y, color):
        x, y = round(x), round(y)
        if 0 <= x < width and 0 <= y < height:
            offset = (y * width + x) * 4
            pixels[offset : offset + 4] = bytes(color)

    def line(x1, y1, x2, y2, color):
        count = max(math.ceil(abs(x2 - x1)), math.ceil(abs(y2 - y1)), 1)
        for index in range(count + 1):
            dot(x1 + (x2 - x1) * index / count, y1 + (y2 - y1) * index / count, color)

    def text(value, x, y):
        cursor = x
        for char in str(value).upper():
            for dy, row in enumerate(FONT.get(char, ())):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        for sy in range(2):
                            for sx in range(2):
                                dot(cursor + dx * 2 + sx, y + dy * 2 + sy, (203, 213, 225, 255))
            cursor += 8

    low, high = min(available), max(available)
    if low == high:
        padding = max(abs(high) * 0.01, 0.01)
        low, high = low - padding, high + padding
    span = high - low
    text(f"{symbol} ({period})", 230, 10)
    for index in range(6):
        y = top + (bottom - top) * index / 5
        line(left, y, right, y, (51, 65, 85, 255))
        value = high - span * index / 5
        label = f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"
        text(label, max(0, left - len(label) * 8 - 5), y - 5)

    if timestamps:
        for timestamp, x in ((timestamps[0], left), (timestamps[-1], right - 80)):
            try:
                text(datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d"), x, bottom + 12)
            except (TypeError, ValueError, OSError, OverflowError):
                pass

    previous = None
    for index, value in enumerate(prices):
        if value is None:
            previous = None
            continue
        point = (left + index * (right - left) / (len(prices) - 1), bottom - (value - low) / span * (bottom - top))
        if previous:
            line(*previous, *point, (56, 189, 248, 255))
        previous = point

    rows = b"".join(b"\x00" + pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b"")
