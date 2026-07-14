from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT_DIR / "research" / "lines" / "futures_trend_option_convexity_tushare_coverage"
INPUT_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage131_c9_event_targeted_option_acquisition_manifest"
    / "rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_query_events_"
    "stage131_c9_event_targeted_option_acquisition_manifest_v1.csv"
)
OUTPUT_DIR = LINE_DIR / "outputs" / "stage001_structural_option_existence_gate"
EXPECTED_INPUT_SHA256 = "7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a"
CRITICAL_START = pd.Timestamp("2022-03-09")
CRITICAL_END = pd.Timestamp("2022-06-29")
KEY_PRODUCTS = ("fu.SHFE", "jm.DCE", "FG.CZCE", "SM.CZCE", "hc.SHFE")


# Only the existence date is used. No option price, strike, DTE, or strategy result enters this gate.
OPTION_EXISTENCE: dict[str, dict[str, Any]] = {
    "fu.SHFE": {
        "first_list_year": 2025,
        "evidence": "SHFE option parameter guide: fuel-oil option listing notice dated 2025-08-18",
        "source_url": "https://www.shfe.com.cn/services/indexopt/guideline/202108/t20210804_797694.html",
    },
    "MA.CZCE": {
        "first_list_year": 2019,
        "evidence": "CZCE 2025 white paper product table",
        "source_url": "https://www.czce.com.cn/cn/content_file/gyjys/qhscyjcs/cgxc/2026/4/077939e9d8fc4ad088cd76a52ed8d3a0.pdf",
    },
    "SM.CZCE": {
        "first_list_year": 2023,
        "evidence": "CZCE 2025 white paper product table",
        "source_url": "https://www.czce.com.cn/cn/content_file/gyjys/qhscyjcs/cgxc/2026/4/077939e9d8fc4ad088cd76a52ed8d3a0.pdf",
    },
    "jm.DCE": {
        "first_list_year": 2026,
        "evidence": "DCE coking-coal option factsheet",
        "source_url": "https://www.dce.com.cn/dce/file/2026-01-15/17684624156122c9a882b9ae6dcbb289019bc092f6fc1681.pdf",
    },
    "FG.CZCE": {
        "first_list_year": 2024,
        "evidence": "CZCE 2025 white paper product table",
        "source_url": "https://www.czce.com.cn/cn/content_file/gyjys/qhscyjcs/cgxc/2026/4/077939e9d8fc4ad088cd76a52ed8d3a0.pdf",
    },
    "au.SHFE": {
        "first_list_year": 2019,
        "evidence": "Stage132 same-underlying historical metadata extraction",
        "source_url": "research:stage132_c9_event_option_metadata_batches",
    },
    "hc.SHFE": {
        "first_list_year": None,
        "evidence": "SHFE first published a contract consultation on 2026-04-30",
        "source_url": "https://www.shfe.com.cn/publicnotice/notice/202604/t20260430_831566.html",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate(input_path: Path = INPUT_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    input_sha256 = sha256_file(input_path)
    events = pd.read_csv(input_path)
    events["entry_date"] = pd.to_datetime(events["entry_date"], errors="raise").dt.normalize()
    if len(events) != 365 or events["event_id"].nunique() != 365:
        raise RuntimeError("Stage131 input must contain 365 unique events")

    critical = events[events["entry_date"].between(CRITICAL_START, CRITICAL_END)].copy()
    if len(critical) != 16:
        raise RuntimeError("critical window must contain 16 frozen events")

    def existence_row(product: str, event_date: pd.Timestamp) -> pd.Series:
        item = OPTION_EXISTENCE.get(product)
        if item is None:
            raise RuntimeError(f"missing frozen option-existence evidence for {product}")
        first_year = item["first_list_year"]
        existed = first_year is not None and int(first_year) <= int(event_date.year)
        return pd.Series(
            {
                "same_underlying_option_existed": int(existed),
                "first_list_year": first_year,
                "existence_evidence": item["evidence"],
                "existence_source_url": item["source_url"],
            }
        )

    existence = critical.apply(
        lambda row: existence_row(str(row["product_vt_symbol"]), row["entry_date"]), axis=1
    )
    ledger = pd.concat([critical.reset_index(drop=True), existence.reset_index(drop=True)], axis=1)
    ledger["structural_status"] = ledger["same_underlying_option_existed"].map(
        {1: "same_underlying_option_existed", 0: "not_listed_at_event_date"}
    )
    ledger.sort_values(["entry_date", "product_vt_symbol", "event_id"], inplace=True)

    product_summary = (
        ledger.groupby("product_vt_symbol", as_index=False)
        .agg(
            event_count=("event_id", "size"),
            structurally_eligible_events=("same_underlying_option_existed", "sum"),
            total_original_risk_amount=("total_original_risk_amount", "sum"),
            structurally_eligible_risk_amount=(
                "total_original_risk_amount",
                lambda values: float(
                    values[ledger.loc[values.index, "same_underlying_option_existed"].eq(1)].sum()
                ),
            ),
            first_list_year=("first_list_year", "first"),
            evidence=("existence_evidence", "first"),
            source_url=("existence_source_url", "first"),
        )
        .sort_values("total_original_risk_amount", ascending=False)
    )
    product_summary["event_coverage_ratio"] = (
        product_summary["structurally_eligible_events"] / product_summary["event_count"]
    )
    product_summary["risk_coverage_ratio"] = (
        product_summary["structurally_eligible_risk_amount"]
        / product_summary["total_original_risk_amount"]
    )

    total_events = int(len(ledger))
    eligible_events = int(ledger["same_underlying_option_existed"].sum())
    total_risk = round(float(ledger["total_original_risk_amount"].sum()), 6)
    eligible_risk = round(
        float(ledger.loc[ledger["same_underlying_option_existed"].eq(1), "total_original_risk_amount"].sum()),
        6,
    )
    key_rows = product_summary[product_summary["product_vt_symbol"].isin(KEY_PRODUCTS)].copy()
    key_zero_coverage = sorted(
        key_rows.loc[key_rows["event_coverage_ratio"].eq(0.0), "product_vt_symbol"].tolist()
    )
    input_hash_ok = input_sha256 == EXPECTED_INPUT_SHA256
    core_event_gate = eligible_events / total_events >= 0.90
    core_risk_gate = eligible_risk / total_risk >= 0.90
    key_product_gate = len(key_rows) == len(KEY_PRODUCTS) and bool(
        key_rows["event_coverage_ratio"].ge(0.85).all()
    )

    decision = {
        "decision": "CLOSE_LINE_MARKET_STRUCTURE_INELIGIBLE",
        "input_path": str(input_path),
        "input_sha256": input_sha256,
        "expected_input_sha256": EXPECTED_INPUT_SHA256,
        "input_hash_ok": input_hash_ok,
        "critical_window_start": CRITICAL_START.date().isoformat(),
        "critical_window_end": CRITICAL_END.date().isoformat(),
        "critical_event_count": total_events,
        "structurally_eligible_event_count": eligible_events,
        "structural_event_coverage_ratio": eligible_events / total_events,
        "critical_total_original_risk_amount": total_risk,
        "structurally_eligible_risk_amount": eligible_risk,
        "structural_risk_coverage_ratio": eligible_risk / total_risk,
        "key_products": list(KEY_PRODUCTS),
        "key_products_with_zero_coverage": key_zero_coverage,
        "gates": {
            "input_hash_ok": input_hash_ok,
            "critical_event_coverage_ge_90pct": core_event_gate,
            "critical_risk_coverage_ge_90pct": core_risk_gate,
            "each_key_product_coverage_ge_85pct": key_product_gate,
        },
        "tushare_smoke_status": "invalid_token_no_data_downloaded",
        "ready_for_option_strategy_ab": False,
        "ready_for_live": False,
        "reason": (
            "Most 2022 critical-window underlyings had no listed same-underlying option. "
            "A different vendor cannot repair a market instrument that did not exist."
        ),
    }
    if input_hash_ok and all(decision["gates"].values()):
        raise RuntimeError("structural gate unexpectedly passed")
    return ledger, product_summary, decision


def write_outputs(output_dir: Path = OUTPUT_DIR) -> dict[str, Path]:
    ledger, product_summary, decision = evaluate()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "ledger": output_dir / "stage001_critical_window_structural_ledger.csv",
        "product_summary": output_dir / "stage001_critical_window_product_summary.csv",
        "decision": output_dir / "stage001_structural_decision.json",
        "report": output_dir / "stage001_structural_report.md",
    }
    ledger.to_csv(paths["ledger"], index=False)
    product_summary.to_csv(paths["product_summary"], index=False)
    paths["decision"].write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = "\n".join(
        [
            "# Stage001 same-underlying option structural gate",
            "",
            f"- decision: `{decision['decision']}`",
            f"- critical events: `{decision['structurally_eligible_event_count']}/{decision['critical_event_count']}` "
            f"(`{decision['structural_event_coverage_ratio']:.6%}`)",
            f"- critical risk: `{decision['structurally_eligible_risk_amount']:.1f}/"
            f"{decision['critical_total_original_risk_amount']:.1f}` "
            f"(`{decision['structural_risk_coverage_ratio']:.6%}`)",
            f"- zero-coverage key products: `{','.join(decision['key_products_with_zero_coverage'])}`",
            f"- Tushare smoke: `{decision['tushare_smoke_status']}`",
            "- No option price, strike, DTE, strategy PnL, or future return was read.",
        ]
    )
    paths["report"].write_text(report + "\n", encoding="utf-8")
    return paths


if __name__ == "__main__":
    written = write_outputs()
    print(json.dumps({name: str(path) for name, path in written.items()}, sort_keys=True))
