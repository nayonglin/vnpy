"""Frozen Weekly19 Stage003 D adapter for the Stage038 multiscale renderer."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys

import pandas as pd

LINE = Path(__file__).resolve().parents[1]
FORENSICS = LINE.parent / "futures_trend_winner_trade_forensics"
sys.path.insert(0, str(FORENSICS / "tools"))
import stage038_c9_15w_big_winner_multiscale_html as renderer

TAG = "weekly19_stop_reversal"
RUN = "stage003_D_20261103_attempt01"
DESTINATION = FORENSICS / "outputs/stage003_weekly19_loss_only_reversal_recap_v1"
AUDIT_HASH = "2d0a2ad145b8a3d22972efa4eab65eb428681d0eb79077a3da2f05d9cd15195b"


@dataclass
class Bundle:
    daily: pd.DataFrame
    trades: pd.DataFrame
    decisions: pd.DataFrame
    closed: pd.DataFrame
    episodes: pd.DataFrame
    database: Path
    mapping: Path
    metrics: dict
    audit: dict
    inputs: dict


def _sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _read_json(path):
    return json.loads(path.read_text())


def _verify(path, expected):
    if _sha(path) != expected:
        raise ValueError(f"frozen source hash mismatch: {path.name}")


def load_bundle(output_root):
    run = output_root / RUN
    audit_path = output_root / "stage003_independent_review.json"
    _verify(audit_path, AUDIT_HASH)
    audit = _read_json(audit_path)
    for name, expected in audit["D"]["hashes"].items():
        _verify(run / name, expected)
    inputs = _read_json(run / "inputs.json")
    if inputs["arm"] != "D" or not inputs["original_position_loss_only"] or inputs["study_git_head"] != audit["study_git_head"]:
        raise ValueError("D identity mismatch")
    paths = {Path(path).name: (Path(path), sha) for path, sha in inputs["inputs_sha256"].items()}
    database, mapping = (paths[name][0] for name in ("daily.sqlite", "mapping.csv"))
    for path in (database, mapping):
        _verify(path, paths[path.name][1])
    summary_root = output_root / "stage003_summary"
    line = next(line for line in (summary_root / "checksums.sha256").read_text().splitlines()
                if line.endswith("/summary.json"))
    _verify(summary_root / "summary.json", line.split()[0])
    metrics = _read_json(summary_root / "summary.json")["D"]
    daily = pd.read_csv(run / "daily.csv")
    if len(daily) != audit["D"]["days"] or daily.date.iloc[-1] != inputs["end"]:
        raise ValueError("D daily window mismatch")
    if not math.isclose(daily.total_account_equity.iloc[-1], metrics["end_equity"]):
        raise ValueError("D daily equity mismatch")
    trades = pd.read_csv(run / "trades.csv", keep_default_na=False).set_index("trade_id", verify_integrity=True)
    decisions = pd.read_csv(run / "reversal_decisions.csv", keep_default_na=False)
    decisions = decisions.loc[decisions.status.eq("filled")].set_index("open_trade_id", verify_integrity=True)
    sleeve = trades.loc[trades.sleeve.eq(TAG)].reset_index()
    if set(sleeve.loc[sleeve.offset.eq("open"), "trade_id"]) != set(decisions.index):
        raise ValueError("unpaired reversal decisions")
    fixes = {row["trade_id"]: row["model_exit"] for row in audit["D"]["legacy_reverse_exit_label_forensic_proof"]}
    sleeve = sleeve.rename(columns={"symbol": "vt_symbol", "side": "direction", "reason": "exit_reason"})
    sleeve["exit_reason"] = [fixes.get(i, reason) for i, reason in zip(sleeve.trade_id, sleeve.exit_reason)]
    # Stable ledger order for same-date fills. This synthetic ordering column
    # is used only by FIFO and never represented as an execution clock.
    sleeve["datetime"] = pd.to_datetime(sleeve.date) + pd.to_timedelta(range(len(sleeve)), unit="ms")
    settings = _read_json(run / "contract_settings.json")
    closed = renderer._closed_lots_from_trade_ledger(sleeve, sizes=settings["sizes"], source_prefix=TAG)
    closed["lot_id"] = [f"{TAG}.{i:05d}" for i in range(len(closed))]
    for i, lot in closed.iterrows():
        opened, exited = trades.loc[lot.open_trade_id], trades.loc[lot.close_trade_id]
        decision = decisions.loc[lot.open_trade_id]
        if (
            decision.original_position_net >= 0 or decision.symbol != lot.vt_symbol
            or decision.direction != lot.direction or decision.decision_day != lot.entry_date
            or float(decision.price) != lot.entry_price or trades.loc[decision.close_trade_id, "symbol"] != lot.vt_symbol
        ):
            raise ValueError(f"reversal identity mismatch: {lot.open_trade_id}")
        costs = sum((fill.slippage + fill.commission) * lot.volume / fill.volume for fill in (opened, exited))
        risk_per_lot = max(abs(lot.entry_price - float(decision.initial_stop)) * lot["size"],
                           settings["priceticks"][lot.vt_symbol] * lot["size"], 1)
        pnl = round(lot.realized_pnl - costs, 8)
        closed.loc[i, ["realized_pnl", "risk_amount", "r_multiple", "winner"]] = (
            pnl, risk_per_lot * lot.volume, pnl / (risk_per_lot * lot.volume), int(pnl > 0),
        )
    episodes = renderer._all_trade_episodes(closed)
    episodes["draw_intraday"] = 0
    expected = audit["D"]["closed_metrics_by_sleeve"][TAG]
    counts = episodes.result_type.value_counts().to_dict()
    if len(episodes) != expected["cycles"] or counts != {"profit": expected["wins"], "loss": expected["losses"]}:
        raise ValueError("reversal episode count mismatch")
    if not math.isclose(episodes.realized_pnl.sum(), audit["reverse_direct_net"], abs_tol=1e-6):
        raise ValueError("reversal net PnL mismatch")
    return Bundle(daily, trades, decisions, closed, episodes, database, mapping, metrics, audit, inputs)


REASON = {
    "prev2day_stop": "两周极值止损",
    "base_stop": "底仓保护止损",
    "ma_stop": "均线止损",
    "weekly19_stop_reversal_stop": "反手仓周线保护止损",
    "two_week_ratchet": "两周移动止损（独审核正）",
    "rollover_after_five_trading_days": "延迟换月平仓（独审核正）",
    "rollover_close": "换月平仓",
    "forced_margin_deleverage": "保证金风控减仓",
    "risk_cluster_heat_deleverage": "组合风险组减仓",
}


def _reason(value):
    return REASON.get(value.removeprefix("long_").removeprefix("short_"), value)


def _annotate(records, manifest, bundle):
    for index, record in enumerate(records):
        meta = record["meta"]
        decision = bundle.decisions.loc[meta["open_trade_id"]]
        original_close = bundle.trades.loc[decision.close_trade_id]
        if original_close.date != decision.close_day or original_close.bound_stop_reason != decision.signal_reason:
            raise ValueError("original close is not the bound stop fill")
        daily = record["daily"]
        bars = {date: (x, close, source) for date, x, close, source in
                zip(daily["date"], daily["x"], daily["close"], daily["source"])}
        if meta["entry_source"] != meta["vt_symbol"] or meta["exit_source"] != meta["vt_symbol"]:
            raise ValueError("missing exact contract on reversal execution day")
        events = []

        def mark(date, price, label, symbol):
            x, close, source = bars[date]
            if source != meta["vt_symbol"]:
                raise ValueError(f"proxy is forbidden for event marker: {source} {date}")
            events.append(dict(x=x, price=close if price is None else float(price),
                               label=f"{date} {label}", symbol=symbol))

        mark(decision.signal_day, None, "原仓周线止损确认", "diamond-open")
        mark(original_close.date, original_close.price, "原仓全平成交", "diamond")
        exits = bundle.closed.loc[bundle.closed.open_trade_id.eq(meta["open_trade_id"])]
        for lot in list(exits.itertuples(index=False))[:-1]:
            mark(lot.exit_date, lot.exit_price, f"反手部分平仓 {lot.volume:g} 手", "circle")
        meta["event_markers"] = events
        text = (
            f"原仓 {decision.signal_day} {_reason(decision.signal_reason)} → "
            f"{original_close.date} 全平 @{original_close.price:g}（净盈亏 {decision.original_position_net:,.0f} 元）"
            f"｜反手 {meta['entry_date']} @{meta['entry_price']:g} ×{meta['volume']:g}手"
            f"｜初始止损 {float(decision.initial_stop):g}｜最终退出 {_reason(meta['exit_reason'])}"
        )
        meta["episode_note"] = text
        meta["selection_basis"] = "原仓净亏损触发"
        for key, value in dict(
            episode_note=text, original_signal_date=decision.signal_day, original_close_id=decision.close_trade_id,
            original_close_date=original_close.date, original_close_price=original_close.price,
            original_net=decision.original_position_net, initial_stop=decision.initial_stop,
        ).items():
            manifest.loc[index, key] = value


def write_recap(bundle, destination):
    if destination.exists():
        raise FileExistsError(destination)
    renderer.ACTIVE_DATABASE_PATH = bundle.database
    renderer.PREFER_DATABASE_DAILY = True
    mapping = pd.read_csv(bundle.mapping, parse_dates=["date"], keep_default_na=False)
    mapping = mapping.loc[mapping.main_contract_vt.ne("")]
    cache, daily, windows = {}, {}, {}
    for episode in bundle.episodes.itertuples(index=False):
        daily[episode.open_trade_id], windows[episode.open_trade_id] = renderer._context_daily(
            episode, mapping, cache, allow_daily_download=False, allow_noncritical_daily_gaps=True,
            recover_local_minutes=False, data_end=pd.Timestamp(bundle.inputs["end"]),
        )
    records, manifest = renderer._records(
        bundle.episodes, daily, windows, pd.DataFrame(columns=["vt_symbol"]),
    )
    _annotate(records, manifest, bundle)
    summary = dict(
        episode_scope="all", source_label="Weekly19 Stage003 D 冻结研究", source_version=bundle.inputs["study_git_head"],
        page_title="Weekly19｜仅亏损反手逐笔复盘",
        coverage_note="56 笔反手均有五种日线衍生周期。橙色标记原仓周线止损、全平成交及反手部分平仓。无 15 分钟图。",
        source_warning="成交为日开盘代理，反手发生在原仓全平后的下一交易日，且在同一执行周内。",
        footer_scope="56 个完整反手周期，20 盈、36 亏，合计净亏 35,305 元。R 以反手实际手数及初始止损距离计。",
        rank_basis="realized_pnl", chart_episodes=len(records),
        chart_profit_episodes=20, chart_loss_episodes=36, chart_flat_episodes=0,
        backtest_metrics=bundle.metrics, reversal_direct_net=bundle.audit["reverse_direct_net"],
        provenance=bundle.inputs, independent_review_sha256=AUDIT_HASH,
        intraday_draw_episodes=0, bars_15m=0, context_fallback_days=int(manifest.context_fallback_days.sum()),
        missing_context_days=sum(len(row["meta"]["missing_context_dates"]) for row in records),
        period_picker={"options": ["day30", "day10", "monthly", "weekly", "daily"], "default_selected": ["day30", "daily"]},
        residual_open_positions=bundle.closed.attrs["residual_open_positions"],
    )
    destination.mkdir(parents=True)
    (destination / "index.html").write_text(renderer._html(records, summary))
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    manifest.to_csv(destination / "chart_manifest.csv", index=False)
    bundle.closed.to_csv(destination / "closed_lots.csv", index=False)
    return destination / "index.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DESTINATION)
    print(write_recap(load_bundle(LINE / "outputs"), parser.parse_args().output))
