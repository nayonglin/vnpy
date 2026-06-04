from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage632_p2_event_outcome_schedule_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage632_p2_event_outcome_schedule_audit"

EVENT_SEED_LEDGER_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage631_p2_event_episode_ledger_contract_event_seed_ledger_stage631_p2_event_episode_ledger_contract_v1.csv"
)
TQSDK_DAILY_DIR = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04" / "CZCE"

OUTCOME_SCHEDULE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_outcome_schedule_{MODEL_TAG}.csv"
PRICE_AVAILABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_price_availability_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

HORIZONS = [20, 63, 126]
PRODUCT_PREFIX = {
    "CY.CZCE": "CY",
    "SR.CZCE": "SR",
}

REFERENCES = [
    "Event study window selection: https://eventstudy.de/docs/window-selection",
    "Event study data preparation: https://eventstudy.de/docs/data-preparation",
    "Purged cross-validation overview: https://en.wikipedia.org/wiki/Purged_cross-validation",
    "USDA WASDE release process: https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/world-agricultural-outlook-board/wasde-report",
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _str(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


def _date_string(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
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


def _prepare_event_seed(frame: pd.DataFrame) -> pd.DataFrame:
    seed = frame.copy()
    for column in [
        "event_id",
        "product_family",
        "product_vt_symbol",
        "source_name",
        "source_url",
        "event_family",
        "event_type",
        "received_at_utc",
        "pit_date",
    ]:
        seed[column] = _str(seed, column)
    for column in ["selector_allowed", "paper_or_whitelist_allowed", "verified_independent_episode"]:
        seed[column] = _num(seed, column).astype(int)
    seed["event_received_date"] = pd.to_datetime(seed["received_at_utc"].str.slice(0, 10), errors="coerce")
    group_size = seed.groupby(["product_vt_symbol", "event_received_date"])["event_id"].transform("count")
    seed["same_day_event_group_size"] = group_size.fillna(0).astype(int)
    return seed


def _load_product_proxy(product: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    prefix = PRODUCT_PREFIX[product]
    files = sorted(TQSDK_DAILY_DIR.glob(f"{prefix}*.csv"))
    parts: list[pd.DataFrame] = []
    non_empty_files = 0
    for path in files:
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if frame.empty:
            continue
        non_empty_files += 1
        frame["contract"] = path.stem
        frame["trade_date"] = pd.to_datetime(frame.get("trade_date"), errors="coerce")
        frame["close"] = _num(frame, "close", np.nan)
        frame["volume"] = _num(frame, "volume", 0.0)
        frame["close_oi"] = _num(frame, "close_oi", 0.0)
        frame = frame.dropna(subset=["trade_date", "close"])
        frame = frame[frame["close"].gt(0)]
        if not frame.empty:
            parts.append(frame[["trade_date", "contract", "close", "volume", "close_oi"]])
    if not parts:
        summary = {
            "product_vt_symbol": product,
            "prefix": prefix,
            "files_count": len(files),
            "non_empty_files": non_empty_files,
            "raw_rows": 0,
            "proxy_rows": 0,
            "tradable_proxy_rows": 0,
            "first_trade_date": "",
            "last_trade_date": "",
            "last_tradable_proxy_date": "",
            "latest_contract": "",
            "latest_close": np.nan,
            "latest_volume": np.nan,
            "latest_close_oi": np.nan,
            "status": "no_local_price_data",
        }
        return pd.DataFrame(), summary

    raw = pd.concat(parts, ignore_index=True)
    raw["tradable_proxy"] = (raw["volume"].gt(0) | raw["close_oi"].gt(0)).astype(int)
    proxy = (
        raw.sort_values(["trade_date", "tradable_proxy", "volume", "close_oi"], ascending=[True, False, False, False])
        .drop_duplicates("trade_date", keep="first")
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    tradable_proxy = proxy[proxy["tradable_proxy"].eq(1)].copy()
    latest = proxy.tail(1).iloc[0]
    latest_tradable_date = tradable_proxy["trade_date"].max() if not tradable_proxy.empty else pd.NaT
    summary = {
        "product_vt_symbol": product,
        "prefix": prefix,
        "files_count": len(files),
        "non_empty_files": non_empty_files,
        "raw_rows": int(len(raw)),
        "proxy_rows": int(len(proxy)),
        "tradable_proxy_rows": int(len(tradable_proxy)),
        "first_trade_date": _date_string(proxy["trade_date"].min()),
        "last_trade_date": _date_string(proxy["trade_date"].max()),
        "last_tradable_proxy_date": _date_string(latest_tradable_date),
        "latest_contract": str(latest["contract"]),
        "latest_close": float(latest["close"]),
        "latest_volume": float(latest["volume"]),
        "latest_close_oi": float(latest["close_oi"]),
        "status": "local_price_proxy_ready",
    }
    return proxy, summary


def _build_outcome_schedule(seed: pd.DataFrame, proxies: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, event in seed.iterrows():
        product = event["product_vt_symbol"]
        proxy = proxies.get(product, pd.DataFrame())
        event_date = event["event_received_date"]
        same_day_group_size = int(event["same_day_event_group_size"])
        pre_event_tradable_days = 0
        entry_date = pd.NaT
        entry_close = np.nan
        entry_contract = ""
        future = pd.DataFrame()
        if not proxy.empty and pd.notna(event_date):
            tradable = proxy[proxy["tradable_proxy"].eq(1)].copy()
            pre_event_tradable_days = int(tradable["trade_date"].le(event_date).sum())
            future = tradable[tradable["trade_date"].gt(event_date)].sort_values("trade_date").reset_index(drop=True)
            if not future.empty:
                entry = future.iloc[0]
                entry_date = entry["trade_date"]
                entry_close = float(entry["close"])
                entry_contract = str(entry["contract"])
        for horizon in HORIZONS:
            horizon_date = pd.NaT
            horizon_close = np.nan
            horizon_contract = ""
            close_to_close_return = np.nan
            mature = 0
            status = "entry_unavailable_local_data_ends_before_event"
            if not future.empty:
                if len(future) >= horizon:
                    outcome = future.iloc[horizon - 1]
                    horizon_date = outcome["trade_date"]
                    horizon_close = float(outcome["close"])
                    horizon_contract = str(outcome["contract"])
                    close_to_close_return = horizon_close / entry_close - 1.0 if entry_close > 0 else np.nan
                    mature = 1
                    status = "mature_outcome_available_but_selector_still_locked"
                else:
                    status = "entry_available_horizon_not_mature_or_missing"
            elif proxy.empty:
                status = "no_local_product_price_proxy"
            rows.append(
                {
                    "event_id": event["event_id"],
                    "product_family": event["product_family"],
                    "product_vt_symbol": product,
                    "event_family": event["event_family"],
                    "event_type": event["event_type"],
                    "source_name": event["source_name"],
                    "source_url": event["source_url"],
                    "received_at_utc": event["received_at_utc"],
                    "event_received_date": _date_string(event_date),
                    "same_day_event_group_size": same_day_group_size,
                    "horizon_trading_days": horizon,
                    "pre_event_tradable_days": pre_event_tradable_days,
                    "entry_date": _date_string(entry_date),
                    "entry_contract": entry_contract,
                    "entry_close": entry_close,
                    "horizon_date": _date_string(horizon_date),
                    "horizon_contract": horizon_contract,
                    "horizon_close": horizon_close,
                    "close_to_close_return": close_to_close_return,
                    "mature_outcome_available": mature,
                    "selector_allowed": 0,
                    "paper_or_whitelist_allowed": 0,
                    "verified_independent_episode": 0,
                    "independent_episode_candidate": 0,
                    "status": status,
                }
            )
    return pd.DataFrame(rows)


def _build_gates(seed: pd.DataFrame, schedule: pd.DataFrame, availability: pd.DataFrame) -> pd.DataFrame:
    selector_rows = int(schedule["selector_allowed"].sum()) if not schedule.empty else 0
    paper_rows = int(schedule["paper_or_whitelist_allowed"].sum()) if not schedule.empty else 0
    verified_rows = int(schedule["verified_independent_episode"].sum()) if not schedule.empty else 0
    mature_rows = int(schedule["mature_outcome_available"].sum()) if not schedule.empty else 0
    return_without_mature = int(
        schedule.loc[schedule["mature_outcome_available"].eq(0), "close_to_close_return"].notna().sum()
    ) if not schedule.empty else 0
    products_with_price = int(availability["status"].eq("local_price_proxy_ready").sum()) if not availability.empty else 0
    products_entry_available = int(schedule["entry_date"].astype(str).ne("").groupby(schedule["product_vt_symbol"]).max().sum()) if not schedule.empty else 0
    min_event_date = pd.to_datetime(seed["event_received_date"], errors="coerce").min() if not seed.empty else pd.NaT
    max_last_tradable = pd.to_datetime(availability["last_tradable_proxy_date"], errors="coerce").max() if not availability.empty else pd.NaT
    data_ends_before_event = int(pd.notna(min_event_date) and pd.notna(max_last_tradable) and max_last_tradable < min_event_date)
    same_day_overlap_groups = int(seed.groupby(["product_vt_symbol", "event_received_date"]).size().gt(1).sum()) if not seed.empty else 0
    rows = [
        {
            "gate": "event_seed_ledger_present",
            "passed": int(len(seed) > 0),
            "current": len(seed),
            "required": ">0",
            "note": "Stage631 event seed ledger is the only event input.",
        },
        {
            "gate": "local_price_proxy_present",
            "passed": int(products_with_price == len(PRODUCT_PREFIX)),
            "current": products_with_price,
            "required": len(PRODUCT_PREFIX),
            "note": "CY/SR local futures daily files can build product-level dominant proxy.",
        },
        {
            "gate": "horizon_rows_created",
            "passed": int(len(schedule) == len(seed) * len(HORIZONS)),
            "current": len(schedule),
            "required": len(seed) * len(HORIZONS),
            "note": "Each event seed should get 20/63/126 trading-day schedule rows.",
        },
        {
            "gate": "no_return_without_mature_outcome",
            "passed": int(return_without_mature == 0),
            "current": return_without_mature,
            "required": 0,
            "note": "Never calculate returns when entry/horizon prices are unavailable.",
        },
        {
            "gate": "local_data_ends_before_event_documented",
            "passed": int(data_ends_before_event == 1),
            "current": _date_string(max_last_tradable),
            "required": f"< {_date_string(min_event_date)}",
            "note": "Current local daily data ends before the 2026-06-04 event seeds.",
        },
        {
            "gate": "mature_outcomes_zero_fail_closed",
            "passed": int(mature_rows == 0),
            "current": mature_rows,
            "required": 0,
            "note": "No 20/63/126 outcome is mature in local data; keep selector locked.",
        },
        {
            "gate": "entry_available_products_zero_fail_closed",
            "passed": int(products_entry_available == 0),
            "current": products_entry_available,
            "required": 0,
            "note": "No product has next-trading-day entry after event in local data.",
        },
        {
            "gate": "same_day_overlap_tracked",
            "passed": int(same_day_overlap_groups >= 0),
            "current": same_day_overlap_groups,
            "required": "tracked",
            "note": "CY same-day multiple seeds cannot be independent episodes.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "Outcome schedule cannot enter selector.",
        },
        {
            "gate": "paper_whitelist_rows_zero",
            "passed": int(paper_rows == 0),
            "current": paper_rows,
            "required": 0,
            "note": "No paper or trading whitelist generated.",
        },
        {
            "gate": "verified_independent_episode_zero",
            "passed": int(verified_rows == 0),
            "current": verified_rows,
            "required": 0,
            "note": "This stage does not verify independent episodes.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(seed: pd.DataFrame, schedule: pd.DataFrame, availability: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage632 P2 event outcome schedule: seed events are not mature outcomes", fontsize=16)

    ax = axes[0, 0]
    min_event_date = pd.to_datetime(seed["event_received_date"], errors="coerce").min() if not seed.empty else pd.NaT
    products = availability["product_vt_symbol"].tolist()
    gaps = []
    labels = []
    for _, row in availability.iterrows():
        last_date = pd.to_datetime(row["last_tradable_proxy_date"], errors="coerce")
        gap = (min_event_date - last_date).days if pd.notna(min_event_date) and pd.notna(last_date) else np.nan
        gaps.append(gap)
        labels.append(row["last_tradable_proxy_date"])
    colors = ["tab:red" if pd.notna(gap) and gap > 0 else "tab:green" for gap in gaps]
    ax.bar(products, gaps, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Local tradable proxy ends before event")
    ax.set_ylabel("days from latest local tradable date to event")
    for idx, (gap, label) in enumerate(zip(gaps, labels)):
        ax.text(idx, 0 if pd.isna(gap) else gap, label, ha="center", va="bottom", fontsize=8)

    ax = axes[0, 1]
    if schedule.empty:
        ax.text(0.5, 0.5, "No schedule rows", ha="center", va="center")
        ax.set_axis_off()
    else:
        pivot = schedule.pivot_table(
            index="product_vt_symbol",
            columns="horizon_trading_days",
            values="mature_outcome_available",
            aggfunc="sum",
            fill_value=0,
        ).reindex(index=list(PRODUCT_PREFIX), columns=HORIZONS, fill_value=0)
        image = ax.imshow(pivot.values, aspect="auto", cmap="Greens", vmin=0, vmax=max(1, int(pivot.values.max())))
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([str(item) for item in pivot.columns])
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_title("Mature outcome rows by product/horizon")
        ax.set_xlabel("trading-day horizon")
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                ax.text(j, i, str(int(pivot.values[i, j])), ha="center", va="center", fontsize=9)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    seed_counts = seed.groupby("product_vt_symbol")["event_id"].count().reindex(list(PRODUCT_PREFIX), fill_value=0)
    overlap_groups = (
        seed.groupby(["product_vt_symbol", "event_received_date"]).size().groupby("product_vt_symbol").max().reindex(list(PRODUCT_PREFIX), fill_value=0)
        if not seed.empty
        else pd.Series(0, index=list(PRODUCT_PREFIX))
    )
    x = np.arange(len(seed_counts))
    ax.bar(x - 0.18, seed_counts.values, width=0.36, label="event seeds")
    ax.bar(x + 0.18, overlap_groups.values, width=0.36, label="max same-day group")
    ax.set_xticks(x)
    ax.set_xticklabels(seed_counts.index)
    ax.set_title("Event seeds and overlap")
    ax.set_ylabel("count")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes fail-closed locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    seed: pd.DataFrame,
    schedule: pd.DataFrame,
    availability: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage632 P2 Event Outcome Schedule Audit Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        f"- event_seed_ledger: `{EVENT_SEED_LEDGER_PATH}`",
        f"- tq_sdk_daily_dir: `{TQSDK_DAILY_DIR}`",
        "",
        "## External Research Judgement",
        "",
        "事件研究的 outcome 必须按交易日窗口定义，并且要把事件窗口、估计窗口、验证窗口隔离。当前 Stage631 只有事件种子和时间戳，不能直接证明可预测收益；Stage632 的职责是建立 20/63/126 交易日 outcome 到期表，并在价格或窗口未成熟时 fail-closed。",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- event seed rows: `{decision['event_seed_rows']}`",
        f"- horizon rows: `{decision['horizon_rows']}`",
        f"- mature outcome rows: `{decision['mature_outcome_rows']}`",
        f"- entry available rows: `{decision['entry_available_rows']}`",
        f"- products with local price proxy: `{decision['products_with_local_price_proxy']}`",
        f"- products with entry available after event: `{decision['products_entry_available']}`",
        f"- same-day overlap groups: `{decision['same_day_overlap_groups']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Price Availability",
        "",
        _md_table(availability),
        "",
        "## Outcome Schedule",
        "",
        _md_table(
            schedule,
            columns=[
                "event_id",
                "product_vt_symbol",
                "event_type",
                "event_received_date",
                "horizon_trading_days",
                "entry_date",
                "horizon_date",
                "mature_outcome_available",
                "status",
            ],
        ),
        "",
        "## Event Seeds",
        "",
        _md_table(
            seed,
            columns=[
                "event_id",
                "product_vt_symbol",
                "event_type",
                "received_at_utc",
                "same_day_event_group_size",
                "selector_allowed",
            ],
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- CY/SR 均能从本地 TQSDK 文件构造产品级主力日线代理，但最新可交易代理日期早于 2026-06-04 事件日。",
        "- 20/63/126 交易日 outcome 行已创建，成熟 outcome 为 0，因此没有任何后验收益被计算。",
        "- CY 同日两个事件种子仍然是重叠事件，只能作为同一时间簇，不能计为独立 episode。",
        "- 该阶段只完成 outcome schedule 与 fail-closed 闸门，不产生 selector、paper whitelist 或交易权限。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    seed = _prepare_event_seed(_read_csv(EVENT_SEED_LEDGER_PATH))
    product_symbols = sorted(set(seed["product_vt_symbol"]) & set(PRODUCT_PREFIX))
    proxies: dict[str, pd.DataFrame] = {}
    availability_rows: list[dict[str, Any]] = []
    for product in product_symbols:
        proxy, summary = _load_product_proxy(product)
        proxies[product] = proxy
        availability_rows.append(summary)
    availability = pd.DataFrame(availability_rows).sort_values("product_vt_symbol").reset_index(drop=True)
    schedule = _build_outcome_schedule(seed[seed["product_vt_symbol"].isin(product_symbols)].copy(), proxies)
    gates = _build_gates(seed[seed["product_vt_symbol"].isin(product_symbols)].copy(), schedule, availability)

    selector_rows = int(schedule["selector_allowed"].sum()) if not schedule.empty else 0
    paper_rows = int(schedule["paper_or_whitelist_allowed"].sum()) if not schedule.empty else 0
    mature_rows = int(schedule["mature_outcome_available"].sum()) if not schedule.empty else 0
    entry_available_rows = int(schedule["entry_date"].astype(str).ne("").sum()) if not schedule.empty else 0
    products_entry_available = int(schedule["entry_date"].astype(str).ne("").groupby(schedule["product_vt_symbol"]).max().sum()) if not schedule.empty else 0
    same_day_overlap_groups = int(seed.groupby(["product_vt_symbol", "event_received_date"]).size().gt(1).sum()) if not seed.empty else 0
    hard_gates_passed = int(gates["passed"].sum()) if not gates.empty else 0
    hard_gates_total = int(len(gates))
    decision = {
        "decision": "p2_event_outcome_schedule_created_outcomes_not_mature_selector_locked",
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "event_seed_rows": int(len(seed[seed["product_vt_symbol"].isin(product_symbols)])),
        "products_covered": int(len(product_symbols)),
        "horizon_rows": int(len(schedule)),
        "mature_outcome_rows": mature_rows,
        "entry_available_rows": entry_available_rows,
        "products_with_local_price_proxy": int(availability["status"].eq("local_price_proxy_ready").sum()) if not availability.empty else 0,
        "products_entry_available": products_entry_available,
        "same_day_overlap_groups": same_day_overlap_groups,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": paper_rows,
        "verified_independent_episode_rows": int(schedule["verified_independent_episode"].sum()) if not schedule.empty else 0,
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "outcome_schedule_path": str(OUTCOME_SCHEDULE_PATH),
        "price_availability_path": str(PRICE_AVAILABILITY_PATH),
        "chart_path": str(CHART_PATH),
    }

    schedule.to_csv(OUTCOME_SCHEDULE_PATH, index=False, encoding="utf-8-sig")
    availability.to_csv(PRICE_AVAILABILITY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report(generated_at, seed, schedule, availability, gates, decision)
    _write_chart(seed, schedule, availability, gates)
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
