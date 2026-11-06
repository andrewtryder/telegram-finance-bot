from io import BytesIO

from PIL import Image

from bot.worker_chart import render_chart


def test_chart_is_valid_png_and_handles_missing_values():
    image = render_chart([123, 128, None, 126, 131], "AAPL", "1mo", [1735741800, 1735828200])
    with Image.open(BytesIO(image)) as png:
        png.load()
        assert png.size == (640, 360)
        assert png.mode == "RGBA"


def test_chart_requires_two_prices():
    assert render_chart([None, 1]) is None
