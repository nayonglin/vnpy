from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parent / "backtest_outputs"
MODEL_TAG = "stage643_base_metals_authorized_source_fallback_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage643_base_metals_authorized_source_fallback_board"

STAGE640_DECISION = OUTPUT_DIR / (
    "qmt_roll_stage640_base_metals_official_source_fetch_probe_decision_"
    "stage640_base_metals_official_source_fetch_probe_v1.json"
)
STAGE640_READINESS = OUTPUT_DIR / (
    "qmt_roll_stage640_base_metals_official_source_fetch_probe_source_readiness_"
    "stage640_base_metals_official_source_fetch_probe_v1.csv"
)
STAGE641_DECISION = OUTPUT_DIR / (
    "qmt_roll_stage641_shfe_current_warehouse_route_forensic_decision_"
    "stage641_shfe_current_warehouse_route_forensic_v1.json"
)
STAGE641_ROUTE = OUTPUT_DIR / (
    "qmt_roll_stage641_shfe_current_warehouse_route_forensic_route_matrix_"
    "stage641_shfe_current_warehouse_route_forensic_v1.csv"
)

SOURCE_REFS = {
    "lme_data_distribution": "https://www.lme.com/Market-data/Market-data-licensing/Data-distribution",
    "lme_market_data_faq": "https://www.lme.com/en/about/faqs/market-data-faqs",
    "lme_warehousing": "https://www.lme.com/en/Physical-services/Warehousing",
    "shfe_vendor_list": "https://tsite.shfe.com.cn/eng/services/marketdata/vendorlist/",
    "shfe_information_rules": "https://www.shfe.com.cn/eng/services/Rules/SHFERules/202508/t20250807_828562.html",
    "cqg_shfe_warehouse": "https://news.cqg.com/news/announcements/2023/06/shanghai-futures-exchange-shfe-warehouse-data",
}


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _bool_text(value: bool | int | float) -> str:
    return "yes" if bool(value) else "no"


def build_board() -> dict[str, pd.DataFrame | dict]:
    stage640_decision = _read_json(STAGE640_DECISION)
    stage641_decision = _read_json(STAGE641_DECISION)
    stage640_readiness = _read_csv(STAGE640_READINESS)
    stage641_route = _read_csv(STAGE641_ROUTE)

    official_current_payload_ready = int(stage641_decision.get("official_current_payload_ready_rows", 0))
    legacy_shape_rows = int(stage641_decision.get("legacy_payload_shape_validated_rows", 0))
    blocked_current_rows = int(stage641_decision.get("blocked_current_rows", 0))
    waf_like_rows = int(stage641_decision.get("waf_like_rows", 0))
    stage640_payload_rows = int(stage640_decision.get("payload_data_validated_rows", 0))
    stage640_waf_rows = int(stage640_decision.get("waf_like_rows", 0))

    source_options = pd.DataFrame(
        [
            {
                "option_id": "lme_xml_next_day_feed",
                "authority": "official_lme",
                "route_type": "licensed_xml_feed",
                "economic_driver": "global_base_metal_inventory",
                "evidence": "LME FAQ says next-day XML feed includes key reports such as warehouse stock movements and is subscribed via OLP.",
                "official": 1,
                "authorized_contract_route_identified": 1,
                "machine_readable_api_or_download_documented": 1,
                "terms_allow_automation_needs_contract": 1,
                "access_owned_now": 0,
                "current_payload_ready_now": 0,
                "pit_raw_hash_possible_after_access": 1,
                "schema_sufficient_after_access": 1,
                "selector_allowed_now": 0,
                "next_action": "Price/terms review, acquire OLP XML access, then run a one-day raw-hash parser probe.",
            },
            {
                "option_id": "lme_olp_daily_off_warrant_report",
                "authority": "official_lme",
                "route_type": "licensed_olp_report",
                "economic_driver": "off_warrant_base_metal_inventory",
                "evidence": "LME warehousing page points to OLP for T+1 daily off-warrant stock reports.",
                "official": 1,
                "authorized_contract_route_identified": 1,
                "machine_readable_api_or_download_documented": 0,
                "terms_allow_automation_needs_contract": 1,
                "access_owned_now": 0,
                "current_payload_ready_now": 0,
                "pit_raw_hash_possible_after_access": 1,
                "schema_sufficient_after_access": 0,
                "selector_allowed_now": 0,
                "next_action": "Confirm report format and automation rights in OLP before considering a parser.",
            },
            {
                "option_id": "lme_public_web_current_report",
                "authority": "official_lme",
                "route_type": "public_web",
                "economic_driver": "global_base_metal_inventory",
                "evidence": "Stage640 public LME current page route had page/hash evidence but no current payload.",
                "official": 1,
                "authorized_contract_route_identified": 0,
                "machine_readable_api_or_download_documented": 0,
                "terms_allow_automation_needs_contract": 0,
                "access_owned_now": 1,
                "current_payload_ready_now": 0,
                "pit_raw_hash_possible_after_access": 0,
                "schema_sufficient_after_access": 0,
                "selector_allowed_now": 0,
                "next_action": "Do not keep scraping public current pages as production source.",
            },
            {
                "option_id": "shfe_authorized_market_data_vendor",
                "authority": "official_shfe_or_licensed_vendor",
                "route_type": "authorized_vendor_feed",
                "economic_driver": "china_exchange_warrant_inventory",
                "evidence": "SHFE publishes an authorized market data vendor list and contact; CQG announces SHFE weekly warehouse data symbols.",
                "official": 1,
                "authorized_contract_route_identified": 1,
                "machine_readable_api_or_download_documented": 1,
                "terms_allow_automation_needs_contract": 1,
                "access_owned_now": 0,
                "current_payload_ready_now": 0,
                "pit_raw_hash_possible_after_access": 1,
                "schema_sufficient_after_access": 1,
                "selector_allowed_now": 0,
                "next_action": "Confirm vendor coverage for daily/weekly warehouse fields and automation rights; then run vendor feed PIT probe.",
            },
            {
                "option_id": "shfe_public_current_dailystock",
                "authority": "official_shfe",
                "route_type": "public_web_or_dat",
                "economic_driver": "china_exchange_warrant_inventory",
                "evidence": "Stage641 direct/session/browser/cookie replay found current public routes blocked, WAF-like, or 404; legacy shape only.",
                "official": 1,
                "authorized_contract_route_identified": 0,
                "machine_readable_api_or_download_documented": 0,
                "terms_allow_automation_needs_contract": 0,
                "access_owned_now": 1,
                "current_payload_ready_now": 0,
                "pit_raw_hash_possible_after_access": 0,
                "schema_sufficient_after_access": 0,
                "selector_allowed_now": 0,
                "next_action": "Stop retrying the same public endpoints; keep as forensic evidence only.",
            },
            {
                "option_id": "third_party_monitor_only",
                "authority": "non_official_or_vendor_unclear",
                "route_type": "monitor_only",
                "economic_driver": "base_metal_inventory_proxy",
                "evidence": "Third-party pages may help manual monitoring, but authorization/PIT/schema provenance is not closed.",
                "official": 0,
                "authorized_contract_route_identified": 0,
                "machine_readable_api_or_download_documented": 0,
                "terms_allow_automation_needs_contract": 0,
                "access_owned_now": 0,
                "current_payload_ready_now": 0,
                "pit_raw_hash_possible_after_access": 0,
                "schema_sufficient_after_access": 0,
                "selector_allowed_now": 0,
                "next_action": "Do not use for selector until authorization and raw source provenance are explicit.",
            },
        ]
    )

    score_cols = [
        "official",
        "authorized_contract_route_identified",
        "machine_readable_api_or_download_documented",
        "terms_allow_automation_needs_contract",
        "access_owned_now",
        "current_payload_ready_now",
        "pit_raw_hash_possible_after_access",
        "schema_sufficient_after_access",
    ]
    source_options["readiness_score"] = source_options[score_cols].sum(axis=1)
    source_options["post_contract_candidate"] = (
        source_options["official"].eq(1)
        & source_options["authorized_contract_route_identified"].eq(1)
        & source_options["machine_readable_api_or_download_documented"].eq(1)
        & source_options["pit_raw_hash_possible_after_access"].eq(1)
        & source_options["schema_sufficient_after_access"].eq(1)
    ).astype(int)
    source_options["owned_selector_ready"] = (
        source_options["post_contract_candidate"].eq(1)
        & source_options["access_owned_now"].eq(1)
        & source_options["current_payload_ready_now"].eq(1)
    ).astype(int)

    official_public = stage641_route[stage641_route.get("source_authority", pd.Series(dtype=str)).astype(str).str.contains("official", na=False)].copy()
    public_route_summary = pd.DataFrame(
        [
            {
                "evidence_item": "Stage640 official payload data validated rows",
                "value": stage640_payload_rows,
                "interpretation": "Only legacy/partial payload evidence, not current selector source.",
            },
            {
                "evidence_item": "Stage640 WAF-like rows",
                "value": stage640_waf_rows,
                "interpretation": "Public route stability is weak.",
            },
            {
                "evidence_item": "Stage641 official current payload ready rows",
                "value": official_current_payload_ready,
                "interpretation": "Current SHFE public payload is not ready.",
            },
            {
                "evidence_item": "Stage641 legacy payload shape validated rows",
                "value": legacy_shape_rows,
                "interpretation": "Schema exists historically; it does not prove current access.",
            },
            {
                "evidence_item": "Stage641 blocked current rows",
                "value": blocked_current_rows,
                "interpretation": "Direct/session/browser/cookie attempts still blocked or wrong format.",
            },
            {
                "evidence_item": "Stage641 WAF-like rows",
                "value": waf_like_rows,
                "interpretation": "WAF/captcha risk is material for production scraping.",
            },
        ]
    )

    gates = pd.DataFrame(
        [
            {
                "gate": "public_current_payload_ready",
                "passed": int(official_current_payload_ready > 0),
                "current": str(official_current_payload_ready),
                "required": ">0",
                "note": "Current public SHFE/LME payload must be machine readable before selector use.",
            },
            {
                "gate": "public_route_retry_stopped",
                "passed": int(blocked_current_rows > 0 and waf_like_rows > 0),
                "current": f"blocked={blocked_current_rows},waf={waf_like_rows}",
                "required": "block evidence documented",
                "note": "Repeated public endpoint probing should stop unless route changes.",
            },
            {
                "gate": "authorized_contract_path_identified",
                "passed": int(source_options["post_contract_candidate"].sum() >= 1),
                "current": str(int(source_options["post_contract_candidate"].sum())),
                "required": ">=1",
                "note": "At least one official/licensed path can become source after contract/access.",
            },
            {
                "gate": "owned_access_now",
                "passed": int(source_options["access_owned_now"].mul(source_options["post_contract_candidate"]).sum() > 0),
                "current": str(int(source_options["access_owned_now"].mul(source_options["post_contract_candidate"]).sum())),
                "required": ">0",
                "note": "No licensed LME/SHFE vendor access is currently present in repo evidence.",
            },
            {
                "gate": "selector_allowed_now",
                "passed": int(source_options["owned_selector_ready"].sum() > 0),
                "current": str(int(source_options["owned_selector_ready"].sum())),
                "required": ">0",
                "note": "Contract possibility is not selector readiness.",
            },
            {
                "gate": "paper_and_whitelist_zero",
                "passed": 1,
                "current": "0/0",
                "required": "0/0",
                "note": "This board must not create paper or trading whitelist rows.",
            },
        ]
    )

    decision_label = "base_metals_authorized_source_paths_exist_contract_missing_selector_locked"
    if int(source_options["post_contract_candidate"].sum()) == 0:
        decision_label = "base_metals_no_authorized_source_path_selector_locked"
    if int(source_options["owned_selector_ready"].sum()) > 0:
        decision_label = "base_metals_source_owned_ready_requires_parser_probe"

    decision = {
        "generated_at_cst": _now_cst(),
        "model_tag": MODEL_TAG,
        "decision": decision_label,
        "line_id": "futures_trend_drawdown30_preserve_return",
        "official_current_payload_ready_rows": official_current_payload_ready,
        "legacy_payload_shape_validated_rows": legacy_shape_rows,
        "blocked_current_rows": blocked_current_rows,
        "waf_like_rows": waf_like_rows,
        "post_contract_candidate_rows": int(source_options["post_contract_candidate"].sum()),
        "owned_selector_ready_rows": int(source_options["owned_selector_ready"].sum()),
        "authorized_paths_identified": int(source_options["authorized_contract_route_identified"].sum()),
        "machine_readable_authorized_paths": int(
            source_options["authorized_contract_route_identified"]
            .mul(source_options["machine_readable_api_or_download_documented"])
            .sum()
        ),
        "selector_rows": 0,
        "paper_allowed": 0,
        "trading_whitelist_allowed": 0,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "source_refs": SOURCE_REFS,
    }

    return {
        "source_options": source_options,
        "public_route_summary": public_route_summary,
        "stage640_readiness": stage640_readiness,
        "stage641_official_public_routes": official_public,
        "gates": gates,
        "decision": decision,
    }


def write_outputs(board: dict[str, pd.DataFrame | dict]) -> dict[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "source_options": OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_options_{MODEL_TAG}.csv",
        "public_route_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_public_route_summary_{MODEL_TAG}.csv",
        "gates": OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "chart": OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png",
    }

    source_options = board["source_options"]
    public_route_summary = board["public_route_summary"]
    gates = board["gates"]
    decision = board["decision"]

    source_options.to_csv(paths["source_options"], index=False, encoding="utf-8-sig")
    public_route_summary.to_csv(paths["public_route_summary"], index=False, encoding="utf-8-sig")
    gates.to_csv(paths["gates"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    write_chart(source_options, public_route_summary, gates, paths["chart"])
    write_report(source_options, public_route_summary, gates, decision, paths["report"], paths["chart"])
    return paths


def write_chart(source_options: pd.DataFrame, public_route_summary: pd.DataFrame, gates: pd.DataFrame, chart_path: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle("Stage643 base metals authorized source fallback board", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    plot_options = source_options.sort_values("readiness_score")
    colors = np.where(plot_options["post_contract_candidate"].eq(1), "#2b6cb0", "#718096")
    ax.barh(plot_options["option_id"], plot_options["readiness_score"], color=colors)
    ax.set_title("Source option readiness: blue requires contract/access")
    ax.set_xlabel("readiness score")
    for i, (_, row) in enumerate(plot_options.iterrows()):
        ax.text(float(row["readiness_score"]) + 0.1, i, f"owned={_bool_text(row['access_owned_now'])}", va="center", fontsize=8)

    ax = axes[0, 1]
    metrics = public_route_summary.copy()
    chart_labels = [
        "640 payload",
        "640 WAF",
        "641 current ready",
        "641 legacy shape",
        "641 blocked",
        "641 WAF",
    ]
    ax.bar(chart_labels, metrics["value"], color=["#2b6cb0", "#dd6b20", "#e53e3e", "#38a169", "#e53e3e", "#e53e3e"])
    ax.set_title("Public route forensic: current payload still absent")
    ax.set_ylabel("count")
    ax.tick_params(axis="x", labelrotation=35)

    ax = axes[1, 0]
    heat_cols = [
        "official",
        "authorized_contract_route_identified",
        "machine_readable_api_or_download_documented",
        "access_owned_now",
        "current_payload_ready_now",
        "pit_raw_hash_possible_after_access",
        "schema_sufficient_after_access",
        "selector_allowed_now",
    ]
    heat = source_options.set_index("option_id")[heat_cols]
    ax.imshow(heat.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Contract path and selector readiness are different gates")
    ax.set_xticks(range(len(heat_cols)))
    ax.set_xticklabels(heat_cols, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(heat.index, fontsize=8)
    for r in range(heat.shape[0]):
        for c in range(heat.shape[1]):
            ax.text(c, r, str(int(heat.iloc[r, c])), ha="center", va="center", fontsize=8)

    ax = axes[1, 1]
    gate_values = gates[["passed"]].to_numpy(dtype=float).T
    ax.imshow(gate_values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Hard gates: authorized path exists, selector remains locked")
    ax.set_yticks([0])
    ax.set_yticklabels(["pass"])
    ax.set_xticks(range(len(gates)))
    ax.set_xticklabels(gates["gate"], rotation=55, ha="right", fontsize=8)
    for c, passed in enumerate(gates["passed"].astype(int)):
        ax.text(c, 0, str(passed), ha="center", va="center", fontsize=9, fontweight="bold")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(chart_path, dpi=170)
    plt.close(fig)


def write_report(
    source_options: pd.DataFrame,
    public_route_summary: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict,
    report_path: Path,
    chart_path: Path,
) -> None:
    option_cols = [
        "option_id",
        "authority",
        "route_type",
        "post_contract_candidate",
        "access_owned_now",
        "current_payload_ready_now",
        "selector_allowed_now",
        "next_action",
    ]
    report = f"""# Stage643 Base Metals Authorized Source Fallback Board

- generated_at_cst: `{decision['generated_at_cst']}`
- decision: `{decision['decision']}`
- stage nature: source fallback decision board after public SHFE/LME probes; no strategy replay, no selector, no paper, no CTP.

## External Research Judgement

Official/authorized source paths exist, but none is currently owned and selector-ready in the repo. LME provides licensed market-data routes through OLP/XML and licensed distributors; SHFE maintains authorized market-data vendors and information rules that restrict redistribution/unauthorized use. Therefore the production route cannot be public scraping. It must be licensed XML/vendor feed first, then a one-day raw-hash parser probe, then PIT accumulation and outcome/TCA gates.

References:
{chr(10).join(f"- {name}: {url}" for name, url in SOURCE_REFS.items())}

## Key Numbers

- official current payload ready rows: `{decision['official_current_payload_ready_rows']}`
- legacy payload shape validated rows: `{decision['legacy_payload_shape_validated_rows']}`
- blocked current rows: `{decision['blocked_current_rows']}`
- WAF-like rows: `{decision['waf_like_rows']}`
- post-contract candidate rows: `{decision['post_contract_candidate_rows']}`
- owned selector-ready rows: `{decision['owned_selector_ready_rows']}`
- authorized paths identified: `{decision['authorized_paths_identified']}`
- machine-readable authorized paths: `{decision['machine_readable_authorized_paths']}`
- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`

## Source Options

{source_options[option_cols].to_markdown(index=False)}

## Public Route Evidence

{public_route_summary.to_markdown(index=False)}

## Gates

{gates.to_markdown(index=False)}

## Interpretation

- `base_metals` remains economically interesting, but public routes are not production-ready.
- LME XML next-day feed and SHFE authorized vendor feed are the only credible machine-readable paths now visible.
- Contract/access possibility is not enough: without owned access, current payload, raw hash, schema, and PIT accumulation, selector remains locked.
- No paper or trading whitelist is allowed from this stage.

## Chart

- chart: `{chart_path}`
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    board = build_board()
    paths = write_outputs(board)
    print(json.dumps(board["decision"], ensure_ascii=False, indent=2))
    print("outputs:")
    for key, value in paths.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
