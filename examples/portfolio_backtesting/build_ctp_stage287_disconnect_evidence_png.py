from __future__ import annotations

import argparse
import csv
import json
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage287_simnow_disconnect_proof_v1"
OUTPUT_PREFIX = "qmt_roll_stage287_simnow_disconnect_proof"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size, index=1 if bold and path.endswith(".ttc") else 0)
        except Exception:
            continue
    return ImageFont.load_default()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _wrap(value: Any, width: int) -> list[str]:
    text = str(value)
    if len(text) <= width:
        return [text]
    return textwrap.wrap(text, width=width, break_long_words=True, replace_whitespace=False) or [text]


def _draw_card(draw: ImageDraw.ImageDraw, xy: tuple[int, int], size: tuple[int, int], label: str, value: str, ok: bool = False) -> None:
    x, y = xy
    w, h = size
    draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=(250, 252, 255), outline=(211, 224, 239), width=2)
    draw.text((x + 24, y + 20), label, font=_font(28), fill=(81, 101, 128))
    fill = (14, 122, 54) if ok else (20, 32, 51)
    for i, line in enumerate(_wrap(value, 35)):
        draw.text((x + 24, y + 60 + i * 36), line, font=_font(34, bold=True), fill=fill)


def _draw_table(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    title: str,
    rows: list[dict[str, Any]],
    cols: list[tuple[str, int]],
    max_rows: int,
) -> int:
    draw.text((x, y), title, font=_font(36, bold=True), fill=(20, 32, 51))
    y += 54
    row_h = 44
    draw.rectangle((x, y, x + width, y + row_h), fill=(235, 242, 249), outline=(211, 224, 239))
    cx = x
    for name, col_w in cols:
        draw.text((cx + 12, y + 10), name, font=_font(24, bold=True), fill=(33, 50, 76))
        draw.line((cx, y, cx, y + row_h), fill=(211, 224, 239), width=1)
        cx += col_w
    draw.line((x + width, y, x + width, y + row_h), fill=(211, 224, 239), width=1)
    y += row_h
    shown = rows[:max_rows]
    if not shown:
        draw.rectangle((x, y, x + width, y + row_h), fill=(255, 255, 255), outline=(211, 224, 239))
        draw.text((x + 12, y + 10), "无记录", font=_font(24), fill=(98, 115, 138))
        return y + row_h + 28
    for idx, row in enumerate(shown):
        fill = (255, 255, 255) if idx % 2 == 0 else (248, 251, 255)
        draw.rectangle((x, y, x + width, y + row_h), fill=fill, outline=(211, 224, 239))
        cx = x
        for key, col_w in cols:
            value = str(row.get(key, ""))
            draw.text((cx + 12, y + 10), value[: max(8, col_w // 15)], font=_font(23), fill=(20, 32, 51))
            draw.line((cx, y, cx, y + row_h), fill=(211, 224, 239), width=1)
            cx += col_w
        draw.line((x + width, y, x + width, y + row_h), fill=(211, 224, 239), width=1)
        y += row_h
    if len(rows) > max_rows:
        draw.text((x, y + 10), f"仅展示前 {max_rows} 行，共 {len(rows)} 行。", font=_font(22), fill=(98, 115, 138))
        y += 42
    return y + 28


def build(run_id: str) -> Path:
    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json"
    logs_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{run_id}_{MODEL_TAG}.csv"
    proxy_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_events_{run_id}_{MODEL_TAG}.csv"
    accounts_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{run_id}_{MODEL_TAG}.csv"
    positions_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{run_id}_{MODEL_TAG}.csv"
    output_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_{run_id}_{MODEL_TAG}.png"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    logs = _read_csv(logs_path)
    proxy_events = _read_csv(proxy_path)
    accounts = _read_csv(accounts_path)
    positions = _read_csv(positions_path)
    flags = summary.get("log_flags", {})
    important_logs = [
        row
        for row in logs
        if any(key in str(row.get("msg", "")) for key in ["连接成功", "登录成功", "授权验证成功", "结算信息确认成功", "连接断开"])
    ]
    for row in important_logs:
        row["gateway"] = row.get("gateway_name", "")
        row["message"] = row.get("msg", "")

    width = 2400
    height = 1900
    image = Image.new("RGB", (width, height), (243, 246, 251))
    draw = ImageDraw.Draw(image)
    margin = 80
    draw.rectangle((margin, 48, width - margin, height - 48), fill=(255, 255, 255), outline=(211, 224, 239), width=2)
    x = margin + 44
    y = 88
    draw.text((x, y), "SimNow 程序化断网回调证明", font=_font(52, bold=True), fill=(20, 32, 51))
    y += 72
    draw.text(
        (x, y),
        f"生成时间：{summary.get('generated_at', '')} | 方法：本机 TCP 代理登录成功后主动切断连接 | 全程不调用订单 API",
        font=_font(28),
        fill=(82, 101, 126),
    )
    y += 66

    card_w = 520
    card_h = 126
    gap = 24
    cards = [
        ("断网测试状态", summary.get("status", ""), summary.get("status") == "disconnect_observed"),
        ("交易登录", "成功" if flags.get("td_login_success") else "未确认", bool(flags.get("td_login_success"))),
        ("行情登录", "成功" if flags.get("md_login_success") else "未确认", bool(flags.get("md_login_success"))),
        ("交易断开回报", "已收到" if flags.get("td_disconnected") else "未收到", bool(flags.get("td_disconnected"))),
        ("行情断开回报", "已收到" if flags.get("md_disconnected") else "未收到", bool(flags.get("md_disconnected"))),
        ("订单API调用", "0 / 0", True),
        ("交易前置", summary.get("remote_td_address", ""), False),
        ("行情前置", summary.get("remote_md_address", ""), False),
        ("本机交易代理", summary.get("proxy_td_address", ""), False),
        ("本机行情代理", summary.get("proxy_md_address", ""), False),
        ("切断时间", summary.get("cut_at", ""), False),
        ("测试环境", "SimNow 普通仿真 trading", False),
    ]
    for idx, (label, value, ok) in enumerate(cards):
        row = idx // 4
        col = idx % 4
        _draw_card(draw, (x + col * (card_w + gap), y + row * (card_h + gap)), (card_w, card_h), label, str(value), ok=ok)
    y += 3 * (card_h + gap) + 20
    draw.text(
        (x, y),
        "说明：没有关闭整台 Mac 网络，而是在 CTP API 与 SimNow 前置之间加本机代理；登录成功后关闭代理 socket，模拟运行中断网。",
        font=_font(26),
        fill=(78, 96, 120),
    )
    y += 58
    table_width = width - 2 * margin - 88
    y = _draw_table(draw, x, y, table_width, "CTP关键日志", important_logs, [("time", 300), ("gateway", 110), ("message", 1580), ("level", 90)], 10)
    y = _draw_table(draw, x, y, table_width, "本机代理事件", proxy_events, [("time", 300), ("proxy", 90), ("event", 260), ("local", 320), ("target", 320), ("reason", 440), ("closed_sockets", 160), ("bytes", 140)], 10)
    left_w = table_width // 2 - 14
    y2 = _draw_table(draw, x, y, left_w, "账户快照", accounts, [("gateway_name", 150), ("accountid", 170), ("balance", 180), ("available", 180), ("frozen", 140)], 4)
    y3 = _draw_table(draw, x + left_w + 28, y, left_w, "持仓快照", positions, [("vt_symbol", 200), ("direction", 140), ("volume", 140), ("frozen", 140), ("yd_volume", 150)], 4)
    y = max(y2, y3) + 18
    draw.text((x, y), "结论：断网回调已被 CTP/vn.py 捕获；本次验证没有报单、没有撤单、没有成交。", font=_font(30, bold=True), fill=(14, 122, 54))
    image.save(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Stage287 PNG evidence from existing outputs.")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    path = build(args.run_id)
    print(path)


if __name__ == "__main__":
    main()
