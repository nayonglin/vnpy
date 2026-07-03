#!/usr/bin/env python3
"""Stage053: compare valuable versions on half-year starts to 2026-06-30.

This is a read-only aggregation over already generated official/proxy/engine
curve artifacts. It does not change strategy parameters or live execution code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / "research/lines/futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE = ROOT / "research/lines/futures_trend_rebuilt_c9_15w_optimization"
OUT = LINE / "outputs/stage053_valuable_versions_halfyear_curves"
MODEL_TAG = "stage053_valuable_versions_halfyear_curves_v1"
END_DATE = pd.Timestamp("2026-06-30")
INITIAL_CAPITAL = 150_000.0
RUN_NOW = datetime.now()
RUN_TS = RUN_NOW.strftime("%Y%m%d_%H%M")
RUN_TIME_LABEL = RUN_NOW.strftime("%Y-%m-%d %H:%M CST")


@dataclass(frozen=True)
class CurveSpec:
    label: str
    path: Path
    equity_col: str
    variant_filter: str | None = None
    source_type: str = "curve"
    note: str = ""


SPECS: tuple[CurveSpec, ...] = (
    CurveSpec(
        label="Official C9/15w Stage847",
        path=UPSTREAM_LINE
        / "outputs/stage006_current_quality_feature_binder/"
        / "rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv",
        equity_col="account_equity",
        source_type="true_engine",
        note="当前官方实盘默认 C9/15w，作为正式版对照。",
    ),
    CurveSpec(
        label="Stage013 account-state pilot",
        path=UPSTREAM_LINE
        / "outputs/stage013_account_state_pilot_gate_engine/"
        / "rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv",
        equity_col="account_equity",
        source_type="true_engine",
        note="账户受伤且低持仓时 flat_entry 降为 1 手的研究母本。",
    ),
    CurveSpec(
        label="Stage008 risk-release gate",
        path=LINE
        / "outputs/stage008_pit_entry_risk_release_gate_engine/"
        / "rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_curves_stage008_pit_entry_risk_release_gate_engine_v1.csv",
        equity_col="account_equity",
        source_type="true_engine",
        note="真实引擎；改善严格左尾但牺牲收益保留。",
    ),
    CurveSpec(
        label="Stage010 quality +25% proxy",
        path=LINE
        / "outputs/stage010_quality_add_risk_proxy/"
        / "rebuilt_c9_v2_stage010_quality_add_risk_proxy_curves_stage010_quality_add_risk_proxy_v1.csv",
        equity_col="stage010_account_equity",
        source_type="closed_lot_proxy",
        note="AI rank 1-8 + selected_volume>1 固定 25% 非挤占加风险 proxy。",
    ),
    CurveSpec(
        label="Stage013 guarded quality proxy",
        path=LINE
        / "outputs/stage013_guarded_quality_add_risk_proxy/"
        / "rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_curves_stage013_guarded_quality_add_risk_proxy_v1.csv",
        equity_col="stage013_guarded_account_equity",
        source_type="closed_lot_proxy",
        note="Stage010 排除 risk_multiplier>=2 后的 guarded proxy。",
    ),
    CurveSpec(
        label="Stage014 guarded floor integer",
        path=LINE
        / "outputs/stage014_integer_add_risk_feasibility_audit/"
        / "rebuilt_c9_v2_stage014_integer_add_risk_feasibility_audit_curves_stage014_integer_add_risk_feasibility_audit_v1.csv",
        equity_col="stage014_floor_account_equity",
        source_type="integer_proxy",
        note="Stage013 guarded proxy 的 floor 整数手可实现版本。",
    ),
    CurveSpec(
        label="Stage014 guarded ceil integer",
        path=LINE
        / "outputs/stage014_integer_add_risk_feasibility_audit/"
        / "rebuilt_c9_v2_stage014_integer_add_risk_feasibility_audit_curves_stage014_integer_add_risk_feasibility_audit_v1.csv",
        equity_col="stage014_ceil_account_equity",
        source_type="integer_proxy",
        note="Stage013 guarded proxy 的 ceil 整数手可实现版本。",
    ),
    CurveSpec(
        label="Stage017 C9 60 + Stage372 40",
        path=LINE
        / "outputs/stage017_fixed_sleeve_blend_audit/"
        / "rebuilt_c9_v2_stage017_fixed_sleeve_blend_audit_combo_curves_stage017_fixed_sleeve_blend_audit_v1.csv",
        equity_col="account_equity",
        variant_filter="c9_60_official_40",
        source_type="sleeve_proxy",
        note="当前 C9/15w 与 previous official Stage372/20w 固定资金袖组合。",
    ),
    CurveSpec(
        label="Stage022 guarded xsmom proxy",
        path=LINE
        / "outputs/stage022_xsmom_entry_confirmation_proxy/"
        / "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_curves_stage022_xsmom_entry_confirmation_proxy_v1.csv",
        equity_col="account_equity",
        variant_filter="stage022_stage013_guarded_quality_xsmom12_not_opposed",
        source_type="closed_lot_proxy",
        note="Stage013 guarded quality + xsmom12 not opposed proxy。",
    ),
    CurveSpec(
        label="Stage036 profit tranche 6x",
        path=LINE
        / "outputs/stage036_profit_lock_survival_audit/"
        / "rebuilt_c9_v2_stage036_profit_lock_survival_audit_curves_stage036_profit_lock_survival_audit_v1.csv",
        equity_col="account_equity",
        variant_filter="profit_tranche_norm6x",
        source_type="account_overlay",
        note="利润兑现资金层，6x 阈值版本。",
    ),
    CurveSpec(
        label="Stage036 balanced tranche 10x",
        path=LINE
        / "outputs/stage036_profit_lock_survival_audit/"
        / "rebuilt_c9_v2_stage036_profit_lock_survival_audit_curves_stage036_profit_lock_survival_audit_v1.csv",
        equity_col="account_equity",
        variant_filter="balanced_tranche_norm10x",
        source_type="account_overlay",
        note="利润兑现资金层，10x balanced 版本。",
    ),
    CurveSpec(
        label="Stage052 contract OI share proxy",
        path=UPSTREAM_LINE
        / "outputs/stage052_contract_oi_share_add_risk_proxy/"
        / "rebuilt_c9_stage052_contract_oi_share_add_risk_proxy_curves_stage052_contract_oi_share_add_risk_proxy_v1.csv",
        equity_col="stage052_account_equity",
        source_type="closed_lot_proxy",
        note="逐合约 OI share >=50% 加风险 proxy；不是 v2 的 TqSdk 补数 Stage052。",
    ),
    CurveSpec(
        label="Stage070 AI top8 active<3 proxy",
        path=UPSTREAM_LINE
        / "outputs/stage070_super_quality_sibling_panel/"
        / "rebuilt_c9_stage070_super_quality_sibling_panel_panel_curves_stage070_super_quality_sibling_panel_v1.csv.gz",
        equity_col="equity",
        variant_filter="full_market_ai_top8_and_active_positions_lt3",
        source_type="closed_lot_proxy",
        note="full-market AI top8 且 active_positions<3 的 super-quality proxy。",
    ),
    CurveSpec(
        label="Stage074 cold-start ramp proxy",
        path=UPSTREAM_LINE
        / "outputs/stage074_cold_start_capital_ramp_proxy/"
        / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_panel_curves_stage074_cold_start_capital_ramp_proxy_v1.csv.gz",
        equity_col="equity",
        variant_filter="full_market_ai_top8_and_active_positions_lt3_cold_start_ramp",
        source_type="account_overlay",
        note="Stage070 目标版本叠加 0.35/252d cold-start ramp。",
    ),
)


def _read_columns(path: Path) -> list[str]:
    return pd.read_csv(path, nrows=0).columns.tolist()


def load_spec(spec: CurveSpec) -> pd.DataFrame:
    columns = set(_read_columns(spec.path))
    required = {"date", "requested_start_month", spec.equity_col}
    if spec.variant_filter is not None:
        required.add("variant")
    missing = required - columns
    if missing:
        raise ValueError(f"{spec.path} missing columns: {sorted(missing)}")

    df = pd.read_csv(spec.path, usecols=sorted(required))
    if spec.variant_filter is not None:
        df = df[df["variant"] == spec.variant_filter].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] <= END_DATE].copy()
    df = df.rename(columns={spec.equity_col: "equity"})
    df["version"] = spec.label
    df["source_type"] = spec.source_type
    df["note"] = spec.note
    df = df[["version", "source_type", "requested_start_month", "date", "equity", "note"]]
    df = df.dropna(subset=["requested_start_month", "date", "equity"])
    df = df.sort_values(["version", "requested_start_month", "date"])
    first_equity = df.groupby(["version", "requested_start_month"])["equity"].transform("first")
    df["nav"] = df["equity"] / first_equity
    return df


def max_drawdown(nav: pd.Series) -> float:
    running_max = nav.cummax()
    dd = nav / running_max - 1.0
    return float(dd.min() * 100.0)


def summarize(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for (version, source_type, start), g in curves.groupby(
        ["version", "source_type", "requested_start_month"], sort=False
    ):
        g = g.sort_values("date")
        final_nav = float(g["nav"].iloc[-1])
        rows.append(
            {
                "version": version,
                "source_type": source_type,
                "requested_start_month": start,
                "start_date": g["date"].iloc[0].date().isoformat(),
                "end_date": g["date"].iloc[-1].date().isoformat(),
                "trading_days": int(len(g)),
                "start_equity": float(g["equity"].iloc[0]),
                "end_equity": float(g["equity"].iloc[-1]),
                "final_nav": final_nav,
                "total_return_pct": (final_nav - 1.0) * 100.0,
                "max_drawdown_pct": max_drawdown(g["nav"]),
            }
        )
    per_start = pd.DataFrame(rows)

    official = per_start[per_start["version"] == "Official C9/15w Stage847"][
        ["requested_start_month", "total_return_pct", "final_nav"]
    ].rename(
        columns={
            "total_return_pct": "official_total_return_pct",
            "final_nav": "official_final_nav",
        }
    )
    per_start = per_start.merge(official, on="requested_start_month", how="left")
    per_start["return_diff_vs_official_pp"] = (
        per_start["total_return_pct"] - per_start["official_total_return_pct"]
    )
    per_start["final_nav_ratio_vs_official"] = per_start["final_nav"] / per_start[
        "official_final_nav"
    ]

    version_rows: list[dict[str, object]] = []
    for (version, source_type), g in per_start.groupby(["version", "source_type"], sort=False):
        comparable = g.dropna(subset=["official_total_return_pct"])
        version_rows.append(
            {
                "version": version,
                "source_type": source_type,
                "start_count": int(g["requested_start_month"].nunique()),
                "positive_start_count": int((g["total_return_pct"] > 0).sum()),
                "win_vs_official_count": int(
                    (comparable["return_diff_vs_official_pp"] > 0).sum()
                ),
                "comparable_to_official_count": int(len(comparable)),
                "min_total_return_pct": float(g["total_return_pct"].min()),
                "median_total_return_pct": float(g["total_return_pct"].median()),
                "max_total_return_pct": float(g["total_return_pct"].max()),
                "worst_max_drawdown_pct": float(g["max_drawdown_pct"].min()),
                "median_max_drawdown_pct": float(g["max_drawdown_pct"].median()),
                "min_final_nav_ratio_vs_official": float(
                    comparable["final_nav_ratio_vs_official"].min()
                )
                if len(comparable)
                else np.nan,
                "median_final_nav_ratio_vs_official": float(
                    comparable["final_nav_ratio_vs_official"].median()
                )
                if len(comparable)
                else np.nan,
            }
        )
    version_summary = pd.DataFrame(version_rows)
    return per_start, version_summary


def plot_curves(curves: pd.DataFrame, path: Path) -> None:
    starts = sorted(curves["requested_start_month"].unique())
    versions = list(dict.fromkeys(curves["version"].tolist()))
    color_map = dict(zip(versions, plt.cm.tab20(np.linspace(0, 1, len(versions)))))
    fig, axes = plt.subplots(5, 4, figsize=(24, 18), sharex=False, sharey=False)
    axes_flat = axes.ravel()
    for ax, start in zip(axes_flat, starts):
        sub = curves[curves["requested_start_month"] == start]
        for version in versions:
            g = sub[sub["version"] == version]
            if g.empty:
                continue
            ax.plot(g["date"], g["nav"], linewidth=1.2, color=color_map[version], alpha=0.9)
        ax.set_title(start, fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.tick_params(axis="x", rotation=35, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_ylabel("NAV")
    for ax in axes_flat[len(starts) :]:
        ax.axis("off")
    handles = [
        plt.Line2D([0], [0], color=color_map[v], lw=2, label=v) for v in versions
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=8)
    fig.suptitle(
        "Valuable versions half-year start NAV curves to 2026-06-30",
        fontsize=16,
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.975))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_heatmap(
    per_start: pd.DataFrame,
    value_col: str,
    title: str,
    cmap: str,
    path: Path,
    fmt: str = ".1f",
) -> None:
    version_order = list(dict.fromkeys(per_start["version"].tolist()))
    start_order = sorted(per_start["requested_start_month"].unique())
    pivot = (
        per_start.pivot(index="version", columns="requested_start_month", values=value_col)
        .reindex(index=version_order, columns=start_order)
    )
    fig, ax = plt.subplots(figsize=(18, max(7, 0.45 * len(version_order))))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(start_order)))
    ax.set_xticklabels(start_order, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(version_order)))
    ax.set_yticklabels(version_order, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iat[i, j]
            if pd.isna(val):
                text = ""
            else:
                text = format(float(val), fmt)
            ax.text(j, i, text, ha="center", va="center", fontsize=6, color="black")
    cbar = fig.colorbar(im, ax=ax)
    cbar.ax.set_ylabel(value_col)
    ax.set_title(title, fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_markdown(
    per_start: pd.DataFrame,
    version_summary: pd.DataFrame,
    output_paths: dict[str, Path],
) -> Path:
    stage_dir = LINE / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    stage_path = stage_dir / f"{RUN_TS}_stage053_valuable_versions_halfyear_curves.md"

    summary_view = version_summary[
        [
            "version",
            "source_type",
            "start_count",
            "positive_start_count",
            "win_vs_official_count",
            "comparable_to_official_count",
            "min_total_return_pct",
            "median_total_return_pct",
            "worst_max_drawdown_pct",
            "min_final_nav_ratio_vs_official",
        ]
    ].copy()
    summary_view = summary_view.round(
        {
            "min_total_return_pct": 4,
            "median_total_return_pct": 4,
            "worst_max_drawdown_pct": 4,
            "min_final_nav_ratio_vs_official": 4,
        }
    )

    top = version_summary.sort_values("min_total_return_pct", ascending=False).head(6)
    best_worst_dd = version_summary.sort_values("worst_max_drawdown_pct", ascending=False).head(6)

    md = [
        "# Stage053 有价值版本逐半年净值曲线复算",
        "",
        f"- 记录时间：{RUN_TIME_LABEL}",
        "- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：否，本阶段是只读汇总与绘图，不新增交易规则。",
        "- 新增参数：无交易参数；新增比较集合 `valuable_versions + official C9/15w`。",
        "- 修改参数：无正式策略参数修改。",
        "- 删除参数：无。",
        "- 回测/曲线口径：逐半年起点；终点统一使用 `2026-06-30`；已存在的真引擎/代理曲线按原 stage 输出读取并重新计算 NAV、终点收益和回撤。",
        "",
        "## 外部调研判断",
        "",
        "- Managed futures / trend-following 资料支持用多起点、跨周期路径和右尾保留判断策略，不应只看单一起点。",
        "- vectorbt 等矩阵化回测框架说明多版本/多起点曲线适合统一面板分析；本阶段仍沿用仓库既有回测曲线，不迁移框架。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 开始是否过拟合：否。本阶段只汇总前面已冻结的版本，不按结果新增阈值、日期、品种、方向或资金比例。",
        "- 结束是否过拟合：否。图表揭示差异但不据此调参；后续若只挑收益最好的起点救参会过拟合。",
        "- 开始是否值得继续：有。用户需要把所有有价值版本放到同一逐半年口径对比，这是判断下一步路线的必要视图。",
        "- 结束是否值得继续：有，但方向应转向能同时保留右尾和减少冷启动左尾的结构；单纯资金 ramp / sleeve / profit lock 已显示收益保留问题。",
        "",
        "## 汇总结论",
        "",
        "- 这次没有新增达成目标的版本；所有候选仍只是研究资产或诊断资产。",
        "- 终点收益/净值曲线最值得继续看的仍是 `Stage010/013/014/022` 质量加风险链；它们多数起点能抬高收益，但仍不是严格任意一年以上正收益解法。",
        "- `Stage008/017/036/074` 更偏防守或部署层，能改善部分左尾窗口，但收益保留或晚近起点表现明显受损。",
        "- `Stage052 contract OI share proxy` 是上游旧 Stage052 逐合约 OI 加风险 proxy，不是 v2 当前 TqSdk jd 补数 Stage052。",
        "",
        "## Version Summary",
        "",
        summary_view.to_markdown(index=False),
        "",
        "## Min Return Top",
        "",
        top[
            [
                "version",
                "source_type",
                "start_count",
                "min_total_return_pct",
                "median_total_return_pct",
                "worst_max_drawdown_pct",
            ]
        ]
        .round(4)
        .to_markdown(index=False),
        "",
        "## Drawdown Top",
        "",
        best_worst_dd[
            [
                "version",
                "source_type",
                "start_count",
                "min_total_return_pct",
                "median_total_return_pct",
                "worst_max_drawdown_pct",
            ]
        ]
        .round(4)
        .to_markdown(index=False),
        "",
        "## 输出",
        "",
    ]
    for key, value in output_paths.items():
        md.append(f"- {key}: `{value}`")
    md.append("")
    stage_path.write_text("\n".join(md), encoding="utf-8")
    return stage_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    curves = pd.concat([load_spec(spec) for spec in SPECS], ignore_index=True)
    per_start, version_summary = summarize(curves)

    curves_path = OUT / f"rebuilt_c9_v2_stage053_halfyear_curves_{MODEL_TAG}.csv.gz"
    per_start_path = OUT / f"rebuilt_c9_v2_stage053_halfyear_per_start_summary_{MODEL_TAG}.csv"
    version_summary_path = OUT / f"rebuilt_c9_v2_stage053_halfyear_version_summary_{MODEL_TAG}.csv"
    nav_chart = OUT / f"rebuilt_c9_v2_stage053_halfyear_nav_curves_{MODEL_TAG}.png"
    return_heatmap = OUT / f"rebuilt_c9_v2_stage053_final_return_heatmap_{MODEL_TAG}.png"
    ratio_heatmap = OUT / f"rebuilt_c9_v2_stage053_vs_official_ratio_heatmap_{MODEL_TAG}.png"

    curves.to_csv(curves_path, index=False)
    per_start.to_csv(per_start_path, index=False)
    version_summary.to_csv(version_summary_path, index=False)
    plot_curves(curves, nav_chart)
    plot_heatmap(
        per_start,
        value_col="total_return_pct",
        title="Final total return by half-year start, end=2026-06-30",
        cmap="RdYlGn",
        path=return_heatmap,
        fmt=".0f",
    )
    plot_heatmap(
        per_start,
        value_col="final_nav_ratio_vs_official",
        title="Final NAV ratio versus official C9/15w Stage847",
        cmap="RdYlGn",
        path=ratio_heatmap,
        fmt=".2f",
    )

    output_paths = {
        "curves": curves_path,
        "per_start_summary": per_start_path,
        "version_summary": version_summary_path,
        "nav_curves_chart": nav_chart,
        "final_return_heatmap": return_heatmap,
        "vs_official_ratio_heatmap": ratio_heatmap,
    }
    stage_path = write_markdown(per_start, version_summary, output_paths)

    print(f"wrote {curves_path}")
    print(f"wrote {per_start_path}")
    print(f"wrote {version_summary_path}")
    print(f"wrote {nav_chart}")
    print(f"wrote {return_heatmap}")
    print(f"wrote {ratio_heatmap}")
    print(f"wrote {stage_path}")


if __name__ == "__main__":
    main()
