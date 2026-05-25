from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage297_stage78_1_risk_cluster_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage297_stage78_1_risk_cluster_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"

DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily.csv"
POSITION_CHANGES_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_position_changes_2020_2026_04.csv"


PRODUCT_BUCKETS: dict[str, dict[str, str]] = {
    "AP.CZCE": {"macro_cluster": "农业软商品", "industry_cluster": "果品"},
    "CF.CZCE": {"macro_cluster": "农业软商品", "industry_cluster": "棉花"},
    "OI.CZCE": {"macro_cluster": "农业软商品", "industry_cluster": "油脂油料"},
    "lc.GFEX": {"macro_cluster": "畜牧养殖", "industry_cluster": "蛋鸡"},
    "lh.DCE": {"macro_cluster": "畜牧养殖", "industry_cluster": "生猪"},
    "au.SHFE": {"macro_cluster": "贵金属", "industry_cluster": "黄金"},
    "cu.SHFE": {"macro_cluster": "有色工业", "industry_cluster": "铜"},
    "si.GFEX": {"macro_cluster": "有色工业", "industry_cluster": "工业硅"},
    "rb.SHFE": {"macro_cluster": "黑色建材", "industry_cluster": "钢材"},
    "hc.SHFE": {"macro_cluster": "黑色建材", "industry_cluster": "钢材"},
    "jm.DCE": {"macro_cluster": "黑色建材", "industry_cluster": "煤焦"},
    "SM.CZCE": {"macro_cluster": "黑色建材", "industry_cluster": "铁合金"},
    "FG.CZCE": {"macro_cluster": "黑色建材", "industry_cluster": "玻璃"},
    "SA.CZCE": {"macro_cluster": "黑色建材", "industry_cluster": "纯碱"},
    "SH.CZCE": {"macro_cluster": "黑色建材", "industry_cluster": "烧碱"},
    "MA.CZCE": {"macro_cluster": "能化工业", "industry_cluster": "甲醇"},
    "fu.SHFE": {"macro_cluster": "能化工业", "industry_cluster": "燃油"},
    "ru.SHFE": {"macro_cluster": "能化工业", "industry_cluster": "橡胶"},
    "sp.SHFE": {"macro_cluster": "能化工业", "industry_cluster": "纸浆"},
}


def _product_from_vt_symbol(vt_symbol: str) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = re.sub(r"\d+", "", symbol)
    return f"{product}.{exchange}"


def _max_drawdown_window(daily_df: pd.DataFrame) -> dict[str, Any]:
    trough = daily_df.loc[daily_df["ddpercent"].idxmin()]
    peak_balance = float(trough["highlevel"])
    peak_candidates = daily_df[
        (daily_df["date"] <= trough["date"]) & (daily_df["balance"].round(6) == round(peak_balance, 6))
    ]
    peak = peak_candidates.tail(1).iloc[0]
    recovery = daily_df[(daily_df["date"] > trough["date"]) & (daily_df["balance"] >= peak_balance)].head(1)
    return {
        "peak_date": peak["date"],
        "peak_balance": float(peak["balance"]),
        "trough_date": trough["date"],
        "trough_balance": float(trough["balance"]),
        "max_drawdown": float(trough["drawdown"]),
        "max_dd_percent": float(trough["ddpercent"]),
        "recovery_date": recovery.iloc[0]["date"] if not recovery.empty else pd.NaT,
        "recovery_balance": float(recovery.iloc[0]["balance"]) if not recovery.empty else None,
    }


def _prepare_positions(position_df: pd.DataFrame) -> pd.DataFrame:
    df = position_df.copy()
    df["product_vt_symbol"] = df["vt_symbol"].map(_product_from_vt_symbol)
    df["macro_cluster"] = df["product_vt_symbol"].map(
        lambda p: PRODUCT_BUCKETS.get(str(p), {}).get("macro_cluster", "未分类")
    )
    df["industry_cluster"] = df["product_vt_symbol"].map(
        lambda p: PRODUCT_BUCKETS.get(str(p), {}).get("industry_cluster", "未分类")
    )
    df["active_marker"] = (
        df["start_pos"].abs() + df["end_pos"].abs() + df["pos_change"].abs() + df["trade_count"].abs()
    )
    return df


def _summarize(
    position_df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    group_cols: list[str],
    window_name: str,
) -> pd.DataFrame:
    window = position_df[(position_df["date"] > start) & (position_df["date"] <= end)].copy()
    grouped = (
        window.groupby(group_cols, as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            turnover=("turnover", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("active_marker", lambda s: int((s > 0).sum())),
            max_abs_end_pos=("end_pos", lambda s: float(s.abs().max())),
        )
        .sort_values("net_pnl")
        .reset_index(drop=True)
    )
    grouped.insert(0, "window", window_name)
    total_loss = abs(float(grouped[grouped["net_pnl"] < 0]["net_pnl"].sum()))
    total_abs = float(grouped["net_pnl"].abs().sum())
    grouped["loss_share_pct"] = grouped["net_pnl"].apply(
        lambda x: abs(min(0.0, float(x))) / total_loss * 100.0 if total_loss > 0 else 0.0
    )
    grouped["abs_share_pct"] = grouped["net_pnl"].abs().apply(
        lambda x: float(x) / total_abs * 100.0 if total_abs > 0 else 0.0
    )
    return grouped


def _merge_window_summaries(full: pd.DataFrame, drawdown: pd.DataFrame, recovery: pd.DataFrame, key: str) -> pd.DataFrame:
    cols = [key, "net_pnl", "loss_share_pct", "trade_count", "active_days"]
    merged = full[cols].rename(
        columns={
            "net_pnl": "full_net_pnl",
            "loss_share_pct": "full_loss_share_pct",
            "trade_count": "full_trade_count",
            "active_days": "full_active_days",
        }
    )
    merged = merged.merge(
        drawdown[cols].rename(
            columns={
                "net_pnl": "drawdown_net_pnl",
                "loss_share_pct": "drawdown_loss_share_pct",
                "trade_count": "drawdown_trade_count",
                "active_days": "drawdown_active_days",
            }
        ),
        on=key,
        how="outer",
    )
    merged = merged.merge(
        recovery[cols].rename(
            columns={
                "net_pnl": "recovery_net_pnl",
                "loss_share_pct": "recovery_loss_share_pct",
                "trade_count": "recovery_trade_count",
                "active_days": "recovery_active_days",
            }
        ),
        on=key,
        how="outer",
    )
    for col in merged.columns:
        if col != key:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
    merged["drawdown_loss_to_full_profit_pct"] = merged.apply(
        lambda row: abs(min(0.0, row["drawdown_net_pnl"])) / row["full_net_pnl"] * 100.0
        if row["full_net_pnl"] > 0
        else float("nan"),
        axis=1,
    )
    return merged.sort_values("drawdown_net_pnl").reset_index(drop=True)


def _build_report(
    window: dict[str, Any],
    macro_merged: pd.DataFrame,
    industry_merged: pd.DataFrame,
    product_merged: pd.DataFrame,
) -> str:
    peak_date = pd.Timestamp(window["peak_date"]).date().isoformat()
    trough_date = pd.Timestamp(window["trough_date"]).date().isoformat()
    recovery_date = pd.Timestamp(window["recovery_date"]).date().isoformat() if pd.notna(window["recovery_date"]) else "-"
    top_macro = macro_merged.head(10)
    top_industry = industry_merged.head(15)
    top_product = product_merged.head(20)
    lines = [
        "# Stage297 第78-1产业风险簇归因",
        "",
        "## 目的",
        "",
        "- 本阶段只做归因，不修改策略参数。",
        "- 目标是判断最大回撤是否来自可泛化的产业/宏观风险簇集中，而不是事后单品种黑名单。",
        "",
        "## 最大回撤窗口",
        "",
        f"- 高点：`{peak_date}`，权益`{window['peak_balance']:,.0f}`",
        f"- 低点：`{trough_date}`，权益`{window['trough_balance']:,.0f}`",
        f"- 最大回撤：`{window['max_dd_percent']:.4f}%`",
        f"- 恢复高点：`{recovery_date}`",
        "",
        "## 宏观风险簇归因",
        "",
        top_macro.to_markdown(index=False),
        "",
        "## 产业风险簇归因",
        "",
        top_industry.to_markdown(index=False),
        "",
        "## 品种归因",
        "",
        top_product.to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
        "- 最大回撤确实呈现风险簇集中，但还不能直接等价为删品种或拉低某几个品种仓位。",
        "- 下一步如果要做候选，应测试通用的风险簇暴露上限或簇内风险预算，而不是按`fu/jm/sp/MA`逐个打补丁。",
        "- 如果簇上限导致长期收益主要来源被截断，则说明第78-1的收益-回撤前沿本身较硬，不能为了30%目标强行牺牲复利。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_df = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    position_df = _prepare_positions(pd.read_csv(POSITION_CHANGES_PATH, parse_dates=["date"]))
    window = _max_drawdown_window(daily_df)
    full_start = daily_df["date"].min() - pd.Timedelta(days=1)
    full_end = daily_df["date"].max()
    peak = pd.Timestamp(window["peak_date"])
    trough = pd.Timestamp(window["trough_date"])
    recovery = pd.Timestamp(window["recovery_date"]) if pd.notna(window["recovery_date"]) else full_end

    macro_full = _summarize(position_df, full_start, full_end, ["macro_cluster"], "全样本")
    macro_dd = _summarize(position_df, peak, trough, ["macro_cluster"], "最大回撤期")
    macro_rec = _summarize(position_df, trough, recovery, ["macro_cluster"], "恢复期")
    industry_full = _summarize(position_df, full_start, full_end, ["industry_cluster"], "全样本")
    industry_dd = _summarize(position_df, peak, trough, ["industry_cluster"], "最大回撤期")
    industry_rec = _summarize(position_df, trough, recovery, ["industry_cluster"], "恢复期")
    product_full = _summarize(position_df, full_start, full_end, ["product_vt_symbol"], "全样本")
    product_dd = _summarize(position_df, peak, trough, ["product_vt_symbol"], "最大回撤期")
    product_rec = _summarize(position_df, trough, recovery, ["product_vt_symbol"], "恢复期")

    macro_merged = _merge_window_summaries(macro_full, macro_dd, macro_rec, "macro_cluster")
    industry_merged = _merge_window_summaries(industry_full, industry_dd, industry_rec, "industry_cluster")
    product_merged = _merge_window_summaries(product_full, product_dd, product_rec, "product_vt_symbol")

    paths = {
        "macro": OUTPUT_DIR / f"{OUTPUT_PREFIX}_macro_{MODEL_TAG}.csv",
        "industry": OUTPUT_DIR / f"{OUTPUT_PREFIX}_industry_{MODEL_TAG}.csv",
        "product": OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }
    macro_merged.to_csv(paths["macro"], index=False, encoding="utf-8-sig")
    industry_merged.to_csv(paths["industry"], index=False, encoding="utf-8-sig")
    product_merged.to_csv(paths["product"], index=False, encoding="utf-8-sig")
    paths["report"].write_text(_build_report(window, macro_merged, industry_merged, product_merged), encoding="utf-8")

    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "window": {
            key: (pd.Timestamp(value).isoformat() if isinstance(value, pd.Timestamp) else value)
            for key, value in window.items()
        },
        "top_macro_drawdown": macro_merged.head(5).to_dict("records"),
        "top_industry_drawdown": industry_merged.head(8).to_dict("records"),
        "top_product_drawdown": product_merged.head(10).to_dict("records"),
        "next_step": "如果继续，优先测试通用风险簇暴露上限，而不是单品种黑名单。",
        "paths": {key: str(path.resolve()) for key, path in paths.items()},
    }
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
