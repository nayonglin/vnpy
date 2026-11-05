"""Draw exact-contract, signal-date-only loss charts for individual visual review."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "outputs/stage027_s44_2022_loss_forensics_v1"
FONT = "/System/Library/Fonts/Menlo.ttc"
REGULAR = ImageFont.truetype(FONT, 13)
HEADER = ImageFont.truetype(FONT, 17)
SIZE = 20
UP, DOWN = "#157d72", "#c85c36"
COLORS = {"ma5": "#5478cd", "ma10": "#a145b1", "ma20": "#202934"}


def render():
    rows = json.loads((OUT / "chart_inputs.json").read_text())
    for index in range(0, len(rows), SIZE):
        sheet = Image.new("RGB", (1320, 922), "#e7edf2")
        draw = ImageDraw.Draw(sheet)
        page = index // SIZE + 1
        draw.text((14, 8), f"S44 2022 losses | sheet {page:02d} | direction-adjusted weekly bars | MA5 blue / MA10 purple / MA20 dark", fill="#182532", font=HEADER)
        for offset, trade in enumerate(rows[index:index + SIZE]):
            column, row = offset % 5, offset // 5
            x, y = 8 + column * 263, 38 + row * 219
            draw.rounded_rectangle((x, y, x + 256, y + 210), radius=8, fill="white")
            side = trade["side"]
            title = f"{trade['cycle']}  {trade['contract'].split('.')[0]}  {'L' if side==1 else 'S'}  {trade['signal'][5:]}"
            draw.text((x+9, y+8), title, fill="#12222c", font=REGULAR)
            bars = trade["bars"]
            fields = ("high", "low", *COLORS)
            values = [side*bar[f] for bar in bars for f in fields if bar[f] is not None]
            low, high = min(values), max(values)
            bottom, top = y + 195, y + 31
            step = 16
            left = x + 20
            def coord(value):
                return bottom - (side * value - low) / (high - low) * (bottom - top)
            draw.rectangle((left + step * (len(bars)-2.5), top - 3, left + step * (len(bars)-.5), bottom + 4), fill="#fff1cf")
            for i, bar in enumerate(bars):
                tx = left + step*i
                if bar["close"] is None:
                    draw.text((tx-2, bottom-10), "·", fill="#aab7c0", font=REGULAR)
                    continue
                o, h, l, c = (coord(bar[f]) for f in ("open", "high", "low", "close"))
                color = UP if c < o else DOWN
                draw.line((tx, h, tx, l), fill=color, width=2)
                draw.rectangle((tx-4, min(o,c), tx+4, max(min(o,c)+1, max(o,c))), fill=color)
            for field, color in COLORS.items():
                for i in range(1, len(bars)):
                    a, b = bars[i-1][field], bars[i][field]
                    if a is not None and b is not None:
                        tx = left + step*i
                        draw.line((tx-step, coord(a), tx, coord(b)), fill=color, width=2)
        sheet.save(OUT / f"sheet_{page:02d}.png")


if __name__ == "__main__":
    render()
