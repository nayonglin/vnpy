from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage073"
MODEL_TAG = "stage073_official_c9_path_governance_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage073_official_c9_path_governance_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
STAGE053_OUT = LINE_DIR / "outputs" / "stage053_valuable_versions_halfyear_curves"
OUT = LINE_DIR / "outputs" / "stage073_official_c9_path_governance_proxy"
STAGES_DIR = LINE_DIR / "stages"

OFFICIAL = "Official C9/15w Stage847"
BASE_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
TOTAL_CAPITAL_30W = BASE_CAPITAL + RESERVE_CAPITAL
REQUESTED_END = pd.Timestamp("2026-06-30")

CURVES_IN = STAGE053_OUT / "rebuilt_c9_v2_stage053_halfyear_curves_stage053_valuable_versions_halfyear_curves_v1.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
DEFECT_PATH = OUT / f"{OUTPUT_PREFIX}_official_defect_by_start_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_{MODEL_TAG}.csv"
CHART_EQUITY_RECENT_PATH = OUT / f"{OUTPUT_PREFIX}_equity_recent_starts_{MODEL_TAG}.png"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_by_start_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_by_start_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

VARIANTS = (
    "official_c9_15w",
    "account_30w_idle_reserve_view",
    "dd25_half_risk_proxy",
)
VARIANT_LABELS = {
    "official_c9_15w": "Official C9 15w",
    "account_30w_idle_reserve_view": "30w idle reserve view",
    "dd25_half_risk_proxy": "DD25 half-risk proxy",
}
VARIANT_COLORS = {
    "official_c9_15w": "#111827",
    "account_30w_idle_reserve_view": "#059669",
    "dd25_half_risk_proxy": "#dc2626",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, str | bytes):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _max_consecutive_true(mask: pd.Series) -> int:
    max_run = 0
    current = 0
    for value in mask.astype(bool):
        if value:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return int(max_run)


def _read_official_curves() -> pd.DataFrame:
    curves = pd.read_csv(CURVES_IN)
    curves = curves[curves["version"].astype(str).eq(OFFICIAL)].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves = curves.dropna(subset=["date"])
    curves = curves[curves["date"].le(REQUESTED_END)].copy()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["official_equity"] = pd.to_numeric(curves["equity"], errors="coerce").ffill()
    return curves.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def _build_dd25_half_risk_proxy(group: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    frame = group.sort_values("date").reset_index(drop=True)
    official = pd.to_numeric(frame["official_equity"], errors="coerce").ffill().to_numpy(dtype=float)
    simulated: list[float] = [float(official[0])]
    active_flags: list[int] = [0]
    active = False
    for idx in range(1, len(official)):
        prev_equity = simulated[-1]
        prev_peak = max(simulated)
        prev_drawdown = prev_equity / prev_peak - 1.0 if prev_peak > 0 else 0.0
        if active and prev_drawdown >= -0.10:
            active = False
        elif not active and prev_drawdown <= -0.25:
            active = True

        multiplier = 0.5 if active else 1.0
        official_pnl = float(official[idx] - official[idx - 1])
        simulated.append(prev_equity + official_pnl * multiplier)
        active_flags.append(1 if active else 0)
    return pd.Series(simulated), pd.Series(active_flags)


def _variant_curves(group: pd.DataFrame) -> pd.DataFrame:
    frame = group.sort_values("date").reset_index(drop=True)
    start = str(frame["requested_start_month"].iloc[0])
    official_equity = pd.to_numeric(frame["official_equity"], errors="coerce").ffill()

    rows: list[pd.DataFrame] = []
    for version, account_capital, account_equity, active_days in (
        ("official_c9_15w", BASE_CAPITAL, official_equity, pd.Series(0, index=frame.index)),
        (
            "account_30w_idle_reserve_view",
            TOTAL_CAPITAL_30W,
            official_equity + RESERVE_CAPITAL,
            pd.Series(0, index=frame.index),
        ),
    ):
        data = pd.DataFrame(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "version": version,
                "variant_label": VARIANT_LABELS[version],
                "requested_start_month": start,
                "date": frame["date"],
                "account_capital": account_capital,
                "account_equity": pd.to_numeric(account_equity, errors="coerce"),
                "official_equity": official_equity,
                "reserve_capital": RESERVE_CAPITAL if version == "account_30w_idle_reserve_view" else 0.0,
                "proxy_multiplier": 1.0,
                "proxy_active": active_days,
                "note": "read official true-engine curve; no strategy rerun",
            }
        )
        data["nav"] = data["account_equity"] / account_capital
        rows.append(data)

    brake_equity, active_flags = _build_dd25_half_risk_proxy(frame)
    brake = pd.DataFrame(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "version": "dd25_half_risk_proxy",
            "variant_label": VARIANT_LABELS["dd25_half_risk_proxy"],
            "requested_start_month": start,
            "date": frame["date"],
            "account_capital": BASE_CAPITAL,
            "account_equity": brake_equity,
            "official_equity": official_equity,
            "reserve_capital": 0.0,
            "proxy_multiplier": np.where(active_flags.astype(bool), 0.5, 1.0),
            "proxy_active": active_flags.astype(int),
            "note": "curve-level no-lookahead proxy: previous equity DD <= -25% halves next-day PnL until DD >= -10%",
        }
    )
    brake["nav"] = brake["account_equity"] / BASE_CAPITAL
    rows.append(brake)
    return pd.concat(rows, ignore_index=True)


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    capital = float(frame["account_capital"].iloc[0])
    dd = _drawdown_pct(equity)
    below = equity < capital - 1e-9
    below_dates = frame.loc[below, "date"].reset_index(drop=True)
    min_idx = int(equity.idxmin())
    last_below = below_dates.iloc[-1] if not below_dates.empty else pd.NaT
    recovered_after_last = ""
    if not below_dates.empty:
        after = frame[frame["date"].gt(last_below)]
        after = after[pd.to_numeric(after["account_equity"], errors="coerce").ge(capital - 1e-9)]
        if not after.empty:
            recovered_after_last = pd.Timestamp(after["date"].iloc[0]).date().isoformat()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": str(frame["version"].iloc[0]),
        "variant_label": str(frame["variant_label"].iloc[0]),
        "requested_start_month": str(frame["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(frame["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(frame["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(frame)),
        "account_capital": capital,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "max_drawdown_pct": float(dd.min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.iloc[min_idx]),
        "min_equity_date": pd.Timestamp(frame["date"].iloc[min_idx]).date().isoformat(),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
        "first_below_initial": pd.Timestamp(below_dates.iloc[0]).date().isoformat() if not below_dates.empty else "",
        "last_below_initial": pd.Timestamp(last_below).date().isoformat() if not below_dates.empty else "",
        "recovered_after_last_below": recovered_after_last,
        "proxy_active_days": int(pd.to_numeric(frame.get("proxy_active", 0), errors="coerce").fillna(0).sum()),
    }


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for sample, data in (
        ("all_2018_2026", summary),
        ("starts_2020_2026", summary[summary["requested_start_month"].astype(str).ge("2020-01")]),
        ("starts_2021_07_2026", summary[summary["requested_start_month"].astype(str).ge("2021-07")]),
    ):
        for version in VARIANTS:
            group = data[data["version"].astype(str).eq(version)].copy()
            if group.empty:
                continue
            returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
            dds = pd.to_numeric(group["max_drawdown_pct"], errors="coerce")
            days = pd.to_numeric(group["days_below_initial"], errors="coerce").fillna(0)
            rows.append(
                {
                    "sample": sample,
                    "version": version,
                    "variant_label": VARIANT_LABELS[version],
                    "start_count": int(len(group)),
                    "positive_count": int(returns.gt(0).sum()),
                    "min_return_pct": float(returns.min()),
                    "median_return_pct": float(returns.median()),
                    "max_return_pct": float(returns.max()),
                    "worst_drawdown_pct": float(dds.min()),
                    "median_drawdown_pct": float(dds.median()),
                    "max_days_below_initial": int(days.max()),
                    "median_days_below_initial": float(days.median()),
                    "max_consecutive_below_initial_days": int(
                        pd.to_numeric(group["max_consecutive_below_initial_days"], errors="coerce").fillna(0).max()
                    ),
                    "median_proxy_active_days": float(
                        pd.to_numeric(group["proxy_active_days"], errors="coerce").fillna(0).median()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq("official_c9_15w")].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for _, row in summary[~summary["version"].eq("official_c9_15w")].iterrows():
        start = str(row["requested_start_month"])
        base = official.loc[start]
        rows.append(
            {
                "version": row["version"],
                "variant_label": row["variant_label"],
                "requested_start_month": start,
                "return_delta_pct": float(row["total_return_pct"] - base["total_return_pct"]),
                "return_retention_ratio": float(row["total_return_pct"] / base["total_return_pct"])
                if float(base["total_return_pct"]) != 0
                else np.nan,
                "end_equity_delta": float(row["end_equity"] - base["end_equity"]),
                "end_equity_ratio": float(row["end_equity"] / base["end_equity"]) if float(base["end_equity"]) else np.nan,
                "drawdown_delta_pct": float(row["max_drawdown_pct"] - base["max_drawdown_pct"]),
                "days_below_delta": int(row["days_below_initial"] - base["days_below_initial"]),
                "max_consecutive_below_delta": int(
                    row["max_consecutive_below_initial_days"] - base["max_consecutive_below_initial_days"]
                ),
                "official_return_pct": float(base["total_return_pct"]),
                "variant_return_pct": float(row["total_return_pct"]),
                "official_max_drawdown_pct": float(base["max_drawdown_pct"]),
                "variant_max_drawdown_pct": float(row["max_drawdown_pct"]),
            }
        )
    return pd.DataFrame(rows)


def build() -> dict[str, pd.DataFrame]:
    official = _read_official_curves()
    curves = pd.concat([_variant_curves(group) for _, group in official.groupby("requested_start_month")], ignore_index=True)
    curves = curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby(["version", "requested_start_month"])])
    summary = summary.sort_values(["requested_start_month", "version"]).reset_index(drop=True)
    variant_summary = _variant_summary(summary)
    retention = _retention(summary)
    defect = summary[summary["version"].eq("official_c9_15w")].copy()
    return {
        "curves": curves,
        "summary": summary,
        "variant_summary": variant_summary,
        "retention": retention,
        "defect": defect,
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    curves = results["curves"].copy()
    summary = results["summary"].copy()
    focus_starts = [item for item in sorted(curves["requested_start_month"].astype(str).unique()) if item >= "2021-07"]

    fig, axes = plt.subplots(3, 1, figsize=(18, 14), sharex=True, constrained_layout=True)
    for ax, version in zip(axes, VARIANTS, strict=True):
        subset = curves[curves["version"].eq(version) & curves["requested_start_month"].astype(str).isin(focus_starts)]
        for start, group in subset.groupby("requested_start_month", sort=True):
            group = group.sort_values("date")
            ax.plot(group["date"], group["account_equity"], linewidth=1.0, alpha=0.8, label=str(start))
        capital = float(subset["account_capital"].iloc[0]) if not subset.empty else BASE_CAPITAL
        ax.axhline(capital, color="#6b7280", linestyle="--", linewidth=0.9)
        ax.set_title(VARIANT_LABELS[version])
        ax.set_ylabel("account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(ncol=7, fontsize=8)
    axes[-1].set_xlabel("date")
    fig.suptitle("Stage073 recent-start account equity curves")
    fig.savefig(CHART_EQUITY_RECENT_PATH, dpi=160)
    plt.close(fig)

    recent_summary = summary[summary["requested_start_month"].astype(str).ge("2020-01")].copy()
    starts = sorted(recent_summary["requested_start_month"].astype(str).unique())
    x = np.arange(len(starts))
    width = 0.24
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for offset, version in zip((-width, 0.0, width), VARIANTS, strict=True):
        group = recent_summary[recent_summary["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(x + offset, group["total_return_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[1].bar(x + offset, group["max_drawdown_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
    axes[0].set_title("Terminal return by start")
    axes[0].set_ylabel("return %")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Max drawdown by start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(starts, rotation=45, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=3)
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for offset, version in zip((-width, 0.0, width), VARIANTS, strict=True):
        group = recent_summary[recent_summary["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(
            x + offset,
            group["days_below_initial"],
            width=width,
            label=VARIANT_LABELS[version],
            color=VARIANT_COLORS[version],
        )
        axes[1].bar(
            x + offset,
            group["max_consecutive_below_initial_days"],
            width=width,
            label=VARIANT_LABELS[version],
            color=VARIANT_COLORS[version],
        )
    axes[0].set_title("Total trading days below initial capital")
    axes[0].set_ylabel("days")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Max consecutive trading days below initial capital")
    axes[1].set_ylabel("days")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(starts, rotation=45, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=3)
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)


def write_outputs(results: dict[str, pd.DataFrame]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    results["curves"].to_csv(CURVES_PATH, index=False, compression="gzip")
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["defect"].to_csv(DEFECT_PATH, index=False, encoding="utf-8-sig")
    results["retention"].to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)

    vs = results["variant_summary"].copy()
    key = vs[vs["sample"].eq("starts_2020_2026")].copy()
    retention = results["retention"].copy()
    dd25 = retention[retention["version"].eq("dd25_half_risk_proxy") & retention["requested_start_month"].ge("2020-01")]
    idle = retention[
        retention["version"].eq("account_30w_idle_reserve_view") & retention["requested_start_month"].ge("2020-01")
    ]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage073_dd_brake_not_promoted_idle_reserve_accounting_only",
        "official_is_still_baseline": True,
        "dd25_half_risk_proxy_promoted": False,
        "idle_reserve_is_strategy_upgrade": False,
        "sample": "starts_2020_2026",
        "key_variant_summary": key.to_dict(orient="records"),
        "dd25_min_return_retention_ratio": float(pd.to_numeric(dd25["return_retention_ratio"], errors="coerce").min()),
        "dd25_median_return_retention_ratio": float(pd.to_numeric(dd25["return_retention_ratio"], errors="coerce").median()),
        "idle_return_retention_ratio_definition": "not a strategy-retention metric because capital denominator changes from 15w to 30w",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Stage073 official C9 path governance proxy",
        "",
        "## 外部调研与判断",
        "",
        "- 参考 CPPI/TIPP 的风险资产 + 安全资产框架，但不做乘数扫参；本阶段只判断备用资金展示和一个回撤触发半风险代理是否值得进入真实引擎。",
        "- 参考 pysystemtrade capital correction 的思路：资本变化应该作为资金治理问题处理，不能把外部入金/备用金搬运当作 alpha。",
        "- 趋势跟随资料也提示，回撤期坚持暴露往往和后续右尾恢复绑定；所以本阶段把右尾收益保留设为硬约束。",
        "- 调研链接：",
        "  - https://core.axa-im.com/investment-strategies/multi-asset/insights/understanding-portfolio-insurance-management-cppitipp",
        "  - https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html",
        "  - https://alphaarchitect.com/avoiding-the-big-drawdown-with-trend-following-investment-strategies/",
        "",
        "## 口径",
        "",
        "- A：`official_c9_15w`，读取 Stage053 中的正式 C9/15w 真实引擎资金曲线。",
        "- C1：`account_30w_idle_reserve_view`，交易曲线不变，只把 15w 闲置储备从第一天计入总账户权益，分母固定 30w。",
        "- C2：`dd25_half_risk_proxy`，曲线级无前视代理：前一日代理账户从高水位回撤到 `-25%` 后，次日起把官方日 PnL 乘 `0.5`；恢复到 `-10%` 后解除。",
        "- 本阶段不重跑策略、不改变 AI 池、不改变开平仓、不连接 CTP、不调用订单 API。",
        "",
        "## starts_2020_2026 汇总",
        "",
        _md_table(key),
        "",
        "## 与正式版收益保留",
        "",
        _md_table(retention[retention["requested_start_month"].ge("2020-01")].round(6), 40),
        "",
        "## 结论",
        "",
        "- `account_30w_idle_reserve_view` 只能降低总账户口径下的回撤百分比，不能缩短核心交易曲线的水下时间，也不是策略增强。",
        "- `dd25_half_risk_proxy` 会明显砍掉 2020/2021 右尾，且 `starts_2020_2026` 的最大水下天数从正式版 `500` 增至 `662`，最差回撤从 `-55.3701%` 恶化到 `-59.9810%`。",
        "- 因此正式 C9 仍是基准；本阶段不建议把亏损后半风险这类账户受伤 brake 推入真实引擎。",
        "",
        "## 输出文件",
        "",
        f"- curves：`{CURVES_PATH}`",
        f"- per_start_summary：`{SUMMARY_PATH}`",
        f"- variant_summary：`{VARIANT_SUMMARY_PATH}`",
        f"- retention_vs_official：`{RETENTION_PATH}`",
        f"- equity chart：`{CHART_EQUITY_RECENT_PATH}`",
        f"- return/dd chart：`{CHART_RETURN_DD_PATH}`",
        f"- underwater chart：`{CHART_UNDERWATER_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage073_official_c9_path_governance_proxy.md"
    stage_record = [
        "# Stage073 official C9 path governance proxy",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 阶段性质：正式 C9 水下治理代理证伪；只读曲线级研究",
        "- 是否重要突破：否，负结论",
        "- 是否触发A/B：是；候选为可能影响正式资金治理的部署层代理，但本阶段只做最小证伪",
        "",
        "## 外部调研与判断",
        "",
        "- CPPI/TIPP、capital correction 和趋势跟随回撤资料均支持把资金治理作为独立层处理，但也提示降风险可能牺牲趋势右尾。",
        "- 本次判断：先用不前视曲线级代理证伪，不通过则不进入真实引擎。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改",
        "- 删除脚本：无",
        "- 新增参数：代理规则 `dd25_half_risk_proxy`，触发 `-25%`，解除 `-10%`，风险乘数 `0.5`；30w 闲置储备展示口径",
        "- 修改参数：无正式交易参数",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：Stage053 正式 C9 曲线，起点 `2018-01` 到 `2026-01` 逐半年，统一终点 `2026-06-30`；重点汇总 `2020-01` 以后。",
        "- 账户规模：正式 `150,000`；展示口径 `300,000=150,000 交易袖 + 150,000 闲置储备`。",
        "- 成本口径：沿用 Stage053 已有真实引擎曲线成本；代理不新增交易成本。",
        "- 样本过滤：只读正式 C9，不读取或修改实盘日志。",
        "- 策略/归因口径：曲线级代理，不是正式真实引擎回测。",
        "",
        "## 结果",
        "",
        _md_table(key),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- curves：`{CURVES_PATH}`",
        f"- quality：`{RETENTION_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：`stage073_dd_brake_not_promoted_idle_reserve_accounting_only`。",
        "- 是否进入下一步：不把 `dd25_half_risk_proxy` 进入真实引擎；30w 闲置储备只能作为账户展示/承受力口径，不能当策略升级。",
        "- 下一步：若继续，应回到正式 C9 的真实成交/持仓层做 2022/2023 水下归因，寻找不以降风险砍恢复段为代价的结构信息；不要继续扫回撤阈值或风险乘数。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。只测试一个预声明、低自由度、账户层代理，并把右尾保留设为硬约束。",
        "- 运行后判断：否。结果为负后直接停止，没有按 2022/2023 窗口继续调阈值或乘数。",
        "- 原因：继续扫 `-20/-25/-30` 或 `0.3/0.5/0.7` 会变成历史窗口救参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有。正式 C9 右尾强但水下体验差，账户层治理值得先证伪。",
        "- 运行后判断：有，但不是这条 brake 形状。价值在于收窄方向：亏损后降风险不是当前优先路线，应转向真实持仓/成交归因或新外生信息源。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：暂不更新，等待下一阶段形成更明确路线。",
        "- 是否更新 `research/registry.md`：否。",
        "- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是负结论代理，不是正式合入或重要突破。",
    ]
    stage_path.write_text("\n".join(stage_record) + "\n", encoding="utf-8")


def main() -> None:
    results = build()
    write_outputs(results)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "summary_rows": int(len(results["summary"])),
                "variant_summary_rows": int(len(results["variant_summary"])),
                "curves_rows": int(len(results["curves"])),
                "decision": "stage073_dd_brake_not_promoted_idle_reserve_accounting_only",
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
