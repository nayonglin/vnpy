"""Frozen stock recap adapter. No strategy, vn.py, futures runtime or network imports.

The canonical renderer has futures imports at module scope. Load only its pinned
pure display definitions (not its module), so the HTML/plotting code has one
source of truth without starting a futures runtime. Stock units and disclosures
are presentation substitutions with exact-match guards, never a copied template.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / "research/lines/stock_qmt357_vnpy"
STOCK = ROOT / "examples/stock_backtesting/qmt357_commit4ac255e"
RUN = STOCK / "outputs/fixed_2020_20260928_commit4ac255e_repaired_v1"
PANEL = STOCK / "data/snapshots/history_201910_20260928_repaired_v1/panel.parquet"
OUTPUT = LINE / "outputs/stage014_commit4ac255e_stock_recap_v1"
CANONICAL = ROOT / "research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py"
RENDERER_SHA = "613672a4cc91493ba17dc055542e4b4172349de210ff932530caf04ce36bb93a"
PURE_FUNCTIONS = {
    "_json_safe", "_date_index", "_window_dates", "_weekly_from_daily",
    "_monthly_from_daily", "_trading_day_bars_from_daily", "_monthly_window",
    "_add_moving_averages", "_period_coordinates", "_records", "_html",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def close(actual: float, expected: float, label: str) -> None:
    if not math.isfinite(float(actual)) or not math.isfinite(float(expected)) or not math.isclose(
        float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-6
    ):
        raise ValueError(f"{label} mismatch: {actual} != {expected}")


def load_renderer() -> SimpleNamespace:
    if sha256(CANONICAL) != RENDERER_SHA:
        raise ValueError("Canonical renderer changed; review the display adapter before updating its pin")
    parsed = ast.parse(CANONICAL.read_text(encoding="utf-8"), filename=str(CANONICAL))
    definitions = [node for node in parsed.body
                   if isinstance(node, ast.FunctionDef) and node.name in PURE_FUNCTIONS]
    if {node.name for node in definitions} != PURE_FUNCTIONS:
        raise ValueError("Canonical pure display functions are incomplete")
    namespace = dict(pd=pd, np=np, math=math, json=json, html=html,
                     datetime=datetime, Any=Any, get_plotlyjs=get_plotlyjs,
                     MA_PERIODS=(5, 10, 20, 40), MONTHLY_PRE=10, MONTHLY_POST=10,
                     OFFICIAL_LIVE_ALIAS="股票研究（非实盘）", OFFICIAL_LIVE_VERSION="未指定")
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                             *definitions], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(CANONICAL), "exec"), namespace)
    return SimpleNamespace(**{key: namespace[key] for key in PURE_FUNCTIONS})


def validate_output_path(output: Path) -> Path:
    resolved = output.resolve()
    allowed = (LINE / "outputs").resolve()
    if resolved.parent != allowed or not resolved.name:
        raise ValueError("Recap output must be a new direct child of the stock line outputs directory")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite recap: {output}")
    return resolved


def pair_episodes(trades: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    fills = trades.copy().reset_index(drop=True)
    fills["date"] = pd.to_datetime(fills.date).dt.normalize()
    if fills.empty or trips.empty or fills.duplicated(["vt_symbol", "date", "direction"]).any():
        raise ValueError("Empty or duplicate stock fills; one entry and final exit required")
    used: set[int] = set()
    rows = []
    for index, trip in enumerate(trips.itertuples(index=False)):
        symbol = str(trip.vt_symbol)
        if not re.fullmatch(r"\d{6}\.(SSE|SZSE)", symbol):
            raise ValueError(f"Invalid stock symbol: {symbol}")
        entry, exit_ = pd.Timestamp(trip.entry_date).normalize(), pd.Timestamp(trip.exit_date).normalize()
        if entry >= exit_:
            raise ValueError("Stock episodes must observe T+1")
        paired = []
        for direction, date in (("buy", entry), ("sell", exit_)):
            matching = fills[(fills.vt_symbol == symbol) & (fills.date == date) & (fills.direction == direction)]
            if len(matching) != 1 or int(matching.index[0]) in used:
                raise ValueError(f"Non-unique episode pairing: {symbol} {date} {direction}")
            used.add(int(matching.index[0]))
            paired.append(matching.iloc[0])
        buy, sell = paired
        if buy.shares != sell.shares or buy.shares <= 0 or buy.price <= 0 or sell.price <= 0:
            raise ValueError("This recap adapter requires positive equal entry/exit shares (no held split)")
        for fill in paired:
            close(fill.turnover, fill.price * fill.shares, "fill turnover")
        close(trip.entry_cost, buy.turnover + buy.commission, "entry cost")
        close(trip.proceeds, sell.turnover - sell.commission, "exit proceeds")
        close(trip.net_pnl, trip.proceeds + trip.dividends - trip.entry_cost, "net pnl")
        change = (sell.price / buy.price - 1) * 100
        outcome = "profit" if trip.net_pnl > 0 else "loss" if trip.net_pnl < 0 else "flat"
        rows.append(dict(open_trade_id=f"stock-{index + 1:04d}", close_trade_id=f"stock-{index + 1:04d}-exit",
                         lot_id=f"stock-{index + 1:04d}", lot_count=1, vt_symbol=symbol, product=symbol,
                         direction="long", entry_date=entry, exit_date=exit_, entry_price=float(buy.price),
                         exit_price=float(sell.price), weighted_exit_price=float(sell.price), volume=float(buy.shares),
                         price_change_pct=float(change), price_change_label=f"原价涨跌 {change:+.2f}%（非账户收益）",
                         realized_pnl=float(trip.net_pnl), r_multiple=float("nan"), result_type=outcome,
                         result_rank=index + 1, is_tail=0, draw_intraday=0, profit_r_threshold=float("nan"),
                         loss_r_threshold=float("nan"), holding_calendar_days=(exit_ - entry).days,
                         selection_basis=f"买 {buy.price:g} → 卖 {sell.price:g}｜{int(buy.shares)}股｜{sell.reason}",
                         exit_reason=str(sell.reason), signal=str(buy.reason),
                         entry_signal_date=str(buy.signal_date)[:10], exit_signal_date=str(sell.signal_date)[:10],
                         dividends=float(trip.dividends), entry_cost=float(trip.entry_cost), proceeds=float(trip.proceeds),
                         commission=float(buy.commission + sell.commission), slippage=float(buy.slippage + sell.slippage)))
    if used != set(fills.index):
        raise ValueError("Unpaired fills or residual positions; cannot silently omit them")
    return pd.DataFrame(rows)


def verify_bundle(run: Path, panel_path: Path) -> dict:
    manifest, summary = read_json(run / "manifest.json"), read_json(run / "summary.json")
    if manifest.get("status") != "COMPLETE" or manifest.get("complete_period_result") is not True:
        raise ValueError("A complete frozen run is required")
    if summary.get("open_positions") != 0:
        raise ValueError("Bundle has residual positions; not supported by this closed-stock adapter")
    required = ("run_identity.json", "code_snapshot.tar.gz", "trades.csv", "round_trips.csv", "daily_equity.csv")
    if any(not (run / name).is_file() for name in required) or not panel_path.is_file():
        raise ValueError("Incomplete source evidence")
    identity = read_json(run / "run_identity.json")
    for key, value in identity.items():
        if key not in ("status", "complete_period_result") and manifest.get(key) != value:
            raise ValueError(f"Frozen run identity mismatch: {key}")
    for path, expected in ((run / "run_identity.json", manifest["run_identity_sha256"]),
                           (run / "code_snapshot.tar.gz", manifest["code_archive_sha256"]),
                           (panel_path, manifest["snapshot"]["panel_sha256"])):
        if sha256(path) != expected:
            raise ValueError(f"Frozen source hash mismatch: {path.name}")
    if manifest["run_id"] != run.name:
        raise ValueError("Run folder and identity do not match")
    snapshot_manifest = read_json(panel_path.parent / "manifest.json")
    if snapshot_manifest != manifest["snapshot"]:
        raise ValueError("Snapshot metadata differs from the frozen run")
    trades = pd.read_csv(run / "trades.csv")
    trips = pd.read_csv(run / "round_trips.csv")
    equity = pd.read_csv(run / "daily_equity.csv", parse_dates=["date"])
    episodes = pair_episodes(trades, trips)
    if equity.empty or equity.date.duplicated().any() or not equity.date.is_monotonic_increasing:
        raise ValueError("Invalid frozen equity chronology")
    if not equity.date.between(pd.Timestamp(manifest["start"]), pd.Timestamp(manifest["end"])).all():
        raise ValueError("Equity dates outside frozen interval")
    if not pd.to_datetime(trades.date).isin(equity.date).all():
        raise ValueError("Fill dates outside frozen equity calendar")
    capital = manifest["settings"]["capital"]
    returns = equity.equity / equity.equity.shift(1, fill_value=capital) - 1
    drawdown = (equity.equity / equity.equity.cummax().clip(lower=capital) - 1) * 100
    std = returns.std(ddof=0)
    checks = dict(end_equity=equity.equity.iloc[-1], total_return_pct=(equity.equity.iloc[-1] / capital - 1) * 100,
                  max_drawdown_pct=drawdown.min(), sharpe=returns.mean() / std * math.sqrt(manifest["settings"]["annual_days"]) if std > 0 else 0.,
                  total_trade_count=len(trades), closed_round_trips=len(trips), trading_days=len(equity),
                  win_rate_pct=100 * (trips.net_pnl > 0).mean(), total_slippage=trades.slippage.sum(),
                  total_commission=trades.commission.sum(), open_positions=equity.position_count.iloc[-1])
    for name, value in checks.items():
        close(value, summary[name], name)
    close(trips.net_pnl.sum(), summary["end_equity"] - capital, "closed ledger vs equity")
    close(equity.market_value.iloc[-1], 0, "residual market value")
    close(equity.cash.iloc[-1], summary["end_equity"], "ending cash")
    source_files = [run / name for name in ("manifest.json", "summary.json", *required)]
    source_files += [panel_path, panel_path.parent / "manifest.json"]
    return dict(manifest=manifest, summary=summary, episodes=episodes, equity=equity,
                input_sha256={str(path): sha256(path) for path in source_files})


def build_records(episodes: pd.DataFrame, panel: pd.DataFrame, renderer: SimpleNamespace) -> tuple[list, pd.DataFrame]:
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel.date).dt.normalize()
    if panel.duplicated(["vt_symbol", "date"]).any():
        raise ValueError("Duplicate market bars")
    benchmark = panel[panel.vt_symbol.eq("000300.SSE")]
    calendar = sorted(benchmark.date.unique() if not benchmark.empty else panel.date.unique())
    day_index = {pd.Timestamp(date): index for index, date in enumerate(calendar)}
    full_by_symbol = {symbol: part.sort_values("date").reset_index(drop=True)
                      for symbol, part in panel[panel.vt_symbol.isin(episodes.vt_symbol)].groupby("vt_symbol")}
    contexts, minute_dates = {}, {}
    for row in episodes.itertuples(index=False):
        if row.vt_symbol not in full_by_symbol:
            raise ValueError(f"No exact stock bars: {row.vt_symbol}")
        full = full_by_symbol[row.vt_symbol].copy()
        numeric = full[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
        if not np.isfinite(numeric).all() or (numeric[:, :4] <= 0).any() or (numeric[:, 4] < 0).any():
            raise ValueError("Invalid raw market bars")
        if any(date not in day_index for date in full.date):
            raise ValueError("Stock bar is outside frozen benchmark calendar")
        visible = renderer._window_dates(full, row.entry_date, row.exit_date, 300, 50)
        full["display"] = full.date.isin(visible).astype(int)
        week_start = pd.Timestamp(visible[0]).to_period("W-FRI").start_time.normalize()
        week_end = pd.Timestamp(visible[-1]).to_period("W-FRI").end_time.normalize()
        full["weekly_display"] = full.date.between(week_start, week_end).astype(int)
        full["trading_day_index"] = full.date.map(day_index).astype(int)
        full["source_vt_symbol"] = row.vt_symbol
        full["context_fallback"] = 0
        available = set(full.date)
        full.attrs["missing_context_dates"] = [str(pd.Timestamp(date).date()) for date in calendar
                                                if visible[0] <= date <= visible[-1] and date not in available]
        contexts[row.open_trade_id] = full
        minute_dates[row.open_trade_id] = renderer._window_dates(full, row.entry_date, row.exit_date, 5, 5)
    records, _ = renderer._records(episodes, contexts, minute_dates, pd.DataFrame(columns=["vt_symbol"]))
    manifest_rows = []
    extras = episodes.set_index("open_trade_id")
    for rec in records:
        meta = rec["meta"]
        row = extras.loc[meta["open_trade_id"]]
        dates = rec["daily"]["date"]
        pre = sum(date < meta["entry_date"] for date in dates)
        post = sum(date > meta["exit_date"] for date in dates)
        full = contexts[meta["open_trade_id"]]
        expected_months = pd.period_range(pd.Timestamp(meta["entry_date"]).to_period("M") - 10,
                                         pd.Timestamp(meta["exit_date"]).to_period("M") + 10, freq="M")
        available_months = set(rec["monthly"]["label"])
        missing_months = [str(month) for month in expected_months if str(month) not in available_months]
        meta.update(price_basis="unadjusted", volume_unit="shares", pre_daily_bars=pre, post_daily_bars=post,
                    pre_history_truncated=pre < 300, post_history_truncated=post < 50,
                    missing_months=missing_months, dividend_cash=float(row.dividends), commission=float(row.commission),
                    slippage=float(row.slippage), entry_signal_date=row.entry_signal_date, exit_signal_date=row.exit_signal_date,
                    source_first_date=str(full.date.iloc[0].date()), source_last_date=str(full.date.iloc[-1].date()),
                    minute_status="not_available_in_frozen_snapshot", no_proxy=True)
        # Trim display payload only AFTER canonical MA warmup, retaining actual buckets crossing a boundary.
        for period in ("day10", "day30"):
            data = rec[period]
            indices = [i for i, x in enumerate(data["x"])
                       if x + data["width"][i] / .78 / 2 >= meta["chart_x_start"]
                       and x - data["width"][i] / .78 / 2 <= meta["chart_x_end"]]
            rec[period] = {key: [values[i] for i in indices] for key, values in data.items()}
        for period in ("day30", "day10", "monthly", "weekly", "daily"):
            meta[f"{period}_ma40_missing_bars"] = sum(value is None for value in rec[period]["ma40"])
        manifest_rows.append({**meta, **{f"{key}_bars": len(rec[key]["x"]) for key in ("day30", "day10", "monthly", "weekly", "daily")},
                              "bars_15m": 0})
    return records, pd.DataFrame(manifest_rows)


def render_stock_html(records: list, summary: dict, renderer: SimpleNamespace) -> str:
    page = renderer._html(records, summary)
    substitutions = {
        "'品种'": "'股票'", "['合约',m.vt_symbol]": "['股票',m.vt_symbol]",
        "['方向',m.direction]": "['方向','仅做多']",
        "['R倍数',rfmt(m.r_multiple)]": "['分红（元）',fmt(m.dividend_cash)]",
        "['平仓lot',m.lot_count]": "['股数',fmt(m.volume,0)]",
        "'全程精确合约'": "'本股票未复权原价'",
        "日主力代理": "日代理（股票版禁止）",
        "产品交易日历": "冻结股票交易日历",
        "灰虚线表示精确合约缺历史数据后切到当日主力上下文。": "不使用其他股票代理补齐历史；未复权除权跳空不等于投资收益。",
        "<option value=\"profit_tail\">盈利尾部</option><option value=\"loss_tail\">亏损尾部</option>": "",
        "切到已补数交易时恢复。": "此冻结快照只有日线。",
        "document.getElementById('periodNote').innerHTML=text":
            "document.getElementById('periodNote').innerHTML=text+` 前窗 ${meta.pre_daily_bars}/300 日，后窗 ${meta.post_daily_bars}/50 日；缺 ${meta.missing_months.length} 个月份。MA40 真实历史不足：30日K ${meta.day30_ma40_missing_bars} 根、10日K ${meta.day10_ma40_missing_bars} 根、月K ${meta.monthly_ma40_missing_bars} 根、周K ${meta.weekly_ma40_missing_bars} 根、日K ${meta.daily_ma40_missing_bars} 根（空值保留）。`",
    }
    for old, new in substitutions.items():
        if page.count(old) != 1:
            raise ValueError(f"Canonical stock presentation hook changed: {old[:60]}")
        page = page.replace(old, new, 1)
    metrics = summary["frozen_metrics"]
    cards = [
        ("冻结期末权益（元）", f"{metrics['end_equity']:,.2f}"),
        ("总收益", f"{metrics['total_return_pct']:+.4f}%"),
        ("最大回撤", f"{metrics['max_drawdown_pct']:.4f}%"),
        ("Sharpe", f"{metrics['sharpe']:.4f}"),
        ("买卖成交 / 闭合交易", f"{metrics['total_trade_count']} / {metrics['closed_round_trips']}"),
        ("净胜率", f"{metrics['win_rate_pct']:.4f}%"),
        ("佣金含印花税（元）", f"{metrics['total_commission']:,.2f}"),
        ("滑点（已含成交价，元）", f"{metrics['total_slippage']:,.2f}"),
    ]
    overview = '<div class="metrics" id="frozenMetrics">' + "".join(
        f'<div class="metric"><div class="k">{html.escape(label)}</div><div class="v">{html.escape(value)}</div></div>'
        for label, value in cards) + "</div>"
    page = page.replace('<div class="toolbar">', overview + '<div class="toolbar">', 1)
    return page


def generate(run: Path = RUN, panel_path: Path = PANEL, output: Path = OUTPUT) -> dict:
    output = validate_output_path(output)
    source = verify_bundle(run, panel_path)
    renderer = load_renderer()
    panel = pd.read_parquet(panel_path)
    records, chart_manifest = build_records(source["episodes"], panel, renderer)
    frozen = source["manifest"]
    summary = dict(status="COMPLETE", artifact_type="stock_display_only_recap", episode_scope="all",
                   page_title="QMT357 · commit4ac255e 股票逐笔复盘｜2020—2026-09-28",
                   source_label="独立股票研究冻结回测（非实盘）", source_version=frozen["version"],
                   source_run_id=frozen["run_id"], source_commit=frozen["source_provenance"]["commit"],
                   start=frozen["start"], end=frozen["end"], rank_basis="realized_pnl",
                   source_warning="收盘信号→次日开盘，不是 QMT 14:50 回放。未复权 K 线及展示均线不等于策略复权信号。净盈亏含现金分红并扣费用；原价涨跌不是账户收益。",
                   coverage_note="全部226笔闭合交易；15分钟无数据，不下载、不补造。早期历史/近期后窗及高周期均线可能不足，以每笔提示为准。",
                   footer_scope="成交量及持仓单位为股，价格单位元；0个残余持仓。数据边界：月度历史池、派生限价、固定费率、分红到账/税近似；15处配股与600515重整未完整建模但本次无除权前直接持仓，176处小额参考价残差尚未逐一公告核验。",
                   frozen_metrics=source["summary"], settings=frozen["settings"],
                   source_snapshot_sha256=frozen["snapshot"]["panel_sha256"], input_sha256=source["input_sha256"],
                   canonical_renderer=str(CANONICAL), canonical_renderer_sha256=RENDERER_SHA,
                   adapter_sha256=sha256(Path(__file__)), completed_episodes=len(records),
                   result_counts=source["episodes"].result_type.value_counts().to_dict(),
                   dividend_total=float(source["episodes"].dividends.sum()), residual_positions=0,
                   available_periods=["day30", "day10", "monthly", "weekly", "daily"],
                   default_periods=["day30", "daily"], minute_bars=0, price_basis="unadjusted",
                   pre_history_truncated_episodes=int(chart_manifest.pre_history_truncated.sum()),
                   post_history_truncated_episodes=int(chart_manifest.post_history_truncated.sum()),
                   strategy_rerun=False, market_download=False, production_access=False,
                   created_at=datetime.now().astimezone().isoformat())
    page = render_stock_html(records, summary, renderer)
    for path, digest in source["input_sha256"].items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"Input changed during rendering: {path}")
    # No outputs are published until identity, pairings, metrics and rendering pass.
    output.mkdir(parents=True, exist_ok=False)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "records.json").write_text(json.dumps(renderer._json_safe(records), ensure_ascii=False, allow_nan=False), encoding="utf-8")
    chart_manifest.to_csv(output / "chart_manifest.csv", index=False, encoding="utf-8-sig")
    summary["artifact_sha256"] = {name: sha256(output / name) for name in ("index.html", "records.json", "chart_manifest.csv")}
    (output / "summary.json").write_text(json.dumps(renderer._json_safe(summary), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    before = set(sys.modules)
    result = generate(output=args.output)
    imported = [name for name in set(sys.modules) - before if name.startswith(("vnpy", "tqsdk", "qmt_roll", "analyze_qmt"))]
    if imported:
        raise RuntimeError(f"Unexpected trading imports: {imported}")
    print(json.dumps(dict(output=str(args.output), episodes=result["completed_episodes"],
                          result_counts=result["result_counts"], frozen_metrics=result["frozen_metrics"],
                          futures_imports=imported), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
