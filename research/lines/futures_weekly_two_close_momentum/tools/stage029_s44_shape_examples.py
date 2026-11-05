"""Draw a reproducible visual review sheet of matched cases and near misses."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "outputs/stage029_s44_weekly_shapes_v1"
FONT = "/System/Library/Fonts/Menlo.ttc"
TEXT = ImageFont.truetype(FONT, 14)
HEADING = ImageFont.truetype(FONT, 20)
RULES = ("range_expansion", "compression_break", "strong_close", "disjoint_ranges")


def cases(rows, rule):
    early = [x for x in rows if x["entry"] < "2022"]
    late = [x for x in rows if x["entry"] >= "2023"]
    taken = set()
    for era, group in (("early", early), ("late", late), ("near miss", late)):
        for direction in ("多", "空"):
            for outcome in (True, False):
                pool = [x for x in group if x["direction"] == direction and (x["pnl"] > 0) == outcome
                        and ((rule in x["rules"]) == (era != "near miss")) and x["margins"][rule] is not None]
                if era == "late":
                    ordered = sorted(pool, key=lambda x: (abs(x["margins"][rule]), x["cycle"]))
                    chosen = ordered[len(ordered)//2]
                else:
                    chosen = min(pool, key=lambda x: (abs(x["margins"][rule]), x["cycle"]))
                assert chosen["cycle"] not in taken
                taken.add(chosen["cycle"])
                yield era, chosen


def render():
    rows = [x for x in json.loads((OUT / "atlas_data.json").read_text()) if x["arm"] == "S44"]
    evidence = []
    late = [row for row in rows if row["entry"] >= "2023" and "range_expansion" in row["rules"]]
    late.sort(key=lambda row: ("break_3w" not in row["rules"], row["entry"], row["cycle"]))
    groups = [(rule, rule, list(cases(rows, rule))) for rule in RULES]
    groups.extend((f"expansion_late_{i//12+1:02d}", "range_expansion",
                   [("break 3w" if "break_3w" in row["rules"] else "no break", row) for row in late[i:i+12]])
                  for i in range(0, len(late), 12))
    for filename, rule, group in groups:
        sheet = Image.new("RGB", (1312, 771), "#e8eef3")
        draw = ImageDraw.Draw(sheet)
        draw.text((16, 8), f"{filename} | S44 exact contract | green = along trade | last 2 weeks shaded", font=HEADING, fill="#182532")
        for index, (era, trade) in enumerate(group):
            evidence.append(dict(sheet=filename, rule=rule, set=era, cycle=trade["cycle"], matched=rule in trade["rules"],
                                 pnl=trade["pnl"], margin=trade["margins"][rule]))
            x, y = 8 + (index % 4)*326, 42 + (index//4)*242
            draw.rounded_rectangle((x, y, x+318, y+231), radius=8, fill="white")
            direction = "L" if trade["direction"] == "多" else "S"
            draw.text((x+10, y+9), f"{trade['cycle']}  {trade['contract']}  {direction}  {trade['signal']}", font=TEXT, fill="#182532")
            draw.text((x+10, y+29), f"{era:9} PnL {trade['pnl']:+,.0f}   score {trade['margins'][rule]:+.3f}",
                      font=TEXT, fill="#157d72" if trade["pnl"] > 0 else "#a34430")
            bars = trade["bars"]
            top = max(bar[1] for bar in bars if bar[1] is not None)
            floor = min(bar[2] for bar in bars if bar[2] is not None)
            def py(value):
                return y + 219 - 162 * (value-floor)/(top-floor)
            draw.rectangle((x+238, y+53, x+296, y+221), fill="#fff1cf")
            for i, (opening, high, low, close) in enumerate(bars):
                if opening is None:
                    continue
                cx = x + 24 + 28*i
                color = "#157d72" if close >= opening else "#c85c36"
                draw.line((cx, py(high), cx, py(low)), fill=color, width=2)
                draw.rectangle((cx-6, py(max(close,opening)), cx+6, max(py(min(close,opening)), py(max(close,opening))+1)), fill=color)
        sheet.save(OUT / f"examples_{filename}.png")
    (OUT / "visual_examples.json").write_text(json.dumps(evidence, indent=2)+"\n")


if __name__ == "__main__":
    render()
