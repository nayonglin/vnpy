"""Attribute Stage007 failure without rerunning or changing the strategy."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
STAGE006_OUT = LINE / "artifacts/stage006_pit_corrected_ranker"
STAGE007_OUT = LINE / "artifacts/stage007_cold_true_engine_ac"
OUT = LINE / "artifacts/stage008_stage007_path_attribution"
PREREGISTRATION = LINE / "stages/20260901_1659_stage008_stage007_path_attribution.md"

STAGE006_MONTHLY = STAGE006_OUT / "monthly_metrics.csv"
STAGE006_SUMMARY = STAGE006_OUT / "summary.json"
STAGE006_PREDICTIONS = STAGE006_OUT / "oos_predictions.csv"
STAGE007_DECISION = STAGE007_OUT / "decision.json"
STAGE007_CURVE = STAGE007_OUT / "equity_curve.csv"
STAGE007_TRADES = STAGE007_OUT / "trades.csv"
STAGE007_MEMBERSHIP = STAGE007_OUT / "stage007_membership_audit.csv"
HORIZON = 60
FORMAL_ELIGIBILITY = Path(
    "/Users/bytedance/Desktop/person/vnpy_production_live/official_strategy_materials/"
    "ai_top10_plus_fu_official_live_v1/releases/"
    "m0004_20260831T112631+0800_2485073e9594/payload/ai/stage182/combined_eligibility.csv"
)

TRADE_PAYLOAD_COLUMNS = [
    "datetime",
    "vt_symbol",
    "direction",
    "offset",
    "price",
    "volume",
    "exit_reason",
]


def future_account_paths(
    curves: pd.DataFrame,
    eval_dates: pd.DatetimeIndex,
    *,
    horizon: int = HORIZON,
) -> pd.DataFrame:
    frame = curves.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    arms = sorted(frame["experiment_arm"].astype(str).unique())
    prepared: dict[str, pd.DataFrame] = {}
    for arm in arms:
        arm_frame = frame[frame["experiment_arm"].astype(str).eq(arm)].sort_values("date").copy()
        arm_frame["daily_return"] = arm_frame["account_equity"].pct_change().fillna(0.0)
        prepared[arm] = arm_frame
    rows: list[dict[str, Any]] = []
    for eval_date in pd.DatetimeIndex(eval_dates).normalize():
        for arm in arms:
            future = prepared[arm][prepared[arm]["date"] > eval_date].head(horizon)
            if len(future) != horizon:
                raise RuntimeError(f"incomplete_future_account_path:{arm}:{eval_date.date()}:{len(future)}")
            returns = future["daily_return"].to_numpy(dtype="float64")
            wealth = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
            drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
            rows.append(
                {
                    "eval_date": eval_date,
                    "experiment_arm": arm,
                    "future_return": float(wealth[-1] - 1.0),
                    "future_max_drawdown": float(drawdown.min()),
                    "future_net_pnl": float(future["net_pnl"].sum())
                    if "net_pnl" in future
                    else float("nan"),
                    "future_end_date": future["date"].iloc[-1],
                    "trading_days": len(future),
                }
            )
    return pd.DataFrame(rows)


def drawdown_episode(frame: pd.DataFrame) -> dict[str, Any]:
    ordered = frame.sort_values("date").copy()
    ordered["date"] = pd.to_datetime(ordered["date"]).dt.normalize()
    equity = pd.to_numeric(ordered["account_equity"], errors="raise")
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    trough_position = int(np.argmin(drawdown.to_numpy(dtype="float64")))
    peak_position = int(np.argmax(equity.iloc[: trough_position + 1].to_numpy(dtype="float64")))
    peak_value = float(equity.iloc[peak_position])
    recovery = ordered.iloc[trough_position + 1 :][
        equity.iloc[trough_position + 1 :].to_numpy(dtype="float64") >= peak_value
    ]
    recovery_date = (
        recovery["date"].iloc[0].date().isoformat() if not recovery.empty else None
    )
    return {
        "peak_date": ordered["date"].iloc[peak_position].date().isoformat(),
        "trough_date": ordered["date"].iloc[trough_position].date().isoformat(),
        "recovery_date": recovery_date,
        "peak_equity": peak_value,
        "trough_equity": float(equity.iloc[trough_position]),
        "max_drawdown": float(drawdown.iloc[trough_position]),
    }


def _trade_counter(frame: pd.DataFrame) -> Counter[tuple[Any, ...]]:
    missing = set(TRADE_PAYLOAD_COLUMNS) - set(frame.columns)
    if missing:
        raise RuntimeError(f"trade_payload_columns_missing:{sorted(missing)}")
    normalized = frame[TRADE_PAYLOAD_COLUMNS].copy()
    for column in ("datetime", "vt_symbol", "direction", "offset", "exit_reason"):
        normalized[column] = normalized[column].fillna("").astype(str)
    for column in ("price", "volume"):
        normalized[column] = pd.to_numeric(normalized[column], errors="raise").round(10)
    return Counter(tuple(row) for row in normalized.itertuples(index=False, name=None))


def trade_multiset_overlap(a: pd.DataFrame, c: pd.DataFrame) -> dict[str, Any]:
    a_counter = _trade_counter(a)
    c_counter = _trade_counter(c)
    common = sum((a_counter & c_counter).values())
    a_count = sum(a_counter.values())
    c_count = sum(c_counter.values())
    return {
        "a_trades": a_count,
        "c_trades": c_count,
        "common_trades": common,
        "a_only_trades": a_count - common,
        "c_only_trades": c_count - common,
        "common_share_of_a": common / a_count if a_count else 0.0,
        "common_share_of_c": common / c_count if c_count else 0.0,
    }


def contract_to_product(vt_symbol: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)\d+(\..+)", str(vt_symbol))
    if not match:
        raise ValueError(f"unrecognized_contract_symbol:{vt_symbol}")
    return f"{match.group(1)}{match.group(2)}"


def formal_proxy_membership_audit(
    formal: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    top_n: int = 10,
) -> pd.DataFrame:
    formal_frame = formal.copy()
    prediction_frame = predictions.copy()
    formal_frame["eval_date"] = pd.to_datetime(formal_frame["eval_date"]).dt.normalize()
    prediction_frame["eval_date"] = pd.to_datetime(prediction_frame["eval_date"]).dt.normalize()
    rows: list[dict[str, Any]] = []
    for eval_date, month in prediction_frame.groupby("eval_date", sort=True):
        formal_products = set(
            formal_frame[
                formal_frame["eval_date"].eq(eval_date)
                & ~formal_frame["product_vt_symbol"].astype(str).eq("fu.SHFE")
            ]["product_vt_symbol"].astype(str)
        )
        if len(formal_products) != top_n:
            raise RuntimeError(f"formal_pool_shape:{eval_date.date()}:{len(formal_products)}")
        proxy_a = set(
            month.sort_values(
                ["score_logistic", "product_vt_symbol"],
                ascending=[False, True],
                kind="mergesort",
            ).head(top_n)["product_vt_symbol"].astype(str)
        )
        c3 = set(
            month.sort_values(
                ["score_two_month_confirmed", "product_vt_symbol"],
                ascending=[False, True],
                kind="mergesort",
            ).head(top_n)["product_vt_symbol"].astype(str)
        )
        rows.append(
            {
                "eval_date": eval_date,
                "formal_equals_proxy_a": formal_products == proxy_a,
                "formal_equals_c3": formal_products == c3,
                "formal_vs_proxy_a_swap_count": len(proxy_a - formal_products),
                "formal_vs_c3_swap_count": len(c3 - formal_products),
                "proxy_a_added_vs_formal": ",".join(sorted(proxy_a - formal_products)),
                "proxy_a_removed_vs_formal": ",".join(sorted(formal_products - proxy_a)),
                "c3_added_vs_formal": ",".join(sorted(c3 - formal_products)),
                "c3_removed_vs_formal": ",".join(sorted(formal_products - c3)),
            }
        )
    return pd.DataFrame(rows)


def _identity(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file_changed_while_hashing:{path}")
    return {"path": str(path.resolve()), "size": after.st_size, "sha256": digest.hexdigest()}


def _period_metrics(curves: pd.DataFrame, period: str) -> pd.DataFrame:
    frame = curves.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame.sort_values(["experiment_arm", "date"], inplace=True)
    frame["daily_return"] = frame.groupby("experiment_arm")["account_equity"].pct_change().fillna(0.0)
    frame["period"] = frame["date"].dt.to_period(period).astype(str)
    rows: list[dict[str, Any]] = []
    for (value, arm), group in frame.groupby(["period", "experiment_arm"], sort=True):
        returns = group["daily_return"].to_numpy(dtype="float64")
        wealth = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
        drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
        rows.append(
            {
                "period": value,
                "experiment_arm": arm,
                "net_pnl": float(group["net_pnl"].sum()),
                "compounded_return": float(wealth[-1] - 1.0),
                "path_max_drawdown": float(drawdown.min()),
                "trading_days": len(group),
            }
        )
    long = pd.DataFrame(rows)
    metrics = ["net_pnl", "compounded_return", "path_max_drawdown", "trading_days"]
    wide = long.pivot(index="period", columns="experiment_arm", values=metrics)
    wide.columns = [f"{metric}_{arm}" for metric, arm in wide.columns]
    wide.reset_index(inplace=True)
    for metric in ("net_pnl", "compounded_return", "path_max_drawdown"):
        wide[f"{metric}_delta_c_minus_a"] = wide[f"{metric}_C"] - wide[f"{metric}_A1"]
    return wide


def _first_trade_divergence(a: pd.DataFrame, c: pd.DataFrame) -> str | None:
    dates = sorted(set(a["date"].astype(str)) | set(c["date"].astype(str)))
    for date in dates:
        if _trade_counter(a[a["date"].astype(str).eq(date)]) != _trade_counter(
            c[c["date"].astype(str).eq(date)]
        ):
            return date
    return None


def _transfer_table(
    stage006_monthly: pd.DataFrame,
    account_paths: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    monthly = stage006_monthly[
        stage006_monthly["arm"].isin(["A_logistic", "C3_confirmed"])
    ].copy()
    monthly["eval_date"] = pd.to_datetime(monthly["eval_date"]).dt.normalize()
    proxy = monthly.pivot(
        index="eval_date",
        columns="arm",
        values=[
            "top10_future_net_pnl_60d",
            "top10_future_max_drawdown_60d",
            "dual_rank_ic",
        ],
    )
    proxy.columns = [f"proxy_{metric}_{arm}" for metric, arm in proxy.columns]
    proxy.reset_index(inplace=True)
    proxy["proxy_pnl_delta_c_minus_a"] = (
        proxy["proxy_top10_future_net_pnl_60d_C3_confirmed"]
        - proxy["proxy_top10_future_net_pnl_60d_A_logistic"]
    )
    proxy["proxy_drawdown_delta_c_minus_a"] = (
        proxy["proxy_top10_future_max_drawdown_60d_C3_confirmed"]
        - proxy["proxy_top10_future_max_drawdown_60d_A_logistic"]
    )
    account = account_paths.pivot(
        index="eval_date",
        columns="experiment_arm",
        values=["future_return", "future_max_drawdown", "future_net_pnl", "future_end_date"],
    )
    account.columns = [f"engine_{metric}_{arm}" for metric, arm in account.columns]
    account.reset_index(inplace=True)
    account["engine_return_delta_c_minus_a"] = (
        account["engine_future_return_C"] - account["engine_future_return_A1"]
    )
    account["engine_drawdown_delta_c_minus_a"] = (
        account["engine_future_max_drawdown_C"]
        - account["engine_future_max_drawdown_A1"]
    )
    account["engine_net_pnl_delta_c_minus_a"] = (
        account["engine_future_net_pnl_C"] - account["engine_future_net_pnl_A1"]
    )
    audit = membership[membership["source"].eq("stage006_oos")][
        ["eval_date", "changed_member_count", "added_products", "removed_products"]
    ].copy()
    audit["eval_date"] = pd.to_datetime(audit["eval_date"]).dt.normalize()
    return proxy.merge(account, on="eval_date", validate="one_to_one").merge(
        audit,
        on="eval_date",
        validate="one_to_one",
    )


def _correlation_summary(transfer: pd.DataFrame) -> dict[str, Any]:
    pnl_proxy = transfer["proxy_pnl_delta_c_minus_a"]
    engine_return = transfer["engine_return_delta_c_minus_a"]
    dd_proxy = transfer["proxy_drawdown_delta_c_minus_a"]
    engine_dd = transfer["engine_drawdown_delta_c_minus_a"]
    return {
        "months": len(transfer),
        "pnl_proxy_vs_engine_return_pearson": float(pnl_proxy.corr(engine_return, method="pearson")),
        "pnl_proxy_vs_engine_return_spearman": float(pnl_proxy.corr(engine_return, method="spearman")),
        "pnl_proxy_engine_sign_agreement": float((np.sign(pnl_proxy) == np.sign(engine_return)).mean()),
        "proxy_pnl_positive_engine_return_negative_months": int(((pnl_proxy > 0) & (engine_return < 0)).sum()),
        "drawdown_proxy_vs_engine_drawdown_pearson": float(dd_proxy.corr(engine_dd, method="pearson")),
        "drawdown_proxy_vs_engine_drawdown_spearman": float(dd_proxy.corr(engine_dd, method="spearman")),
        "drawdown_proxy_engine_sign_agreement": float((np.sign(dd_proxy) == np.sign(engine_dd)).mean()),
    }


def _render_report(summary: dict[str, Any]) -> str:
    transfer = summary["proxy_engine_transfer"]
    baseline = summary["formal_proxy_baseline"]
    lines = [
        "# Stage008 Stage007失败归因",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- 首个逐日净利润分叉：`{summary['path']['first_daily_pnl_divergence']}`",
        f"- A最大回撤：`{summary['drawdown']['A1']['max_drawdown']:.4%}`；"
        f"C最大回撤：`{summary['drawdown']['C']['max_drawdown']:.4%}`。",
        f"- A/C公共交易：`{summary['trade_overlap']['common_trades']}`，"
        f"占A的`{summary['trade_overlap']['common_share_of_a']:.2%}`。",
        f"- Stage006代理A与正式A完全同池仅`{baseline['exact_months']}/{baseline['months']}`个月，"
        f"月均换出`{baseline['mean_swap_count']:.4f}`个品种。",
        "",
        "## 代理到真引擎",
        "",
        f"- 净利润代理与真引擎60日收益差：Pearson `{transfer['pnl_proxy_vs_engine_return_pearson']:.4f}`，"
        f"Spearman `{transfer['pnl_proxy_vs_engine_return_spearman']:.4f}`，"
        f"符号一致率 `{transfer['pnl_proxy_engine_sign_agreement']:.2%}`。",
        f"- 代理显示C净利润更好、但真引擎收益更差：`{transfer['proxy_pnl_positive_engine_return_negative_months']}`个月。",
        f"- 回撤代理与真引擎60日回撤差：Spearman "
        f"`{transfer['drawdown_proxy_vs_engine_drawdown_spearman']:.4f}`，"
        f"符号一致率 `{transfer['drawdown_proxy_engine_sign_agreement']:.2%}`。",
        "",
        "## 边界",
        "",
        "- 本阶段没有训练模型或运行新回测，只消费冻结产物。",
        "- 归因不能恢复Stage007候选资格，也不能作为调参依据。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    tracked = {
        "stage006_monthly": STAGE006_MONTHLY,
        "stage006_summary": STAGE006_SUMMARY,
        "stage006_predictions": STAGE006_PREDICTIONS,
        "formal_eligibility": FORMAL_ELIGIBILITY,
        "stage007_decision": STAGE007_DECISION,
        "stage007_curve": STAGE007_CURVE,
        "stage007_trades": STAGE007_TRADES,
        "stage007_membership": STAGE007_MEMBERSHIP,
        "preregistration": PREREGISTRATION,
        "runner": Path(__file__).resolve(),
    }
    before = {name: _identity(path) for name, path in tracked.items()}
    decision = json.loads(STAGE007_DECISION.read_text())
    if decision.get("decision") != "stage007_fullperiod_fail_stop_xgboost_c3":
        raise RuntimeError("stage007_decision_not_frozen_failure")

    curves = pd.read_csv(STAGE007_CURVE)
    curves = curves[curves["experiment_arm"].isin(["A1", "C"])].copy()
    curves["date"] = pd.to_datetime(curves["date"]).dt.normalize()
    a_curve = curves[curves["experiment_arm"].eq("A1")].sort_values("date").reset_index(drop=True)
    c_curve = curves[curves["experiment_arm"].eq("C")].sort_values("date").reset_index(drop=True)
    if not a_curve["date"].equals(c_curve["date"]):
        raise RuntimeError("stage007_attribution_curve_dates_differ")
    daily_delta = c_curve["net_pnl"].to_numpy(dtype="float64") - a_curve["net_pnl"].to_numpy(dtype="float64")
    differing = np.flatnonzero(np.abs(daily_delta) > 1e-12)
    first_daily_divergence = (
        a_curve.loc[int(differing[0]), "date"].date().isoformat() if len(differing) else None
    )
    monthly = _period_metrics(curves, "M")
    yearly = _period_metrics(curves, "Y")
    worst_months = monthly.sort_values("net_pnl_delta_c_minus_a").head(12).copy()
    total_delta = float(daily_delta.sum())
    worst5_delta = float(monthly.nsmallest(5, "net_pnl_delta_c_minus_a")["net_pnl_delta_c_minus_a"].sum())

    trades = pd.read_csv(STAGE007_TRADES)
    a_trades = trades[trades["experiment_arm"].eq("A1")].copy()
    c_trades = trades[trades["experiment_arm"].eq("C")].copy()
    overlap = trade_multiset_overlap(a_trades, c_trades)
    overlap["first_trade_divergence_date"] = _first_trade_divergence(a_trades, c_trades)
    trades["product_vt_symbol"] = trades["vt_symbol"].map(contract_to_product)
    product_counts = (
        trades[trades["experiment_arm"].isin(["A1", "C"])]
        .groupby(["product_vt_symbol", "experiment_arm", "direction", "offset"], as_index=False)
        .size()
        .rename(columns={"size": "trade_count"})
    )

    stage006_monthly = pd.read_csv(STAGE006_MONTHLY)
    eval_dates = pd.DatetimeIndex(
        sorted(pd.to_datetime(stage006_monthly["eval_date"]).dt.normalize().unique())
    )
    account_paths = future_account_paths(curves, eval_dates, horizon=HORIZON)
    membership = pd.read_csv(STAGE007_MEMBERSHIP)
    transfer = _transfer_table(stage006_monthly, account_paths, membership)
    correlations = _correlation_summary(transfer)
    drawdowns = {"A1": drawdown_episode(a_curve), "C": drawdown_episode(c_curve)}
    formal_proxy = formal_proxy_membership_audit(
        pd.read_csv(FORMAL_ELIGIBILITY),
        pd.read_csv(STAGE006_PREDICTIONS),
    )

    after = {name: _identity(path) for name, path in tracked.items()}
    if before != after:
        raise RuntimeError("stage008_input_changed_during_attribution")
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": "stage008_proxy_to_executable_account_path_mismatch",
        "stage007_decision": decision["decision"],
        "path": {
            "first_daily_pnl_divergence": first_daily_divergence,
            "total_net_pnl_delta_c_minus_a": total_delta,
            "worst_5_month_delta_sum": worst5_delta,
            "worst_5_month_share_of_total_shortfall": worst5_delta / total_delta
            if total_delta
            else None,
        },
        "drawdown": drawdowns,
        "trade_overlap": overlap,
        "proxy_engine_transfer": correlations,
        "formal_proxy_baseline": {
            "months": len(formal_proxy),
            "exact_months": int(formal_proxy["formal_equals_proxy_a"].sum()),
            "changed_months": int((~formal_proxy["formal_equals_proxy_a"]).sum()),
            "mean_swap_count": float(formal_proxy["formal_vs_proxy_a_swap_count"].mean()),
            "median_swap_count": float(formal_proxy["formal_vs_proxy_a_swap_count"].median()),
            "maximum_swap_count": int(formal_proxy["formal_vs_proxy_a_swap_count"].max()),
        },
        "source_unchanged": True,
        "identities": before,
        "safety": {
            "strategy_backtest_ran": False,
            "model_trained": False,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
        },
    }
    monthly.to_csv(OUT / "monthly_account_path.csv", index=False)
    yearly.to_csv(OUT / "yearly_account_path.csv", index=False)
    worst_months.to_csv(OUT / "worst_months.csv", index=False)
    account_paths.to_csv(OUT / "future_account_paths.csv", index=False)
    transfer.to_csv(OUT / "proxy_engine_transfer.csv", index=False)
    formal_proxy.to_csv(OUT / "formal_proxy_membership_audit.csv", index=False)
    product_counts.to_csv(OUT / "trade_product_counts.csv", index=False)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(_render_report(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
