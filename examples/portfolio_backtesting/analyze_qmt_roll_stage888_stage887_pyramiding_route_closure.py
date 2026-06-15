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

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage888"
MODEL_TAG = "stage888_stage887_pyramiding_route_closure_v1"
OUTPUT_PREFIX = "qmt_roll_stage888_stage887_pyramiding_route_closure"

ROUTE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
SCORECARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scorecard_{MODEL_TAG}.csv"
VISUAL_INDEX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_visual_index_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

STAGE_FILES = {
    "stage881_decision": OUTPUT_DIR
    / "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_decision_stage881_stage863_progress_pyramid_proxy_audit_v1.json",
    "stage881_state": OUTPUT_DIR
    / "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_state_summary_stage881_stage863_progress_pyramid_proxy_audit_v1.csv",
    "stage881_yearly": OUTPUT_DIR
    / "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_yearly_stage881_stage863_progress_pyramid_proxy_audit_v1.csv",
    "stage882_decision": OUTPUT_DIR
    / "qmt_roll_stage882_stage881_progress_pyramid_engine_decision_stage882_stage881_progress_pyramid_engine_v1.json",
    "stage882_comparison": OUTPUT_DIR
    / "qmt_roll_stage882_stage881_progress_pyramid_engine_comparison_stage882_stage881_progress_pyramid_engine_v1.csv",
    "stage883_decision": OUTPUT_DIR
    / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_decision_stage883_stage882_progress_pyramid_sleeve1_engine_v1.json",
    "stage883_comparison": OUTPUT_DIR
    / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_comparison_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv",
    "stage884_decision": OUTPUT_DIR
    / "qmt_roll_stage884_stage883_broker10_path_forensics_decision_stage884_stage883_broker10_path_forensics_v1.json",
    "stage885_decision": OUTPUT_DIR
    / "qmt_roll_stage885_stage884_holding_pressure_state_audit_decision_stage885_stage884_holding_pressure_state_audit_v1.json",
    "stage885_bucket": OUTPUT_DIR
    / "qmt_roll_stage885_stage884_holding_pressure_state_audit_pressure_bucket_stage885_stage884_holding_pressure_state_audit_v1.csv",
    "stage886_decision": OUTPUT_DIR
    / "qmt_roll_stage886_stage885_pressure_failure_structure_audit_decision_stage886_stage885_pressure_failure_structure_audit_v1.json",
    "stage886_shape": OUTPUT_DIR
    / "qmt_roll_stage886_stage885_pressure_failure_structure_audit_shape_proxy_stage886_stage885_pressure_failure_structure_audit_v1.csv",
    "stage887_decision": OUTPUT_DIR
    / "qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_decision_stage887_stage883_sleeve_pressure_gate_audit_v1.json",
    "stage887_gate": OUTPUT_DIR
    / "qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_gate_summary_stage887_stage883_sleeve_pressure_gate_audit_v1.csv",
}

VISUAL_MANIFESTS = {
    "Stage881": OUTPUT_DIR
    / "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_manifest_stage881_stage863_progress_pyramid_proxy_audit_v1.csv",
    "Stage882": OUTPUT_DIR
    / "qmt_roll_stage882_stage881_progress_pyramid_engine_atlas_manifest_stage882_stage881_progress_pyramid_engine_v1.csv",
    "Stage883": OUTPUT_DIR
    / "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_atlas_manifest_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv",
    "Stage884": OUTPUT_DIR
    / "qmt_roll_stage884_stage883_broker10_path_forensics_atlas_manifest_stage884_stage883_broker10_path_forensics_v1.csv",
    "Stage885": OUTPUT_DIR
    / "qmt_roll_stage885_stage884_holding_pressure_state_audit_atlas_manifest_stage885_stage884_holding_pressure_state_audit_v1.csv",
    "Stage886": OUTPUT_DIR
    / "qmt_roll_stage886_stage885_pressure_failure_structure_audit_atlas_manifest_stage886_stage885_pressure_failure_structure_audit_v1.csv",
    "Stage887": OUTPUT_DIR
    / "qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_atlas_manifest_stage887_stage883_sleeve_pressure_gate_audit_v1.csv",
}

ATLAS_GLOBS = {
    "Stage881": "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_page*_stage881_stage863_progress_pyramid_proxy_audit_v1.png",
    "Stage882": "qmt_roll_stage882_stage881_progress_pyramid_engine_atlas_page*_stage882_stage881_progress_pyramid_engine_v1.png",
    "Stage883": "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_atlas_page*_stage883_stage882_progress_pyramid_sleeve1_engine_v1.png",
    "Stage884": "qmt_roll_stage884_stage883_broker10_path_forensics_atlas_page*_stage884_stage883_broker10_path_forensics_v1.png",
    "Stage885": "qmt_roll_stage885_stage884_holding_pressure_state_audit_atlas_page*_stage885_stage884_holding_pressure_state_audit_v1.png",
    "Stage886": "qmt_roll_stage886_stage885_pressure_failure_structure_audit_atlas_page*_stage886_stage885_pressure_failure_structure_audit_v1.png",
    "Stage887": "qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_atlas_page*_stage887_stage883_sleeve_pressure_gate_audit_v1.png",
}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _comparison_row(frame: pd.DataFrame, arm_contains: str) -> pd.Series:
    hit = frame[frame["arm"].astype(str).str.contains(arm_contains, regex=False)].copy()
    if hit.empty:
        raise RuntimeError(f"missing comparison arm containing {arm_contains}")
    return hit.iloc[0]


def _bool_mask(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _build_route_summary() -> pd.DataFrame:
    s881 = _load_json(STAGE_FILES["stage881_decision"])
    s882_cmp = _load_csv(STAGE_FILES["stage882_comparison"])
    s883_cmp = _load_csv(STAGE_FILES["stage883_comparison"])
    s884 = _load_json(STAGE_FILES["stage884_decision"])
    s885_bucket = _load_csv(STAGE_FILES["stage885_bucket"])
    s886_shape = _load_csv(STAGE_FILES["stage886_shape"])
    s887_gate = _load_csv(STAGE_FILES["stage887_gate"])

    c16 = _comparison_row(s882_cmp, "progress_pyramid_once")
    c17 = _comparison_row(s883_cmp, "progress_pyramid_sleeve1_once")
    c17_pressure = s885_bucket[
        s885_bucket["arm"].astype(str).str.contains("progress_pyramid_sleeve1_once", regex=False)
        & _bool_mask(s885_bucket["holding_pressure_state"])
    ].iloc[0]
    price_failure = s886_shape[s886_shape["shape"].eq("price_failure_shape")].iloc[0]
    gate_g4 = s887_gate[s887_gate["gate"].eq("G4_prev_pressure_or_projected_after_heat80")].iloc[0]

    rows = [
        {
            "stage": "Stage881",
            "test_type": "readonly_proxy",
            "route_step": "+0.5R progress pyramiding proxy",
            "decision": s881["decision"],
            "main_positive_evidence": f"proxy_delta={s881['pyramid_proxy_delta']:.2f}; candidates={s881['pyramid_candidate_lots']}",
            "main_negative_evidence": "proxy lacks margin, equity path, true position interaction",
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "proxy_delta": s881["pyramid_proxy_delta"],
            "winner_cut_or_loser_saved_balance": np.nan,
            "closure_verdict": "proxy_only_not_promoted",
        },
        {
            "stage": "Stage882",
            "test_type": "true_engine",
            "route_step": "same-volume +0.5R progress pyramiding",
            "decision": _load_json(STAGE_FILES["stage882_decision"])["decision"],
            "main_positive_evidence": f"end_equity_delta_vs_C9={c16['end_equity_delta_vs_C9']:.2f}",
            "main_negative_evidence": (
                f"max_dd={c16['max_dd_pct']:.4f}%; "
                f"broker10={c16['max_broker10_margin_to_equity_pct']:.4f}%"
            ),
            "end_equity_delta_vs_c9": c16["end_equity_delta_vs_C9"],
            "max_dd_delta_vs_c9_pp": c16["max_dd_delta_vs_C9"],
            "sharpe_delta_vs_c9": c16["sharpe_delta_vs_C9"],
            "max_broker10_pct": c16["max_broker10_margin_to_equity_pct"],
            "proxy_delta": np.nan,
            "winner_cut_or_loser_saved_balance": np.nan,
            "closure_verdict": "not_promoted_survival_failure",
        },
        {
            "stage": "Stage883",
            "test_type": "true_engine",
            "route_step": "one-lot +0.5R progress sleeve",
            "decision": _load_json(STAGE_FILES["stage883_decision"])["decision"],
            "main_positive_evidence": f"end_equity_delta_vs_C9={c17['end_equity_delta_vs_C9']:.2f}; dd_delta={c17['max_dd_delta_vs_C9']:.4f}pp",
            "main_negative_evidence": (
                f"sharpe_delta_vs_C9={c17['sharpe_delta_vs_C9']:.6f}; "
                f"broker10={c17['max_broker10_margin_to_equity_pct']:.4f}%"
            ),
            "end_equity_delta_vs_c9": c17["end_equity_delta_vs_C9"],
            "max_dd_delta_vs_c9_pp": c17["max_dd_delta_vs_C9"],
            "sharpe_delta_vs_c9": c17["sharpe_delta_vs_C9"],
            "max_broker10_pct": c17["max_broker10_margin_to_equity_pct"],
            "proxy_delta": np.nan,
            "winner_cut_or_loser_saved_balance": np.nan,
            "closure_verdict": "not_promoted_broker10_sharpe_failure",
        },
        {
            "stage": "Stage884",
            "test_type": "path_forensics",
            "route_step": "C17 broker10 path decomposition",
            "decision": s884["decision"],
            "main_positive_evidence": "diagnoses root cause instead of adding new rule",
            "main_negative_evidence": f"top10 mechanism={s884['top10_c17_mechanism_counts']}",
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "proxy_delta": np.nan,
            "winner_cut_or_loser_saved_balance": np.nan,
            "closure_verdict": "risk_from_exposure_numerator",
        },
        {
            "stage": "Stage885",
            "test_type": "pressure_state_audit",
            "route_step": "holding pressure state abstraction",
            "decision": _load_json(STAGE_FILES["stage885_decision"])["decision"],
            "main_positive_evidence": f"C17 pressure days={int(c17_pressure['days'])}; max broker10={c17_pressure['max_broker10']:.4f}%",
            "main_negative_evidence": (
                f"median_next20={c17_pressure['median_next20_return_pct']:.4f}%; "
                f"negative_next20_share={c17_pressure['negative_next20_share']:.4f}"
            ),
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": c17_pressure["max_broker10"],
            "proxy_delta": np.nan,
            "winner_cut_or_loser_saved_balance": np.nan,
            "closure_verdict": "pressure_label_not_trade_rule",
        },
        {
            "stage": "Stage886",
            "test_type": "pressure_failure_structure",
            "route_step": "minute failure shape inside pressure",
            "decision": _load_json(STAGE_FILES["stage886_decision"])["decision"],
            "main_positive_evidence": "fixed no-progress/adverse-half shape tested",
            "main_negative_evidence": (
                f"EOD proxy delta={price_failure['same_day_eod_exit_proxy_delta']:.2f}; "
                f"winner_cut={price_failure['winner_cut']:.2f}"
            ),
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "proxy_delta": price_failure["same_day_eod_exit_proxy_delta"],
            "winner_cut_or_loser_saved_balance": price_failure["loser_saved"] + price_failure["winner_cut"],
            "closure_verdict": "pressure_exit_rule_rejected",
        },
        {
            "stage": "Stage887",
            "test_type": "sleeve_pressure_gate",
            "route_step": "pre-add heat/pressure gate for sleeve",
            "decision": _load_json(STAGE_FILES["stage887_decision"])["decision"],
            "main_positive_evidence": f"G4 catches {int(gate_g4['active_on_pressure_events'])} later pressure events",
            "main_negative_evidence": (
                f"skip_proxy_delta={gate_g4['skip_proxy_delta']:.2f}; "
                f"winner_cut={gate_g4['winner_cut']:.2f}; loser_saved={gate_g4['loser_saved']:.2f}"
            ),
            "end_equity_delta_vs_c9": np.nan,
            "max_dd_delta_vs_c9_pp": np.nan,
            "sharpe_delta_vs_c9": np.nan,
            "max_broker10_pct": np.nan,
            "proxy_delta": gate_g4["skip_proxy_delta"],
            "winner_cut_or_loser_saved_balance": gate_g4["loser_saved"] + gate_g4["winner_cut"],
            "closure_verdict": "pressure_gate_rejected",
        },
    ]
    return pd.DataFrame(rows)


def _build_scorecard(route_summary: pd.DataFrame) -> pd.DataFrame:
    s881 = _load_json(STAGE_FILES["stage881_decision"])
    s882_cmp = _load_csv(STAGE_FILES["stage882_comparison"])
    s883_cmp = _load_csv(STAGE_FILES["stage883_comparison"])
    s886_shape = _load_csv(STAGE_FILES["stage886_shape"])
    s887_gate = _load_csv(STAGE_FILES["stage887_gate"])
    c16 = _comparison_row(s882_cmp, "progress_pyramid_once")
    c17 = _comparison_row(s883_cmp, "progress_pyramid_sleeve1_once")
    price_failure = s886_shape[s886_shape["shape"].eq("price_failure_shape")].iloc[0]
    gate_g4 = s887_gate[s887_gate["gate"].eq("G4_prev_pressure_or_projected_after_heat80")].iloc[0]
    return pd.DataFrame(
        [
            {
                "requirement": "right_tail_participation_exists",
                "status": "proven_but_not_sufficient",
                "evidence": f"Stage881 proxy delta {s881['pyramid_proxy_delta']:.2f}; Stage882 equity delta vs C9 {c16['end_equity_delta_vs_C9']:.2f}",
                "decision_impact": "right-tail participation is real, but survival gates decide promotion",
            },
            {
                "requirement": "true_engine_survives_margin_path",
                "status": "failed",
                "evidence": f"Stage882 max broker10 {c16['max_broker10_margin_to_equity_pct']:.4f}%, max DD {c16['max_dd_pct']:.4f}%",
                "decision_impact": "same-volume pyramiding closed",
            },
            {
                "requirement": "small_sleeve_improves_risk_adjusted_path",
                "status": "failed",
                "evidence": f"Stage883 Sharpe delta vs C9 {c17['sharpe_delta_vs_C9']:.6f}, max broker10 {c17['max_broker10_margin_to_equity_pct']:.4f}%",
                "decision_impact": "one-lot sleeve not promoted",
            },
            {
                "requirement": "pressure_state_can_be_exit_rule",
                "status": "failed",
                "evidence": f"Stage886 price-failure EOD proxy {price_failure['same_day_eod_exit_proxy_delta']:.2f}, median next20 {price_failure['median_next20_return_pct']:.4f}%",
                "decision_impact": "do not exit/reduce existing high-pressure right-tail positions",
            },
            {
                "requirement": "pressure_gate_can_block_bad_sleeves",
                "status": "failed",
                "evidence": f"Stage887 G4 skip proxy {gate_g4['skip_proxy_delta']:.2f}; loser_saved {gate_g4['loser_saved']:.2f}; winner_cut {gate_g4['winner_cut']:.2f}",
                "decision_impact": "do not add heat-threshold sleeve gate",
            },
            {
                "requirement": "visual_evidence_supports_closure",
                "status": "proven",
                "evidence": "Stage881-887 atlas pages show both stopped sleeve failures and high-heat winners; no clean visual boundary",
                "decision_impact": "visual review supports stopping parameter rescue",
            },
        ]
    )


def _build_visual_index() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    role_map = {
        "Stage881": "proxy candidate open/stopped minute-K samples",
        "Stage882": "same-volume true engine pyramid minute-K samples",
        "Stage883": "one-lot sleeve open/stopped minute-K samples",
        "Stage884": "broker10 exposure numerator pressure atlas",
        "Stage885": "holding-pressure product-direction minute-K atlas",
        "Stage886": "pressure failure/resilience minute-K atlas",
        "Stage887": "sleeve gate loser-saved vs winner-cut minute-K atlas",
    }
    for stage, manifest_path in VISUAL_MANIFESTS.items():
        page_paths = sorted(OUTPUT_DIR.glob(ATLAS_GLOBS[stage]))
        if manifest_path.exists():
            manifest = pd.read_csv(manifest_path, encoding="utf-8-sig")
            pages = sorted(pd.to_numeric(manifest.get("page", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).unique())
        else:
            manifest = pd.DataFrame()
            pages = list(range(1, len(page_paths) + 1))
        rows.append(
            {
                "stage": stage,
                "visual_role": role_map[stage],
                "manifest": str(manifest_path),
                "manifest_rows": int(len(manifest)),
                "atlas_pages": len(page_paths),
                "page_numbers": ",".join(map(str, pages)),
                "first_page": str(page_paths[0]) if page_paths else "",
                "visual_closure_read": _visual_closure_sentence(stage),
            }
        )
    return pd.DataFrame(rows)


def _visual_closure_sentence(stage: str) -> str:
    return {
        "Stage881": "proxy visually confirms +0.5R progress can join right tail, but stopped samples are material.",
        "Stage882": "same-volume add-on visually thickens right tail while also creating account-level survival stress.",
        "Stage883": "one-lot sleeve is operationally cleaner, yet still cannot remove broker10 pressure.",
        "Stage884": "risk is exposure numerator expansion, not a single product/date blacklist.",
        "Stage885": "pressure days are visually high exposure but often trend-continuation, not automatic exits.",
        "Stage886": "price-failure shapes include later winners; weak pressure-day close is not enough.",
        "Stage887": "heat gates catch some losers but also obvious high-heat winners; no clean boundary.",
    }[stage]


def _plot_summary(route_summary: pd.DataFrame, scorecard: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), constrained_layout=True)

    engine = route_summary[route_summary["test_type"].eq("true_engine")].copy()
    x = np.arange(len(engine))
    axes[0].bar(x - 0.2, engine["end_equity_delta_vs_c9"] / 1_000_000, width=0.4, label="equity delta vs C9 (M)")
    ax0 = axes[0].twinx()
    ax0.plot(x + 0.2, engine["max_broker10_pct"], color="#dc2626", marker="o", label="max broker10 pct")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(engine["stage"] + "\n" + engine["route_step"], rotation=0)
    axes[0].set_ylabel("equity delta vs C9, million")
    ax0.set_ylabel("max broker10 pct")
    axes[0].set_title("Pyramiding/sleeve true engines: right tail vs survival")
    handles1, labels1 = axes[0].get_legend_handles_labels()
    handles2, labels2 = ax0.get_legend_handles_labels()
    axes[0].legend(handles1 + handles2, labels1 + labels2, loc="best")
    axes[0].grid(True, alpha=0.25)

    proxy = route_summary[route_summary["proxy_delta"].notna()].copy()
    colors = np.where(proxy["proxy_delta"].ge(0), "#16a34a", "#64748b")
    axes[1].bar(proxy["stage"], proxy["proxy_delta"] / 1_000_000, color=colors)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Proxy/gate deltas after true-engine failures")
    axes[1].set_ylabel("proxy delta, million")
    axes[1].grid(True, alpha=0.25)

    status_order = ["proven_but_not_sufficient", "failed", "proven"]
    status_counts = scorecard["status"].value_counts().reindex(status_order).fillna(0)
    axes[2].bar(status_counts.index, status_counts.values, color=["#f59e0b", "#dc2626", "#16a34a"])
    axes[2].set_title("Closure scorecard")
    axes[2].set_ylabel("requirements")
    axes[2].grid(True, alpha=0.25)

    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _decision(route_summary: pd.DataFrame, scorecard: pd.DataFrame) -> str:
    failures = set(scorecard[scorecard["status"].eq("failed")]["requirement"].astype(str))
    required_failures = {
        "true_engine_survives_margin_path",
        "small_sleeve_improves_risk_adjusted_path",
        "pressure_state_can_be_exit_rule",
        "pressure_gate_can_block_bad_sleeves",
    }
    if required_failures.issubset(failures):
        return "stage888_pyramiding_sleeve_route_closed_no_more_param_rescue"
    return "stage888_route_closure_incomplete_needs_followup"


def _write_report(route_summary: pd.DataFrame, scorecard: pd.DataFrame, visual_index: pd.DataFrame, decision: str) -> None:
    lines = [
        "# Stage888 pyramiding/sleeve 路线收束审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：Stage881-887 路线收束；不新增交易规则、不重跑引擎、不改正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py/VeighNa 官方项目支持组合策略回测与实盘框架，本阶段只按已有组合回测和只读审计证据做 closure。",
        "- 趋势跟随 pyramiding 资料支持“盈利后加仓”这个方向，但也强调 portfolio heat / units 必须控制；本线的真实引擎证据显示该控制没有低误伤规则。",
        "- CME open interest 资料支持把 OI/成交量作为趋势参与度辅助信息，但不能单独决定退出或禁入；Stage885-887 已用本线数据反证了这一点。",
        "- 我的判断：pyramiding/sleeve 的右尾是真实的，但它无法穿越组合保证金生存线，且压力状态无法低误伤地变成规则。",
        "",
        "## Route Summary",
        "",
        _md_table(route_summary, max_rows=20),
        "",
        "## Scorecard",
        "",
        _md_table(scorecard, max_rows=20),
        "",
        "## Visual Index",
        "",
        _md_table(visual_index, max_rows=20),
        "",
        "## Closure Decision",
        "",
        f"- decision：`{decision}`",
        "- 结论：停止 Stage881-887 pyramiding/sleeve 分支；不扫 progress R、加仓比例、1/2/3 手 sleeve、止损位置、heat 阈值、产品方向、年份或分钟窗口。",
        "- 允许保留的经验：`+0.5R progress` 是右尾参与度标签；高压/弱收/OI 状态是复盘标签，不是交易规则。",
        "- 下一步：若继续本线，应回到 C9 本体，找新的低自由度外生信息源或账户级非交易层生存线，而不是继续新增仓救参。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只合并既有冻结测试和只读证据，不产生新参数。",
        "- 运行后判断：否。closure 是反证归纳；如果继续围绕 sleeve 手数、progress R、heat 阈值、品种、方向或年份救参，就会过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。它把一条已经连续反证的分支正式收束，减少后续重复探索。",
        "- 运行后判断：pyramiding/sleeve 分支继续价值低；整条候选分钟规则研究线仍有价值，但方向应切换到 C9 本体的新信息源或账户层非交易生存线。",
        "",
        "## 输出文件",
        "",
        f"- route summary：`{ROUTE_SUMMARY_PATH}`",
        f"- scorecard：`{SCORECARD_PATH}`",
        f"- visual index：`{VISUAL_INDEX_PATH}`",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    route_summary = _build_route_summary()
    scorecard = _build_scorecard(route_summary)
    visual_index = _build_visual_index()
    _plot_summary(route_summary, scorecard)
    decision = _decision(route_summary, scorecard)

    route_summary.to_csv(ROUTE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    scorecard.to_csv(SCORECARD_PATH, index=False, encoding="utf-8-sig")
    visual_index.to_csv(VISUAL_INDEX_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "official_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "route_summary": route_summary.to_dict("records"),
        "scorecard": scorecard.to_dict("records"),
        "visual_index_rows": int(len(visual_index)),
        "outputs": {
            "route_summary": str(ROUTE_SUMMARY_PATH),
            "scorecard": str(SCORECARD_PATH),
            "visual_index": str(VISUAL_INDEX_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "guardrails": {
            "strategy_changed": False,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "formal_ab_triggered": False,
            "readonly_only": True,
            "new_rule_created": False,
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(route_summary, scorecard, visual_index, decision)
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
