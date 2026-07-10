from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from build_qmt_roll_stage182_ai_product_pool_live_inference_runner import (
    COMBINED_ELIGIBILITY_PATH,
    ELIGIBILITY_COLUMNS,
    OUTPUT_DIR,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


MODEL_TAG = "stage174_ai_pool_snapshot_repair_v1"
OUTPUT_PREFIX = "qmt_roll_stage174_ai_pool_snapshot_repair"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.txt"

RECOVERED_SNAPSHOTS: dict[str, dict[str, Any]] = {
    "2026-03-31": {
        "products": [
            "SH.CZCE",
            "jm.DCE",
            "cu.SHFE",
            "FG.CZCE",
            "SA.CZCE",
            "sp.SHFE",
            "ru.SHFE",
            "lh.DCE",
            "fu.SHFE",
        ],
        "score_type": "stage174_recovered_stage189_20260509_membership_only_no_original_score",
        "evidence": "research/lines/futures_trend/stages/20260509_1450_stage189_ai_pool_backfill_multimonth_replay.md",
    },
    "2026-04-30": {
        "products": [
            "SA.CZCE",
            "SH.CZCE",
            "FG.CZCE",
            "si.GFEX",
            "MA.CZCE",
            "jm.DCE",
            "rb.SHFE",
            "AP.CZCE",
            "fu.SHFE",
        ],
        "score_type": "stage174_recovered_stage189_20260509_membership_only_no_original_score",
        "evidence": "research/lines/futures_trend/stages/20260509_1450_stage189_ai_pool_backfill_multimonth_replay.md",
    },
    "2026-05-29": {
        "products": [
            "SA.CZCE",
            "si.GFEX",
            "FG.CZCE",
            "MA.CZCE",
            "OI.CZCE",
            "jm.DCE",
            "AP.CZCE",
            "rb.SHFE",
            "fu.SHFE",
        ],
        "score_type": "stage174_recovered_stage294_stage109_membership_only_no_original_score",
        "evidence": (
            "research/lines/futures_trend/stages/20260604_1900_stage294_stage78_shadow_20260604_ai_pool.md; "
            "research/lines/futures_trend_stage819_intraday_rules/stages/"
            "20260622_1731_stage109_c9_live_monthly_ai_pool_wiring_fix.md"
        ),
    },
}


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeError:
        return pd.read_csv(path)


def _build_recovered_rows() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    strategy = str(AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME)
    for eval_date, snapshot in RECOVERED_SNAPSHOTS.items():
        products = list(snapshot["products"])
        if len(products) != 9:
            raise ValueError(f"recovered snapshot {eval_date} must contain exactly 9 products")
        for rank, product in enumerate(products, start=1):
            rows.append(
                {
                    "strategy": strategy,
                    "score_type": str(snapshot["score_type"]),
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": 0.0,
                    "score_rank": rank,
                    "top_n": 9,
                }
            )
    return pd.DataFrame(rows, columns=ELIGIBILITY_COLUMNS)


def _membership_by_eval_date(frame: pd.DataFrame) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for eval_date, group in frame.groupby("eval_date"):
        ordered = group.sort_values(["score_rank", "product_vt_symbol"], kind="stable")
        result[str(eval_date)] = ordered["product_vt_symbol"].astype(str).tolist()
    return result


def main() -> None:
    if not COMBINED_ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(f"missing combined eligibility file: {COMBINED_ELIGIBILITY_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = COMBINED_ELIGIBILITY_PATH.with_name(
        f"{COMBINED_ELIGIBILITY_PATH.name}.bak_{timestamp}_{MODEL_TAG}"
    )
    shutil.copy2(COMBINED_ELIGIBILITY_PATH, backup_path)

    current = _read_csv(COMBINED_ELIGIBILITY_PATH)
    for column in ELIGIBILITY_COLUMNS:
        if column not in current.columns:
            current[column] = ""
    current = current.loc[:, ELIGIBILITY_COLUMNS].copy()

    recovered = _build_recovered_rows()
    strategy = str(AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME)
    recovered_dates = set(recovered["eval_date"].astype(str))
    keep = ~(
        current["strategy"].astype(str).eq(strategy)
        & current["eval_date"].astype(str).isin(recovered_dates)
    )
    repaired = pd.concat([current[keep].copy(), recovered], ignore_index=True)
    repaired["score_rank"] = pd.to_numeric(repaired["score_rank"], errors="coerce").fillna(999).astype(int)
    repaired["top_n"] = pd.to_numeric(repaired["top_n"], errors="coerce").fillna(0).astype(int)
    repaired.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    repaired.reset_index(drop=True, inplace=True)

    repaired.to_csv(COMBINED_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    recovered_view = repaired[
        repaired["strategy"].astype(str).eq(strategy)
        & repaired["eval_date"].astype(str).isin(recovered_dates)
    ].copy()

    recovered_membership = _membership_by_eval_date(recovered_view)
    if "rb.SHFE" not in recovered_membership.get("2026-05-29", []):
        raise RuntimeError("2026-05-29 recovered membership must include rb.SHFE")
    if "SM.CZCE" in recovered_membership.get("2026-05-29", []):
        raise RuntimeError("2026-05-29 recovered membership must not use the later SM.CZCE rerun snapshot")

    eval_dates = repaired[repaired["strategy"].astype(str).eq(strategy)]["eval_date"].astype(str)
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": generated_at,
        "combined_eligibility_path": str(COMBINED_ELIGIBILITY_PATH),
        "backup_path": str(backup_path),
        "before_rows": int(len(current)),
        "after_rows": int(len(repaired)),
        "recovered_rows": int(len(recovered)),
        "recovered_eval_dates": sorted(recovered_dates),
        "recovered_membership_by_eval_date": recovered_membership,
        "evidence_by_eval_date": {
            eval_date: str(snapshot["evidence"])
            for eval_date, snapshot in RECOVERED_SNAPSHOTS.items()
        },
        "strategy_membership_only_repair": True,
        "score_columns_are_recovered_placeholders": True,
        "eval_date_tail": sorted(eval_dates.drop_duplicates().tolist())[-10:],
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "real_order_enabled": False,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "Stage174 AI池历史月度截面修复",
        "",
        f"生成时间：{generated_at}",
        f"组合AI池：{COMBINED_ELIGIBILITY_PATH}",
        f"备份文件：{backup_path}",
        f"修复前行数：{len(current)}",
        f"修复后行数：{len(repaired)}",
        f"恢复截面：{', '.join(sorted(recovered_dates))}",
        "说明：本修复只恢复当时留档的品种成员资格，score 列为占位，不伪造原始模型分数。",
        "下单 API 次数：0",
        "撤单 API 次数：0",
        "",
        "恢复后成员：",
    ]
    for eval_date, products in recovered_membership.items():
        lines.append(f"{eval_date}: {', '.join(products)}")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
