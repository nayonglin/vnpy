"""Qualify the first active marginal-slot month without reading performance."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import pandas as pd


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage011_marginal_slot_activity_qualification"
PREREGISTRATION = LINE / "stages/20260901_1746_stage011_marginal_slot_activity_qualification.md"
RANKING_PATH = LINE / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
PRODUCTION_REPO = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
SOURCE_COMMIT = "6750783fe7aab92e6dbdd6820fa212e2e53ea353"
SOURCE_PATH = (
    "research/lines/futures_trend_rollover_shape_same_volume/artifacts/"
    "stage061_ai_top10_to_top19_fullperiod/stage061_trades.csv"
)
FIRST_EVAL_DATE = "2022-04-29"
USED_TRADE_COLUMNS = ["experiment_arm", "offset", "date", "vt_symbol"]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_bytes(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=PRODUCTION_REPO,
        check=True,
        capture_output=True,
    ).stdout


def _git_blob_id(commit: str, path: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"],
        cwd=PRODUCTION_REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def contract_to_product(vt_symbol: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)\d+(\..+)", str(vt_symbol))
    if not match:
        raise ValueError(f"unrecognized_contract_symbol:{vt_symbol}")
    return f"{match.group(1)}{match.group(2)}"


def build_activity_audit(
    trades: pd.DataFrame,
    ranking: pd.DataFrame,
    *,
    first_eval_date: str = FIRST_EVAL_DATE,
    product_resolver: Callable[[str], str] = contract_to_product,
) -> pd.DataFrame:
    missing_trades = set(USED_TRADE_COLUMNS) - set(trades.columns)
    missing_ranking = {"eval_date", "product_vt_symbol", "score_rank"} - set(ranking.columns)
    if missing_trades:
        raise RuntimeError(f"trade_columns_missing:{sorted(missing_trades)}")
    if missing_ranking:
        raise RuntimeError(f"ranking_columns_missing:{sorted(missing_ranking)}")
    activity = trades.loc[:, USED_TRADE_COLUMNS].copy()
    activity = activity[
        activity["experiment_arm"].astype(str).eq("T18")
        & activity["offset"].astype(str).isin({"开", "Open"})
    ].copy()
    activity["date"] = pd.to_datetime(activity["date"], errors="raise").dt.normalize()
    activity["product_vt_symbol"] = activity["vt_symbol"].astype(str).map(product_resolver)

    ranking = ranking.loc[:, ["eval_date", "product_vt_symbol", "score_rank"]].copy()
    ranking["eval_date"] = pd.to_datetime(ranking["eval_date"], errors="raise").dt.normalize()
    ranking["score_rank"] = pd.to_numeric(ranking["score_rank"], errors="raise").astype(int)
    if ranking.duplicated(["eval_date", "score_rank"]).any():
        raise RuntimeError("ranking_duplicate_month_rank")
    dates = sorted(ranking["eval_date"].unique())
    rows: list[dict[str, Any]] = []
    for index, eval_value in enumerate(dates[:-1]):
        eval_date = pd.Timestamp(eval_value).normalize()
        if eval_date < pd.Timestamp(first_eval_date):
            continue
        next_eval_date = pd.Timestamp(dates[index + 1]).normalize()
        month_activity = activity[
            activity["date"].gt(eval_date) & activity["date"].le(next_eval_date)
        ]
        month_ranking = ranking[
            ranking["eval_date"].eq(eval_date) & ranking["score_rank"].between(10, 18)
        ].sort_values("score_rank")
        if len(month_ranking) != 9:
            raise RuntimeError(f"marginal_rank_shape:{eval_date.date()}:{len(month_ranking)}")
        for item in month_ranking.itertuples(index=False):
            product = str(item.product_vt_symbol)
            rows.append(
                {
                    "eval_date": eval_date.date().isoformat(),
                    "next_eval_date": next_eval_date.date().isoformat(),
                    "score_rank": int(item.score_rank),
                    "product_vt_symbol": product,
                    "t18_open_trade_count": int(
                        month_activity["product_vt_symbol"].eq(product).sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def select_first_qualified_month(
    audit: pd.DataFrame,
    *,
    min_active_challengers: int = 2,
) -> dict[str, Any]:
    required = {
        "eval_date",
        "next_eval_date",
        "score_rank",
        "product_vt_symbol",
        "t18_open_trade_count",
    }
    if missing := sorted(required - set(audit.columns)):
        raise RuntimeError(f"audit_columns_missing:{missing}")
    for eval_date, month in audit.groupby("eval_date", sort=True):
        baseline = month[month["score_rank"].eq(10)]
        active_challengers = month[
            month["score_rank"].gt(10) & month["t18_open_trade_count"].ge(1)
        ].sort_values("score_rank")
        if (
            len(baseline) == 1
            and int(baseline.iloc[0]["t18_open_trade_count"]) >= 1
            and len(active_challengers) >= min_active_challengers
        ):
            return {
                "eval_date": str(eval_date),
                "next_eval_date": str(month["next_eval_date"].iloc[0]),
                "baseline_rank": 10,
                "baseline_product": str(baseline.iloc[0]["product_vt_symbol"]),
                "challenger_ranks": active_challengers["score_rank"].astype(int).tolist(),
                "challenger_products": active_challengers[
                    "product_vt_symbol"
                ].astype(str).tolist(),
                "selection_rule": (
                    "first_eval_date_with_rank10_open_and_at_least_"
                    f"{min_active_challengers}_lower_rank_opens_in_T18"
                ),
            }
    raise RuntimeError("no_qualified_activity_month")


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"stage011_output_already_exists:{OUT}")
    source_payload = _git_bytes(SOURCE_COMMIT, SOURCE_PATH)
    source_all = pd.read_csv(BytesIO(source_payload))
    source = source_all.loc[:, USED_TRADE_COLUMNS].copy()
    ranking = pd.read_csv(RANKING_PATH)
    audit = build_activity_audit(source, ranking)
    selection = select_first_qualified_month(audit)
    if (
        selection["eval_date"] != "2022-05-31"
        or selection["next_eval_date"] != "2022-06-30"
        or selection["baseline_rank"] != 10
        or selection["challenger_ranks"] != [12, 13]
    ):
        raise RuntimeError(f"stage011_mechanical_selection_drift:{selection}")
    OUT.mkdir(parents=True)
    audit_path = OUT / "activity_audit.csv"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    selection.update(
        {
            "line_id": "futures_trend_ai_xgboost_ensemble",
            "stage": "Stage011",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "decision": "stage011_first_active_marginal_month_qualified",
            "source_commit": SOURCE_COMMIT,
            "source_path": SOURCE_PATH,
            "source_blob_id": _git_blob_id(SOURCE_COMMIT, SOURCE_PATH),
            "source_payload_sha256": _sha256(source_payload),
            "source_total_rows": int(len(source_all)),
            "source_columns_consumed": USED_TRADE_COLUMNS,
            "performance_columns_consumed": [],
            "ranking_sha256": _sha256(RANKING_PATH.read_bytes()),
            "preregistration_sha256": _sha256(PREREGISTRATION.read_bytes()),
            "activity_audit_sha256": _sha256(audit_path.read_bytes()),
            "runs_backtest": False,
            "trains_model": False,
            "order_api_called_count": 0,
            "ctp_connected": False,
        }
    )
    (OUT / "selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    selected_rows = audit[audit["eval_date"].eq(selection["eval_date"])]
    report = (
        "# Stage011 边际席位活动资格\n\n"
        f"- 决策：`{selection['decision']}`\n"
        f"- 机械选择：`{selection['eval_date']}`至`{selection['next_eval_date']}`。\n"
        f"- A：rank10 `{selection['baseline_product']}`。\n"
        f"- C：ranks `{selection['challenger_ranks']}`，产品 `{selection['challenger_products']}`。\n"
        f"- 只消费成交列：`{USED_TRADE_COLUMNS}`；消费绩效列：`[]`。\n"
        "- 本阶段不回测、不训练模型、不连接CTP、不调用订单API。\n\n"
        + selected_rows.to_markdown(index=False)
        + "\n"
    )
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(selection, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
