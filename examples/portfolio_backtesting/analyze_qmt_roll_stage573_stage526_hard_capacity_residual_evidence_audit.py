from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DATA_ROOT = PROJECT_DIR / "downloaded_futures"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage573_stage526_hard_capacity_residual_evidence_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE567_PREFIX = "qmt_roll_stage567_stage526_residual_capacity_boundary_audit"
STAGE567_TAG = "stage567_stage526_residual_capacity_boundary_audit_v1"
HARD_EVENTS_IN = OUTPUT_DIR / f"{STAGE567_PREFIX}_hard_capacity_events_{STAGE567_TAG}.csv"
ROLL_PAIR_IN = OUTPUT_DIR / f"{STAGE567_PREFIX}_roll_pair_context_{STAGE567_TAG}.csv"

DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hard_event_detail_{MODEL_TAG}.csv"
MINUTE_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_candidates_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

DAILY_ROOT = DATA_ROOT / "tqsdk_daily_2010_2026_04"
DAILY_VOLUME_HARD_PCT = 1.0
DAILY_VOLUME_SOFT_PCT = 0.5
MIN_CLOSE_WINDOW_VOLUME = 1.0


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _split_vt(vt_symbol: str) -> tuple[str, str]:
    if "." not in str(vt_symbol):
        return str(vt_symbol), ""
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, exchange


def _daily_row(vt_symbol: str, trade_date: pd.Timestamp) -> dict[str, Any]:
    symbol, exchange = _split_vt(vt_symbol)
    path = DAILY_ROOT / exchange.upper() / f"{symbol}.csv"
    empty = {
        "daily_source_path": str(path),
        "daily_found": 0,
        "daily_volume": 0.0,
        "daily_open_oi": 0.0,
        "daily_close_oi": 0.0,
        "daily_close": np.nan,
    }
    if not path.exists():
        return empty
    frame = _read_csv(path)
    if "trade_date" not in frame.columns:
        return empty
    rows = frame[frame["trade_date"].astype(str).eq(trade_date.date().isoformat())].copy()
    if rows.empty:
        return empty
    row = rows.iloc[-1]
    return {
        "daily_source_path": str(path),
        "daily_found": 1,
        "daily_volume": float(row.get("volume", 0.0) or 0.0),
        "daily_open_oi": float(row.get("open_oi", 0.0) or 0.0),
        "daily_close_oi": float(row.get("close_oi", 0.0) or 0.0),
        "daily_close": float(row.get("close", np.nan)),
    }


def _minute_paths(vt_symbol: str) -> list[Path]:
    symbol, _ = _split_vt(vt_symbol)
    lower = symbol.lower()
    upper = symbol.upper()
    paths: list[Path] = []
    for path in DATA_ROOT.rglob("*.csv"):
        name = path.name
        if "minute_backtest" not in name:
            continue
        if name.startswith(lower) or name.startswith(upper):
            paths.append(path)
    return sorted(paths, key=lambda item: (0 if "completed" in item.name.lower() else 1, len(str(item)), str(item)))


def _window_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        return {
            "target_rows": 0,
            "target_total_volume": 0.0,
            "target_first_bar_at": "",
            "target_last_bar_at": "",
            "target_close_window_rows": 0,
            "target_close_window_volume": 0.0,
            "target_close_window_first_at": "",
            "target_close_window_last_at": "",
            "nearest_prior_date": "",
            "nearest_prior_close_window_volume": 0.0,
            "nearest_prior_close_window_rows": 0,
        }
    rows = rows.sort_values("bar_datetime").copy()
    clock = rows["bar_datetime"].dt.strftime("%H:%M")
    close_rows = rows[(clock >= "14:30") & (clock <= "15:00")].copy()
    return {
        "target_rows": int(len(rows)),
        "target_total_volume": float(_num(rows, "volume").sum()),
        "target_first_bar_at": rows["bar_datetime"].iloc[0],
        "target_last_bar_at": rows["bar_datetime"].iloc[-1],
        "target_close_window_rows": int(len(close_rows)),
        "target_close_window_volume": float(_num(close_rows, "volume").sum()) if not close_rows.empty else 0.0,
        "target_close_window_first_at": close_rows["bar_datetime"].iloc[0] if not close_rows.empty else "",
        "target_close_window_last_at": close_rows["bar_datetime"].iloc[-1] if not close_rows.empty else "",
    }


def _minute_candidate_rows(vt_symbol: str, trade_date: pd.Timestamp) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_date = trade_date.normalize()
    for path in _minute_paths(vt_symbol):
        try:
            frame = _read_csv(path)
        except Exception:
            continue
        if "bar_datetime" not in frame.columns:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
        frame = frame[frame["bar_datetime"].notna()].copy()
        for column in ["volume", "open_oi", "close_oi", "close"]:
            frame[column] = _num(frame, column)
        frame["_trade_date"] = frame["bar_datetime"].dt.normalize()
        exact = frame[frame["_trade_date"].eq(target_date)].copy()
        prior = frame[frame["_trade_date"].lt(target_date)].copy()
        metrics = _window_metrics(exact)
        nearest_prior_date = ""
        nearest_prior_close_volume = 0.0
        nearest_prior_close_rows = 0
        if not prior.empty:
            nearest_date = prior["_trade_date"].max()
            near_rows = prior[prior["_trade_date"].eq(nearest_date)].copy()
            near_clock = near_rows["bar_datetime"].dt.strftime("%H:%M")
            near_close = near_rows[(near_clock >= "14:30") & (near_clock <= "15:00")]
            nearest_prior_date = pd.Timestamp(nearest_date).date().isoformat()
            nearest_prior_close_volume = float(_num(near_close, "volume").sum()) if not near_close.empty else 0.0
            nearest_prior_close_rows = int(len(near_close))
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "trade_date": target_date.date().isoformat(),
                "minute_source_path": str(path),
                **metrics,
                "nearest_prior_date": nearest_prior_date,
                "nearest_prior_close_window_volume": nearest_prior_close_volume,
                "nearest_prior_close_window_rows": nearest_prior_close_rows,
            }
        )
    return rows


def _best_minute_evidence(candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidate_rows:
        return {
            "best_minute_source_path": "",
            "best_target_rows": 0,
            "best_target_total_volume": 0.0,
            "best_target_first_bar_at": "",
            "best_target_last_bar_at": "",
            "best_target_close_window_rows": 0,
            "best_target_close_window_volume": 0.0,
            "best_target_close_window_first_at": "",
            "best_target_close_window_last_at": "",
            "best_prior_minute_source_path": "",
            "best_nearest_prior_date": "",
            "best_nearest_prior_close_window_volume": 0.0,
            "best_nearest_prior_close_window_rows": 0,
        }
    def score(row: dict[str, Any]) -> tuple[float, int, float, int, str]:
        return (
            float(row.get("target_close_window_volume", 0.0) or 0.0),
            int(row.get("target_close_window_rows", 0) or 0),
            float(row.get("target_total_volume", 0.0) or 0.0),
            int(row.get("target_rows", 0) or 0),
            str(row.get("minute_source_path", "")),
        )

    best = sorted(candidate_rows, key=score, reverse=True)[0]
    best_prior = sorted(
        candidate_rows,
        key=lambda row: (
            float(row.get("nearest_prior_close_window_volume", 0.0) or 0.0),
            int(row.get("nearest_prior_close_window_rows", 0) or 0),
            str(row.get("minute_source_path", "")),
        ),
        reverse=True,
    )[0]
    return {
        "best_minute_source_path": best["minute_source_path"],
        "best_target_rows": int(best.get("target_rows", 0) or 0),
        "best_target_total_volume": float(best.get("target_total_volume", 0.0) or 0.0),
        "best_target_first_bar_at": best.get("target_first_bar_at", ""),
        "best_target_last_bar_at": best.get("target_last_bar_at", ""),
        "best_target_close_window_rows": int(best.get("target_close_window_rows", 0) or 0),
        "best_target_close_window_volume": float(best.get("target_close_window_volume", 0.0) or 0.0),
        "best_target_close_window_first_at": best.get("target_close_window_first_at", ""),
        "best_target_close_window_last_at": best.get("target_close_window_last_at", ""),
        "best_prior_minute_source_path": best_prior.get("minute_source_path", ""),
        "best_nearest_prior_date": best_prior.get("nearest_prior_date", ""),
        "best_nearest_prior_close_window_volume": float(best_prior.get("nearest_prior_close_window_volume", 0.0) or 0.0),
        "best_nearest_prior_close_window_rows": int(best_prior.get("nearest_prior_close_window_rows", 0) or 0),
    }


def build_detail() -> tuple[pd.DataFrame, pd.DataFrame]:
    hard = _read_csv(HARD_EVENTS_IN)
    pairs = _read_csv(ROLL_PAIR_IN) if ROLL_PAIR_IN.exists() else pd.DataFrame()
    if not pairs.empty:
        pairs["event_id"] = _num(pairs, "event_id").astype(int)
    for column in ["event_id", "order_volume", "daily_volume", "daily_close_oi", "close_price"]:
        hard[column] = _num(hard, column)
    hard["event_id"] = hard["event_id"].astype(int)
    hard["date"] = pd.to_datetime(hard["date"], errors="coerce").dt.normalize()

    detail_rows: list[dict[str, Any]] = []
    all_candidate_rows: list[dict[str, Any]] = []
    for _, event in hard.sort_values(["date", "vt_symbol"]).iterrows():
        event_id = int(event["event_id"])
        vt_symbol = str(event["vt_symbol"])
        trade_date = pd.Timestamp(event["date"]).normalize()
        daily = _daily_row(vt_symbol, trade_date)
        candidate_rows = _minute_candidate_rows(vt_symbol, trade_date)
        all_candidate_rows.extend({"event_id": event_id, **row} for row in candidate_rows)
        minute = _best_minute_evidence(candidate_rows)

        pair_row = pairs[pairs["event_id"].eq(event_id)].copy() if not pairs.empty else pd.DataFrame()
        pair_vt_symbol = str(pair_row.iloc[0].get("pair_vt_symbol", "")) if not pair_row.empty else ""
        if pair_vt_symbol == "nan":
            pair_vt_symbol = ""
        pair_daily = _daily_row(pair_vt_symbol, trade_date) if pair_vt_symbol else {}
        pair_order_pct = float(pair_row.iloc[0].get("pair_order_volume_to_day_volume_pct", np.nan)) if not pair_row.empty else np.nan
        old_to_pair_ratio = float(pair_row.iloc[0].get("old_to_pair_daily_volume_ratio", np.nan)) if not pair_row.empty else np.nan

        daily_volume = float(daily["daily_volume"])
        daily_oi = float(daily["daily_close_oi"])
        order_volume = float(event["order_volume"])
        daily_order_pct = order_volume / daily_volume * 100.0 if daily_volume > 0 else np.nan
        oi_order_pct = order_volume / daily_oi * 100.0 if daily_oi > 0 else np.nan
        target_close_volume = float(minute["best_target_close_window_volume"])
        close_window_participation_pct = order_volume / target_close_volume * 100.0 if target_close_volume > 0 else np.nan

        status = "closed_by_target_close_window"
        if target_close_volume <= 0 and daily_volume > 0:
            status = "daily_capacity_positive_but_close_window_missing"
        if target_close_volume <= 0 and daily_volume <= 0:
            status = "no_target_day_liquidity_evidence"
        if target_close_volume <= 0 and pair_vt_symbol:
            status = "roll_pair_daily_liquidity_positive_but_old_close_window_missing"
        if daily_order_pct > DAILY_VOLUME_HARD_PCT:
            status += "_daily_hard_pct"

        detail_rows.append(
            {
                "event_id": event_id,
                "date": trade_date.date().isoformat(),
                "vt_symbol": vt_symbol,
                "product_vt_symbol": event.get("product_vt_symbol", ""),
                "offset_type": event.get("offset_type", ""),
                "pos_change": float(event.get("pos_change", 0.0) or 0.0),
                "order_volume": order_volume,
                "close_price": float(event.get("close_price", np.nan)),
                **daily,
                "daily_order_volume_pct": daily_order_pct,
                "daily_order_oi_pct": oi_order_pct,
                **minute,
                "target_close_window_order_pct": close_window_participation_pct,
                "pair_vt_symbol": pair_vt_symbol,
                "pair_daily_volume": float(pair_daily.get("daily_volume", 0.0) or 0.0) if pair_daily else 0.0,
                "pair_daily_close_oi": float(pair_daily.get("daily_close_oi", 0.0) or 0.0) if pair_daily else 0.0,
                "pair_order_volume_to_day_volume_pct": pair_order_pct,
                "old_to_pair_daily_volume_ratio": old_to_pair_ratio,
                "evidence_status": status,
                "target_close_window_closed": int(target_close_volume >= MIN_CLOSE_WINDOW_VOLUME),
                "daily_capacity_positive": int(daily_volume > 0),
                "daily_order_pct_le_1pct": int(daily_order_pct <= DAILY_VOLUME_HARD_PCT) if not np.isnan(daily_order_pct) else 0,
                "daily_order_pct_le_0p5pct": int(daily_order_pct <= DAILY_VOLUME_SOFT_PCT) if not np.isnan(daily_order_pct) else 0,
                "pair_daily_capacity_positive": int(float(pair_daily.get("daily_volume", 0.0) or 0.0) > 0.0) if pair_daily else 0,
            }
        )
    return pd.DataFrame(detail_rows), pd.DataFrame(all_candidate_rows)


def build_gates(detail: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    total = int(len(detail))
    close_window_closed = int(_num(detail, "target_close_window_closed").sum())
    daily_positive = int(_num(detail, "daily_capacity_positive").sum())
    daily_le_1 = int(_num(detail, "daily_order_pct_le_1pct").sum())
    pair_count = int(detail["pair_vt_symbol"].astype(str).ne("").sum())
    pair_positive = int(_num(detail, "pair_daily_capacity_positive").sum())
    unresolved = total - close_window_closed
    hard_daily_over_1 = int(_num(detail, "daily_order_pct_le_1pct").rsub(1).clip(lower=0).sum())
    gates = pd.DataFrame(
        [
            {
                "gate": "hard_events_have_daily_liquidity",
                "passed": int(daily_positive == total),
                "actual": daily_positive,
                "threshold": total,
                "note": "所有硬容量事件当天日线成交量为正。",
            },
            {
                "gate": "hard_events_daily_order_pct_le_1pct",
                "passed": int(daily_le_1 == total),
                "actual": daily_le_1,
                "threshold": total,
                "note": "订单量/日成交量不超过1%。",
            },
            {
                "gate": "hard_events_have_target_close_window_volume",
                "passed": int(close_window_closed == total),
                "actual": close_window_closed,
                "threshold": total,
                "note": "目标日14:30-15:00收盘窗口分钟成交量为正。",
            },
            {
                "gate": "roll_pair_daily_capacity_available",
                "passed": int(pair_positive == pair_count),
                "actual": pair_positive,
                "threshold": pair_count,
                "note": "同日换月配对合约有日线成交量。",
            },
            {
                "gate": "residual_close_window_gap_closed",
                "passed": int(unresolved == 0),
                "actual": unresolved,
                "threshold": 0,
                "note": "没有残余收盘窗口缺口。",
            },
        ]
    )
    summary = {
        "hard_event_count": total,
        "daily_positive_count": daily_positive,
        "daily_order_pct_le_1pct_count": daily_le_1,
        "target_close_window_closed_count": close_window_closed,
        "residual_close_window_gap_count": unresolved,
        "pair_event_count": pair_count,
        "pair_daily_positive_count": pair_positive,
        "daily_order_pct_over_1pct_count": hard_daily_over_1,
        "max_daily_order_pct": float(_num(detail, "daily_order_volume_pct").max()) if total else np.nan,
        "max_target_close_window_order_pct": float(_num(detail, "target_close_window_order_pct").max()) if total else np.nan,
    }
    return gates, summary


def _make_chart(detail: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage573 Stage526 hard-capacity residual evidence", fontsize=14)

    labels = detail["vt_symbol"].astype(str) + "\n" + detail["date"].astype(str)
    x = np.arange(len(detail))

    ax = axes[0, 0]
    ax.bar(x, detail["daily_volume"], color="#4C78A8", label="daily volume")
    ax.scatter(x, detail["order_volume"], color="#E45756", label="order volume", zorder=3)
    ax.set_title("Target-day daily liquidity")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("lots")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[0, 1]
    colors = np.where(detail["target_close_window_closed"].eq(1), "#54A24B", "#E45756")
    ax.bar(x, detail["best_target_close_window_volume"], color=colors)
    ax.set_title("Target-day 14:30-15:00 minute volume")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("lots")
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    pct = detail["daily_order_volume_pct"].astype(float)
    colors = np.where(pct.le(0.5), "#54A24B", np.where(pct.le(1.0), "#F2CF5B", "#E45756"))
    ax.bar(x, pct, color=colors)
    ax.axhline(0.5, color="#F2CF5B", linestyle="--", linewidth=1, label="0.5%")
    ax.axhline(1.0, color="#E45756", linestyle="--", linewidth=1, label="1.0%")
    ax.set_title("Order / target-day daily volume")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("%")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    pair_view = detail[detail["pair_vt_symbol"].astype(str).ne("")].copy()
    if pair_view.empty:
        ax.text(0.5, 0.5, "No roll-pair events", ha="center", va="center")
        ax.set_axis_off()
    else:
        pair_labels = pair_view["vt_symbol"].astype(str) + "\n-> " + pair_view["pair_vt_symbol"].astype(str)
        px = np.arange(len(pair_view))
        ax.bar(px - 0.18, pair_view["daily_volume"], width=0.36, label="old contract", color="#4C78A8")
        ax.bar(px + 0.18, pair_view["pair_daily_volume"], width=0.36, label="pair contract", color="#54A24B")
        ax.set_title("Same-day roll pair daily volume")
        ax.set_xticks(px)
        ax.set_xticklabels(pair_labels, rotation=20, ha="right")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _make_report(detail: pd.DataFrame, candidates: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> str:
    lines = [
        "# Stage573 Stage526 Hard-Capacity Residual Evidence Audit",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Decision",
        "",
        f"`{decision['decision']}`",
        "",
        "## Key Takeaways",
        "",
        *[f"- {item}" for item in decision["key_takeaways"]],
        "",
        "## Hard Event Detail",
        "",
        _md_table(
            detail,
            [
                "event_id",
                "date",
                "vt_symbol",
                "offset_type",
                "order_volume",
                "daily_volume",
                "daily_order_volume_pct",
                "best_target_rows",
                "best_target_close_window_volume",
                "best_nearest_prior_date",
                "best_nearest_prior_close_window_volume",
                "pair_vt_symbol",
                "pair_daily_volume",
                "pair_order_volume_to_day_volume_pct",
                "evidence_status",
            ],
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Minute Candidate Snapshot",
        "",
        _md_table(
            candidates.sort_values(["event_id", "target_close_window_volume", "target_rows"], ascending=[True, False, False]),
            [
                "event_id",
                "vt_symbol",
                "trade_date",
                "target_rows",
                "target_total_volume",
                "target_first_bar_at",
                "target_last_bar_at",
                "target_close_window_volume",
                "nearest_prior_date",
                "nearest_prior_close_window_volume",
                "minute_source_path",
            ],
            max_rows=30,
        ),
        "",
        "## Outputs",
        "",
        f"- detail: `{DETAIL_PATH}`",
        f"- minute candidates: `{MINUTE_CANDIDATES_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- chart: `{CHART_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    detail, candidates = build_detail()
    gates, summary = build_gates(detail)

    passed = int(gates["passed"].sum())
    total = int(len(gates))
    unresolved = int(summary["residual_close_window_gap_count"])
    over_1pct = int(summary["daily_order_pct_over_1pct_count"])
    if unresolved == 0 and over_1pct == 0:
        decision_code = "hard_capacity_execution_evidence_closed"
    elif unresolved > 0:
        decision_code = "daily_capacity_improved_close_window_still_not_closed"
    else:
        decision_code = "close_window_closed_daily_capacity_hard_pct_remains"

    unresolved_symbols = detail[detail["target_close_window_closed"].eq(0)]["vt_symbol"].astype(str).tolist()
    daily_over = detail[detail["daily_order_volume_pct"].gt(DAILY_VOLUME_HARD_PCT)]["vt_symbol"].astype(str).tolist()
    key_takeaways = [
        f"Hard capacity daily liquidity is present for {summary['daily_positive_count']}/{summary['hard_event_count']} events.",
        f"Target-day close-window minute evidence is still present for only {summary['target_close_window_closed_count']}/{summary['hard_event_count']} events.",
        f"Residual close-window gaps: {', '.join(unresolved_symbols) if unresolved_symbols else 'none'}.",
        f"Daily order/volume >1% events: {', '.join(daily_over) if daily_over else 'none'}; max daily order pct={summary['max_daily_order_pct']:.4f}%.",
        f"Same-day roll pair daily capacity is present for {summary['pair_daily_positive_count']}/{summary['pair_event_count']} roll-pair events.",
    ]

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision_code,
        "passed_gates": passed,
        "total_gates": total,
        "summary": summary,
        "key_takeaways": key_takeaways,
        "outputs": {
            "detail": str(DETAIL_PATH),
            "minute_candidates": str(MINUTE_CANDIDATES_PATH),
            "gates": str(GATES_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(MINUTE_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_make_report(detail, candidates, gates, decision), encoding="utf-8")
    _make_chart(detail, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
