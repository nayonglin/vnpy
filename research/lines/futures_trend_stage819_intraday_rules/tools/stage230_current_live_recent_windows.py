from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STAGE = "Stage230"
MODEL_TAG = "stage230_current_live_2025_2026_recent_windows_v1"

LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "outputs" / "stage230_current_live_recent_windows"
SUMMARY_PATH = OUTPUT_DIR / "summary.csv"
CURVES_PATH = OUTPUT_DIR / "curves.csv"
TRADES_PATH = OUTPUT_DIR / "trades.csv"
CHART_PATH = OUTPUT_DIR / "equity_nav_drawdown.png"
MANIFEST_PATH = OUTPUT_DIR / "identity_manifest.json"
DECISION_PATH = OUTPUT_DIR / "decision.json"
REPORT_PATH = OUTPUT_DIR / "report.md"
MINUTE_PATCH_PATH = OUTPUT_DIR / "minute_patch.csv"
MINUTE_COVERAGE_PATH = OUTPUT_DIR / "open_day_minute_coverage.csv"
MINUTE_MISSING_PATH = OUTPUT_DIR / "open_day_minute_missing.csv"
MINUTE_PATCH_FETCH_STATUS_PATH = OUTPUT_DIR / "minute_patch_fetch_status.csv"
MINIMUM_OPEN_DAY_MINUTE_BARS = 200


@dataclass(frozen=True)
class WindowSpec:
    name: str
    label: str
    start: pd.Timestamp
    end: pd.Timestamp


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_requested_windows(latest_complete_date: pd.Timestamp) -> tuple[WindowSpec, ...]:
    end = pd.Timestamp(latest_complete_date).normalize()
    if end < pd.Timestamp("2026-01-01"):
        raise ValueError(f"latest_complete_date_before_2026_start:{end.date()}")
    return (
        WindowSpec("since_2025", "2025年1月至最新完整交易日", pd.Timestamp("2025-01-01"), end),
        WindowSpec("since_2026", "2026年1月至最新完整交易日", pd.Timestamp("2026-01-01"), end),
    )


def latest_complete_daily_date(overviews: list[Any]) -> pd.Timestamp:
    dates: list[pd.Timestamp] = []
    for row in overviews:
        interval = getattr(getattr(row, "interval", None), "value", getattr(row, "interval", ""))
        if str(interval).lower() not in {"d", "1d", "daily"}:
            continue
        end = pd.to_datetime(getattr(row, "end", None), errors="coerce")
        if pd.notna(end):
            dates.append(pd.Timestamp(end).tz_localize(None).normalize())
    if not dates:
        raise RuntimeError("no_daily_bar_overview_end_date")
    return max(dates)


def summarize_window(
    daily: pd.DataFrame,
    *,
    window_name: str,
    initial_capital: float,
) -> dict[str, Any]:
    if daily.empty:
        raise ValueError(f"empty_window:{window_name}")
    ordered = daily.copy()
    ordered["date"] = pd.to_datetime(ordered["date"], errors="raise").dt.normalize()
    ordered = ordered.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(ordered["account_equity"], errors="raise").astype(float)
    net_pnl = pd.to_numeric(ordered.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    slippage = pd.to_numeric(ordered.get("slippage", 0.0), errors="coerce").fillna(0.0)
    trade_count = pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    margin = pd.to_numeric(
        ordered.get("broker10_total_margin_exact", 0.0), errors="coerce"
    ).fillna(0.0)
    peaks = equity.cummax()
    drawdown_pct = (equity / peaks.replace(0.0, np.nan) - 1.0).fillna(0.0) * 100.0
    daily_returns = equity.pct_change().fillna(equity.iloc[0] / float(initial_capital) - 1.0)
    return_std = float(daily_returns.std(ddof=1))
    sharpe = float(daily_returns.mean() / return_std * np.sqrt(252.0)) if return_std > 0 else 0.0
    nonzero = net_pnl[net_pnl.abs().gt(1e-12)]
    margin_pct = (margin / equity.replace(0.0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return {
        "window_name": window_name,
        "actual_start": ordered["date"].iloc[0].date().isoformat(),
        "actual_end": ordered["date"].iloc[-1].date().isoformat(),
        "trading_days": int(len(ordered)),
        "initial_capital": float(initial_capital),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / float(initial_capital) - 1.0) * 100.0),
        "max_dd_pct": float(drawdown_pct.min()),
        "sharpe": sharpe,
        "total_slippage": float(slippage.sum()),
        "total_trade_count": float(trade_count.sum()),
        "nonzero_daily_win_rate_pct": float((nonzero > 0.0).mean() * 100.0) if len(nonzero) else 0.0,
        "max_broker10_margin_to_equity_pct": float(margin_pct.max()),
        "days_over_100pct": int(margin_pct.gt(100.0).sum()),
    }


def audit_open_day_minute_coverage(
    trades: pd.DataFrame,
    minute_bars: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if trades.empty:
        return {
            "open_trade_count": 0,
            "covered_open_trade_count": 0,
            "missing_open_trade_count": 0,
            "open_day_coverage_pct": 100.0,
            "minimum_required_bars_per_open_day": MINIMUM_OPEN_DAY_MINUTE_BARS,
            "minimum_observed_bars_per_covered_open_day": None,
        }, pd.DataFrame(
            columns=["vt_symbol", "required_date", "minute_bar_count", "minimum_required_bars"]
        )
    data = trades.copy()
    offset = data.get("offset", pd.Series("", index=data.index)).astype(str).str.strip().str.lower()
    opens = data[offset.isin({"开", "open"})].copy()
    opens["required_date"] = pd.to_datetime(opens["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    opens = opens.dropna(subset=["vt_symbol", "required_date"])

    bars = minute_bars.copy()
    if bars.empty:
        bar_counts: dict[tuple[str, str], int] = {}
    else:
        bars["required_date"] = pd.to_datetime(bars["bar_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        bar_counts = {
            (str(symbol), str(required_date)): int(count)
            for (symbol, required_date), count in bars.groupby(
                [bars["vt_symbol"].astype(str), bars["required_date"].astype(str)], dropna=False
            ).size().items()
        }
    opens["minute_bar_count"] = [
        bar_counts.get((str(symbol), str(required_date)), 0)
        for symbol, required_date in zip(opens["vt_symbol"], opens["required_date"], strict=False)
    ]
    opens["minimum_required_bars"] = MINIMUM_OPEN_DAY_MINUTE_BARS
    opens["covered"] = opens["minute_bar_count"].ge(MINIMUM_OPEN_DAY_MINUTE_BARS).astype(int)
    missing = (
        opens[opens["covered"].eq(0)][
            ["vt_symbol", "required_date", "minute_bar_count", "minimum_required_bars"]
        ]
        .drop_duplicates()
        .sort_values(["required_date", "vt_symbol"])
        .reset_index(drop=True)
    )
    open_count = int(len(opens))
    covered_count = int(opens["covered"].sum())
    covered_bar_counts = opens.loc[opens["covered"].eq(1), "minute_bar_count"]
    audit = {
        "open_trade_count": open_count,
        "covered_open_trade_count": covered_count,
        "missing_open_trade_count": int(open_count - covered_count),
        "open_day_coverage_pct": float(covered_count / open_count * 100.0) if open_count else 100.0,
        "minimum_required_bars_per_open_day": MINIMUM_OPEN_DAY_MINUTE_BARS,
        "minimum_observed_bars_per_covered_open_day": (
            int(covered_bar_counts.min()) if not covered_bar_counts.empty else None
        ),
    }
    return audit, missing


def require_complete_open_day_minute_coverage(audit: Mapping[str, Any]) -> None:
    missing_count = int(audit.get("missing_open_trade_count", 0) or 0)
    if missing_count:
        coverage = float(audit.get("open_day_coverage_pct", 0.0) or 0.0)
        raise RuntimeError(f"open_day_minute_coverage_incomplete:{missing_count}:coverage_pct={coverage:.4f}")


def _load_stage229():
    path = Path(__file__).with_name("stage229_c9_30w_capital_ab.py")
    spec = importlib.util.spec_from_file_location("stage229_c9_30w_capital_ab", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot_load_stage229:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_combined_minute_bars(modules: Any, metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    vt_symbols = set(str(item) for item in metadata.get("vt_symbols", []))
    base = modules.s901._load_stage861_full_minute_bars(vt_symbols)
    frames = [base.assign(minute_patch_source="stage861_frozen_source")]
    patch_rows = 0
    if MINUTE_PATCH_PATH.exists():
        patch = pd.read_csv(MINUTE_PATCH_PATH, encoding="utf-8-sig")
        patch["bar_datetime"] = pd.to_datetime(patch["bar_datetime"], errors="coerce")
        patch["bar_date"] = pd.to_datetime(patch["bar_date"], errors="coerce").dt.normalize()
        patch = patch[
            patch["vt_symbol"].astype(str).isin(vt_symbols)
        ].dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"])
        patch_rows = int(len(patch))
        frames.append(patch.assign(minute_patch_source="stage230_exact_open_day_patch"))
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = (
        combined.sort_values(["vt_symbol", "bar_datetime", "minute_patch_source"])
        .drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
        .reset_index(drop=True)
    )
    audit = {
        "base_source": str(modules.s901.s861.FULL_MINUTE_BARS_PATH),
        "patch_source": str(MINUTE_PATCH_PATH),
        "patch_exists": bool(MINUTE_PATCH_PATH.exists()),
        "base_rows": int(len(base)),
        "patch_rows": patch_rows,
        "patch_sha256": sha256_file(MINUTE_PATCH_PATH),
        "patch_contract_date_group_count": (
            int(patch.groupby(["vt_symbol", "bar_date"]).ngroups) if patch_rows else 0
        ),
        "patch_fetch_status_source": str(MINUTE_PATCH_FETCH_STATUS_PATH),
        "patch_fetch_status_sha256": sha256_file(MINUTE_PATCH_FETCH_STATUS_PATH),
        "patch_fetch_status_rows": (
            int(len(pd.read_csv(MINUTE_PATCH_FETCH_STATUS_PATH, encoding="utf-8-sig")))
            if MINUTE_PATCH_FETCH_STATUS_PATH.exists()
            else 0
        ),
        "combined_rows": int(len(combined)),
        "combined_symbol_count": int(combined["vt_symbol"].nunique()),
        "combined_min_date": pd.to_datetime(combined["bar_date"], errors="coerce").min(),
        "combined_max_date": pd.to_datetime(combined["bar_date"], errors="coerce").max(),
    }
    return combined, audit


def _plot(curves: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    colors = {"since_2025": "#2f6bff", "since_2026": "#e1812c"}
    for window_name, group in curves.groupby("window_name", sort=False):
        ordered = group.sort_values("date")
        color = colors.get(str(window_name))
        axes[0].plot(ordered["date"], ordered["account_equity"], label=window_name, color=color)
        axes[1].plot(ordered["date"], ordered["normalized_nav"], label=window_name, color=color)
        axes[2].plot(ordered["date"], ordered["drawdown_pct"], label=window_name, color=color)
    axes[0].set_title("Current Live Stage847-C9-15w - Equity")
    axes[0].set_ylabel("CNY")
    axes[1].set_title("Normalized NAV")
    axes[1].set_ylabel("NAV")
    axes[2].set_title("Drawdown")
    axes[2].set_ylabel("%")
    for axis in axes:
        axis.grid(alpha=0.22)
        axis.legend(loc="best")
    axes[-1].set_xlabel("Date")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _md_table(frame: pd.DataFrame) -> str:
    view = frame.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    s229 = _load_stage229()
    modules = s229._load_production_modules()
    live_cfg = modules.live_cfg
    if float(live_cfg.OFFICIAL_LIVE_CAPITAL) != 150_000.0:
        raise RuntimeError(f"official_live_capital_drift:{live_cfg.OFFICIAL_LIVE_CAPITAL}")

    from vnpy.trader.database import get_database

    latest_complete_date = latest_complete_daily_date(get_database().get_bar_overview())
    windows = build_requested_windows(latest_complete_date)
    metadata = modules.s901.s513._metadata()
    minute_bars, minute_source_audit = _load_combined_minute_bars(modules, metadata)
    minute_groups = modules.s847.s825._minute_groups(minute_bars)
    original_ensure = modules.s901._ensure_c9_minute_bars

    def _ensure_stage230_minutes(_metadata: dict[str, Any]) -> dict[str, Any]:
        modules.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = minute_groups
        return dict(minute_source_audit)

    modules.s901._ensure_c9_minute_bars = _ensure_stage230_minutes
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    minute_audits: dict[str, Any] = {}
    coverage_rows: list[dict[str, Any]] = []
    missing_frames: list[pd.DataFrame] = []

    try:
        for window in windows:
            print(f"[{STAGE}] start {window.name} {window.start.date()}..{window.end.date()}", flush=True)
            daily, frames, spec, minute_audit = s229._run_arm(
                modules,
                metadata,
                arm=s229.A_ARM,
                target_capital=float(live_cfg.OFFICIAL_LIVE_CAPITAL),
                analysis_start=window.start,
                analysis_end=window.end,
            )
            if str(spec.profile) != str(live_cfg.OFFICIAL_LIVE_PROFILE_NAME):
                raise RuntimeError(f"official_profile_mismatch:{spec.profile}")
            trades = frames.get("trades", pd.DataFrame()).copy()
            coverage_audit, missing = audit_open_day_minute_coverage(trades, minute_bars)
            coverage_audit["window_name"] = window.name
            coverage_rows.append(coverage_audit)
            if not missing.empty:
                missing["window_name"] = window.name
                missing_frames.append(missing)
            pd.DataFrame(coverage_rows).to_csv(MINUTE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
            current_missing = (
                pd.concat(missing_frames, ignore_index=True, sort=False)
                if missing_frames
                else pd.DataFrame(columns=["vt_symbol", "required_date", "window_name"])
            )
            current_missing.to_csv(MINUTE_MISSING_PATH, index=False, encoding="utf-8-sig")
            require_complete_open_day_minute_coverage(coverage_audit)

            row = summarize_window(
                daily,
                window_name=window.name,
                initial_capital=float(live_cfg.OFFICIAL_LIVE_CAPITAL),
            )
            row.update(
                {
                    "stage": STAGE,
                    "model_tag": MODEL_TAG,
                    "window_label": window.label,
                    "official_live_alias": live_cfg.OFFICIAL_LIVE_ALIAS,
                    "official_live_version": live_cfg.OFFICIAL_LIVE_VERSION,
                    "official_live_profile": live_cfg.OFFICIAL_LIVE_PROFILE_NAME,
                    "open_day_minute_coverage_pct": coverage_audit["open_day_coverage_pct"],
                }
            )
            summary_rows.append(row)
            minute_audits[window.name] = {**minute_audit, **coverage_audit}

            curve = s229.add_curve_fields(daily, float(live_cfg.OFFICIAL_LIVE_CAPITAL), s229.A_ARM)
            curve["window_name"] = window.name
            curve_frames.append(curve)
            if not trades.empty:
                trades["window_name"] = window.name
                trade_frames.append(trades)
            print(
                f"[{STAGE}] done {window.name} end={row['end_equity']:.2f} "
                f"return={row['total_return_pct']:.4f}% dd={row['max_dd_pct']:.4f}% "
                f"open_day_minutes={coverage_audit['open_day_coverage_pct']:.2f}%",
                flush=True,
            )
    finally:
        modules.s901._ensure_c9_minute_bars = original_ensure

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    trades = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    _plot(curves)

    manifest = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(),
        "production_root": str(s229.PRODUCTION_ROOT),
        "production_head": s229._run_git("rev-parse", "HEAD"),
        "production_status_porcelain": s229._run_git("status", "--porcelain"),
        "official_live_manifest": live_cfg.build_official_live_manifest(),
        "latest_complete_date": latest_complete_date.date().isoformat(),
        "latest_complete_date_basis": "local vn.py daily database latest completed trading day",
        "windows": [
            {"name": item.name, "start": item.start.date().isoformat(), "end": item.end.date().isoformat()}
            for item in windows
        ],
        "minute_audits": minute_audits,
        "minute_source_audit": minute_source_audit,
        "ctp_connected": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_counter_scope": "historical_backtest_only_no_ctp_gateway_or_order_adapter_imported",
    }
    MANIFEST_PATH.write_text(json.dumps(json_safe(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decision = {
        "decision": "current_live_recent_windows_backtest_completed_no_strategy_change",
        "overfit_reflection_after": "否；两个起点由用户事前指定，同一正式身份独立冷启动，未调参、未筛选品种或窗口。",
        "continue_value_after": "有；可作为当前正式版近两年与今年以来的健康度快照，但不是未来收益保证。",
        "data_limitation": "截止日动态读取本地vn.py日线数据库；Stage861冻结分钟源叠加Stage230精确开仓日补丁，两个独立路径实际开仓日均须至少200根分钟K且覆盖率100%，否则程序fail-close。",
        "auto_live_change": False,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "trades": str(TRADES_PATH),
            "chart": str(CHART_PATH),
            "manifest": str(MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "minute_patch": str(MINUTE_PATCH_PATH),
            "minute_coverage": str(MINUTE_COVERAGE_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# Stage230 当前正式版近两年窗口回测",
        "",
        f"- 生成时间：`{datetime.now().astimezone().isoformat()}`",
        f"- 正式身份：`{live_cfg.OFFICIAL_LIVE_ALIAS}` / `{live_cfg.OFFICIAL_LIVE_VERSION}`。",
        f"- 资金：`{live_cfg.OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- 最新完整交易日：`{latest_complete_date.date()}`。",
        "- 两个窗口均为独立冷启动；不从全周期曲线切片，不继承窗口前持仓或权益。",
        "- 两个窗口实际开仓日均须至少200根分钟K且覆盖率100%；覆盖不足时程序直接失败，不输出成功结论。",
        "- 纯历史回测路径未导入CTP gateway或订单适配器；未连接CTP，未提交或撤销订单。",
        "",
        "## 结果",
        "",
        _md_table(summary[[
            "window_name", "actual_start", "actual_end", "trading_days", "end_equity",
            "total_return_pct", "max_dd_pct", "sharpe", "total_slippage",
            "total_trade_count", "nonzero_daily_win_rate_pct",
            "max_broker10_margin_to_equity_pct", "days_over_100pct",
            "open_day_minute_coverage_pct",
        ]]),
        "",
        "## 结论",
        "",
        f"- {decision['decision']}。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        f"- 数据限制：{decision['data_limitation']}",
        "- 本阶段不修改正式策略、配置、AI池或执行链路。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
