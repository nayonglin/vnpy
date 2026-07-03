from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import signal
from typing import Any

import numpy as np
import pandas as pd

from stage079_member_rank_pit_coverage_audit import (
    FEATURE_MATRIX_PATH,
    LEFT_TAIL_END,
    LEFT_TAIL_START,
    MAX_MEMBER_RANK_AGE_DAYS,
    MEMBER_RANK_PATH,
    WINDOW_ENTRIES_PATH,
    _md_table,
    _read_csv,
    attach_member_rank_asof,
    normalize_member_rank_history,
    summarize_member_rank_coverage,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage080"
MODEL_TAG = "stage080_member_rank_2022_backfill_feasibility_v1"
STAGE_SLUG = "stage080_member_rank_2022_backfill_feasibility"
OUTPUT_PREFIX = "rebuilt_c9_stage080_member_rank_2022_backfill_feasibility"

BACKFILL_START = "2022-01-01"
BACKFILL_END = "2022-12-31"
FETCH_CHUNK_DAYS = 31
MIN_AFTER_LOSS_COVERAGE_PCT = 80.0

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

FETCH_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_manifest_{MODEL_TAG}.csv"
FETCHED_RAW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetched_raw_{MODEL_TAG}.csv"
COMBINED_RAW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_raw_{MODEL_TAG}.csv"
COMBINED_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_member_features_{MODEL_TAG}.csv"
BEFORE_JOINED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_before_joined_window_entries_{MODEL_TAG}.csv"
AFTER_JOINED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_after_joined_window_entries_{MODEL_TAG}.csv"
AFTER_JOINED_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_after_joined_feature_matrix_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DCE_PRODUCTS = {
    "A",
    "B",
    "BB",
    "C",
    "CS",
    "EB",
    "EG",
    "FB",
    "I",
    "J",
    "JD",
    "JM",
    "L",
    "LH",
    "M",
    "P",
    "PG",
    "PP",
    "RR",
    "V",
    "Y",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _date_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):08d}"
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return f"{int(value):08d}"
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return f"{int(float(text)):08d}"
    compact = re.sub(r"[^0-9]", "", text)
    if len(compact) == 8:
        return compact
    return text


def _product_code(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if "." in text:
        text = text.split(".", 1)[0]
    match = re.match(r"([A-Za-z]+)", text)
    return match.group(1).upper() if match else ""


def _exchange_suffix(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if "." not in text:
        return ""
    return text.rsplit(".", 1)[-1].upper()


def _entry_product_series(frame: pd.DataFrame) -> pd.Series:
    for column in ["product", "vt_symbol", "product_key", "symbol", "variety"]:
        if column in frame.columns:
            product = frame[column].map(_product_code)
            if product.ne("").any():
                return product
    return pd.Series("", index=frame.index)


def _entry_exchange_series(frame: pd.DataFrame) -> pd.Series:
    for column in ["product", "vt_symbol", "product_key"]:
        if column in frame.columns:
            exchange = frame[column].map(_exchange_suffix)
            if exchange.ne("").any():
                return exchange
    return pd.Series("", index=frame.index)


def extract_required_member_rank_products(
    window_entries: pd.DataFrame,
    *,
    start: str = BACKFILL_START,
    end: str = BACKFILL_END,
    exclude_dce: bool = True,
) -> list[str]:
    frame = window_entries.copy()
    frame["entry_date"] = pd.to_datetime(frame.get("entry_date"), errors="coerce").dt.normalize()
    frame["product_code"] = _entry_product_series(frame)
    frame["exchange"] = _entry_exchange_series(frame)
    in_period = frame["entry_date"].between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")
    required = frame.loc[in_period & frame["product_code"].ne(""), ["product_code", "exchange"]].copy()
    if exclude_dce:
        required = required[~required["exchange"].eq("DCE") & ~required["product_code"].isin(DCE_PRODUCTS)]
    return sorted(required["product_code"].dropna().unique().tolist())


def build_member_rank_fetch_windows(
    *,
    start: str = BACKFILL_START,
    end: str = BACKFILL_END,
    chunk_days: int = FETCH_CHUNK_DAYS,
) -> list[tuple[str, str]]:
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    current = pd.Timestamp(start).normalize()
    final = pd.Timestamp(end).normalize()
    windows: list[tuple[str, str]] = []
    while current <= final:
        chunk_end = min(current + pd.Timedelta(days=chunk_days - 1), final)
        windows.append((current.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        current = chunk_end + pd.Timedelta(days=1)
    return windows


def _normalize_raw_member_key_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ["date", "symbol", "variety"]:
        if column not in result.columns:
            result[column] = ""
    result["date"] = result["date"].map(_date_text)
    result["symbol"] = result["symbol"].map(lambda value: str(value).strip().upper() if pd.notna(value) else "")
    result["variety"] = result["variety"].map(_product_code)
    return result


def combine_member_rank_histories(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    existing_norm = _normalize_raw_member_key_columns(existing)
    fetched_norm = _normalize_raw_member_key_columns(fetched)
    combined = pd.concat([existing_norm, fetched_norm], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(subset=["date", "symbol", "variety"], keep="first")
    return combined.sort_values(["date", "symbol", "variety"]).reset_index(drop=True)


def _left_tail_coverage(joined_windows: pd.DataFrame) -> dict[str, float | int]:
    windows = joined_windows.copy()
    windows["entry_date"] = pd.to_datetime(windows.get("entry_date"), errors="coerce").dt.normalize()
    available = windows.get("member_rank_available", pd.Series(False, index=windows.index)).fillna(False).astype(bool)
    left_tail = windows["entry_date"].between(LEFT_TAIL_START, LEFT_TAIL_END, inclusive="both")
    loss_abs = pd.to_numeric(windows.get("stage071_base_loss_abs"), errors="coerce").fillna(0.0)
    entry_count = int(left_tail.sum())
    available_count = int((left_tail & available).sum())
    total_loss = float(loss_abs.loc[left_tail].sum())
    covered_loss = float(loss_abs.loc[left_tail & available].sum())
    return {
        "entry_count": entry_count,
        "available_count": available_count,
        "entry_coverage_pct": float(available_count / entry_count * 100.0) if entry_count else 0.0,
        "total_loss_abs": total_loss,
        "covered_loss_abs": covered_loss,
        "loss_coverage_pct": float(covered_loss / total_loss * 100.0) if total_loss else 0.0,
    }


def summarize_backfill_coverage_change(
    before_joined_windows: pd.DataFrame,
    after_joined_windows: pd.DataFrame,
    *,
    min_after_loss_coverage_pct: float = MIN_AFTER_LOSS_COVERAGE_PCT,
) -> dict[str, Any]:
    before = _left_tail_coverage(before_joined_windows)
    after = _left_tail_coverage(after_joined_windows)
    loss_gain = float(after["loss_coverage_pct"] - before["loss_coverage_pct"])
    entry_gain = float(after["entry_coverage_pct"] - before["entry_coverage_pct"])
    ready = after["loss_coverage_pct"] >= min_after_loss_coverage_pct and loss_gain > 0.0
    if ready:
        decision = "stage080_member_rank_backfill_coverage_ready_for_signal_audit"
    elif loss_gain > 0.0:
        decision = "stage080_member_rank_backfill_partial_coverage_not_enough"
    else:
        decision = "stage080_member_rank_backfill_no_coverage_gain"
    return {
        "decision": decision,
        "coverage_ready_for_signal_audit": bool(ready),
        "before_left_tail_entry_count": before["entry_count"],
        "before_left_tail_available_count": before["available_count"],
        "before_left_tail_entry_coverage_pct": before["entry_coverage_pct"],
        "before_left_tail_total_loss_abs": before["total_loss_abs"],
        "before_left_tail_covered_loss_abs": before["covered_loss_abs"],
        "before_left_tail_loss_coverage_pct": before["loss_coverage_pct"],
        "after_left_tail_entry_count": after["entry_count"],
        "after_left_tail_available_count": after["available_count"],
        "after_left_tail_entry_coverage_pct": after["entry_coverage_pct"],
        "after_left_tail_total_loss_abs": after["total_loss_abs"],
        "after_left_tail_covered_loss_abs": after["covered_loss_abs"],
        "after_left_tail_loss_coverage_pct": after["loss_coverage_pct"],
        "left_tail_entry_coverage_gain_pp": entry_gain,
        "left_tail_loss_coverage_gain_pp": loss_gain,
        "min_after_loss_coverage_pct": min_after_loss_coverage_pct,
    }


class _Timeout:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.previous_handler: Any = None

    def __enter__(self) -> None:
        if self.seconds <= 0:
            return
        self.previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.seconds <= 0:
            return
        signal.alarm(0)
        signal.signal(signal.SIGALRM, self.previous_handler)

    @staticmethod
    def _handle_timeout(signum: int, frame: Any) -> None:
        raise TimeoutError("akshare get_rank_sum_daily timed out")


def fetch_rank_sum_daily_akshare(
    *,
    start_day: str,
    end_day: str,
    vars_list: list[str],
    timeout_seconds: int = 180,
) -> pd.DataFrame:
    import akshare as ak

    with _Timeout(timeout_seconds):
        result = ak.get_rank_sum_daily(start_day=start_day, end_day=end_day, vars_list=vars_list)
    if result is None:
        return pd.DataFrame()
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)


def fetch_member_rank_backfill(
    *,
    products: list[str],
    fetch_windows: list[tuple[str, str]],
    timeout_seconds: int = 180,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    chunks: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, Any]] = []
    for start_day, end_day in fetch_windows:
        row: dict[str, Any] = {
            "start_day": start_day,
            "end_day": end_day,
            "products": ",".join(products),
            "status": "pending",
            "rows": 0,
            "error": "",
        }
        try:
            fetched = fetch_rank_sum_daily_akshare(
                start_day=start_day,
                end_day=end_day,
                vars_list=products,
                timeout_seconds=timeout_seconds,
            )
            row["status"] = "ok"
            row["rows"] = int(len(fetched))
            if not fetched.empty:
                chunks.append(fetched)
        except Exception as exc:  # noqa: BLE001 - stage record needs the source failure text.
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        manifest_rows.append(row)
    fetched_all = pd.concat(chunks, ignore_index=True, sort=False) if chunks else pd.DataFrame()
    manifest = pd.DataFrame(manifest_rows)
    return fetched_all, manifest


def _year_coverage_delta(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, data in [("before", before), ("after", after)]:
        frame = data.copy()
        frame["entry_date"] = pd.to_datetime(frame.get("entry_date"), errors="coerce").dt.normalize()
        frame["entry_year"] = frame["entry_date"].dt.year
        frame["member_rank_available"] = frame.get("member_rank_available", False)
        frame["member_rank_available"] = frame["member_rank_available"].fillna(False).astype(bool)
        for year, group in frame.groupby("entry_year", dropna=True):
            rows.append(
                {
                    "sample": label,
                    "entry_year": int(year),
                    "entry_count": int(len(group)),
                    "available_count": int(group["member_rank_available"].sum()),
                    "coverage_pct": float(group["member_rank_available"].sum() / len(group) * 100.0)
                    if len(group)
                    else 0.0,
                    "loss_abs": float(pd.to_numeric(group.get("stage071_base_loss_abs"), errors="coerce").fillna(0.0).sum()),
                    "covered_loss_abs": float(
                        pd.to_numeric(
                            group.loc[group["member_rank_available"], "stage071_base_loss_abs"],
                            errors="coerce",
                        )
                        .fillna(0.0)
                        .sum()
                    )
                    if "stage071_base_loss_abs" in group.columns
                    else 0.0,
                }
            )
    return pd.DataFrame(rows).sort_values(["entry_year", "sample"]).reset_index(drop=True)


def _excluded_dce_summary(window_entries: pd.DataFrame) -> dict[str, Any]:
    frame = window_entries.copy()
    frame["entry_date"] = pd.to_datetime(frame.get("entry_date"), errors="coerce").dt.normalize()
    frame["product_code"] = _entry_product_series(frame)
    frame["exchange"] = _entry_exchange_series(frame)
    frame["loss_abs"] = pd.to_numeric(frame.get("stage071_base_loss_abs"), errors="coerce").fillna(0.0)
    in_backfill = frame["entry_date"].between(pd.Timestamp(BACKFILL_START), pd.Timestamp(BACKFILL_END), inclusive="both")
    dce = frame.loc[in_backfill & (frame["exchange"].eq("DCE") | frame["product_code"].isin(DCE_PRODUCTS))]
    return {
        "excluded_dce_entry_count": int(len(dce)),
        "excluded_dce_loss_abs": float(dce["loss_abs"].sum()) if not dce.empty else 0.0,
        "excluded_dce_products": sorted(dce["product_code"].dropna().unique().tolist()) if not dce.empty else [],
    }


def _source_summary(existing_raw: pd.DataFrame, fetched_raw: pd.DataFrame, combined_raw: pd.DataFrame) -> dict[str, Any]:
    dates = combined_raw["date"].map(_date_text) if "date" in combined_raw.columns else pd.Series(dtype="object")
    return {
        "existing_raw_rows": int(len(existing_raw)),
        "fetched_raw_rows": int(len(fetched_raw)),
        "combined_raw_rows": int(len(combined_raw)),
        "combined_date_min": dates.min() if not dates.empty else None,
        "combined_date_max": dates.max() if not dates.empty else None,
        "combined_unique_dates": int(dates.nunique()) if not dates.empty else 0,
        "existing_source_path": str(MEMBER_RANK_PATH),
    }


def _write_report(decision: dict[str, Any], year_delta: pd.DataFrame, manifest: pd.DataFrame) -> None:
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage080 member rank 2022 backfill feasibility",
                "",
                f"- 决策：`{decision['decision']}`。",
                "- 类型：国内会员持仓/成交排名 2022 补数可行性审计；不写交易规则、不改线上、不改 AI 池。",
                f"- 补数区间：`{BACKFILL_START}` 到 `{BACKFILL_END}`；只抓非 DCE 左尾所需品种。",
                f"- 待补品种：`{', '.join(decision['required_products'])}`。",
                f"- DCE 暂排除：`{decision['excluded_dce_summary']['excluded_dce_products']}`，亏损覆盖缺口 `{decision['excluded_dce_summary']['excluded_dce_loss_abs']:.2f}`。",
                "",
                "## 覆盖变化",
                "",
                f"- 补数前左尾 entry 覆盖：`{decision['before_left_tail_available_count']}/{decision['before_left_tail_entry_count']}` = `{decision['before_left_tail_entry_coverage_pct']:.4f}%`。",
                f"- 补数后左尾 entry 覆盖：`{decision['after_left_tail_available_count']}/{decision['after_left_tail_entry_count']}` = `{decision['after_left_tail_entry_coverage_pct']:.4f}%`。",
                f"- 补数前左尾亏损金额覆盖：`{decision['before_left_tail_covered_loss_abs']:.2f}/{decision['before_left_tail_total_loss_abs']:.2f}` = `{decision['before_left_tail_loss_coverage_pct']:.4f}%`。",
                f"- 补数后左尾亏损金额覆盖：`{decision['after_left_tail_covered_loss_abs']:.2f}/{decision['after_left_tail_total_loss_abs']:.2f}` = `{decision['after_left_tail_loss_coverage_pct']:.4f}%`。",
                f"- 亏损覆盖提升：`{decision['left_tail_loss_coverage_gain_pp']:.4f}pp`。",
                "",
                "## 年度覆盖对比",
                "",
                _md_table(year_delta, max_rows=20),
                "",
                "## 抓取状态",
                "",
                _md_table(manifest, max_rows=40),
                "",
                "## 反思",
                "",
                "- 运行前过拟合反思：否；本阶段不是用坏窗口调参，而是验证 2022 PIT 原始输入能否补回。",
                "- 运行后过拟合反思：只有补数覆盖达标后进入下一阶段信号审计才合理；若直接按本阶段覆盖结果写规则，就是过拟合。",
                "- 运行前继续价值反思：有；Stage079 的缺口集中在 2022 左尾，且外部源显示 AKShare/交易所历史接口可能可补。",
                "- 运行后继续价值反思：取决于覆盖提升；覆盖达标则值得做信号方向审计，不达标则停止会员排名历史 selector。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_stage_record(decision: dict[str, Any], year_delta: pd.DataFrame, manifest: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage080_member_rank_2022_backfill_feasibility.md"
    stage_path.write_text(
        "\n".join(
            [
                "# Stage080 国内会员持仓排名 2022 补数可行性审计",
                "",
                f"- line_id：`{LINE_ID}`",
                "- 当前模式：day",
                f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
                "- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`",
                "- 阶段性质：只读外生源补数可行性与覆盖审计，不改线上、不改 AI 池、不接 CTP/SimNow。",
                "- 是否重要突破：否，除非后续信号审计证明有稳定 OOS 价值。",
                "- 是否触发A/B：否。",
                "",
                "## 外部调研与判断",
                "",
                "- 参考资料：AKShare 期货数据文档列出 `get_rank_sum_daily`、`get_rank_table_czce`、`get_shfe_rank_table`、`futures_dce_position_rank` 等接口；上期所、郑商所、大商所官网均有历史日排名/持仓数据入口。",
                "- 我的判断：会员排名数据有可能重建 2022 非 DCE 左尾输入，但 DCE 当前接口仍不稳定；因此本阶段只补非 DCE 覆盖，不写交易规则。",
                "",
                "## 本次变更",
                "",
                f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage080_member_rank_2022_backfill_feasibility.py`。",
                f"- 新增测试：`tests/test_rebuilt_c9_stage080_member_rank_backfill_feasibility.py`。",
                "- 修改脚本：无正式交易脚本修改。",
                "- 删除脚本：无。",
                f"- 新增参数：`BACKFILL_START={BACKFILL_START}`、`BACKFILL_END={BACKFILL_END}`、`FETCH_CHUNK_DAYS={FETCH_CHUNK_DAYS}`、`MIN_AFTER_LOSS_COVERAGE_PCT={MIN_AFTER_LOSS_COVERAGE_PCT}`。",
                "- 修改参数：无正式交易参数修改。",
                "- 删除参数：无。",
                "",
                "## 回测/归因参数",
                "",
                f"- 数据区间：会员排名既有源 `{decision['source_summary']['existing_source_path']}` + AKShare 非 DCE `{BACKFILL_START}` 到 `{BACKFILL_END}` 补数。",
                "- 账户规模：不适用，本阶段无资金曲线回测。",
                "- 成本口径：不适用，本阶段无交易回放。",
                f"- 样本过滤：Stage071 左尾窗口；会员排名 `T+1` 可见，最大旧值 `{MAX_MEMBER_RANK_AGE_DAYS}` 天；DCE 先排除。",
                "- 策略/归因口径：只比较补数前后 PIT 覆盖率和亏损金额覆盖率。",
                "",
                "## 结果",
                "",
                "- 期末权益：不适用。",
                "- 总收益：不适用。",
                "- 最大回撤：不适用。",
                "- Sharpe：不适用。",
                "- 总滑点：不适用。",
                "- 总交易次数：不适用。",
                "- 胜率：不适用。",
                f"- 决策：`{decision['decision']}`。",
                f"- 抓取行数：`{decision['source_summary']['fetched_raw_rows']}`。",
                f"- 合并后原始行数：`{decision['source_summary']['combined_raw_rows']}`。",
                f"- 补数前左尾亏损金额覆盖：`{decision['before_left_tail_loss_coverage_pct']:.4f}%`。",
                f"- 补数后左尾亏损金额覆盖：`{decision['after_left_tail_loss_coverage_pct']:.4f}%`。",
                f"- 覆盖提升：`{decision['left_tail_loss_coverage_gain_pp']:.4f}pp`。",
                "",
                "## 输出文件",
                "",
                f"- report：`{REPORT_PATH}`",
                f"- summary：`{DECISION_PATH}`",
                f"- fetched_raw：`{FETCHED_RAW_PATH}`",
                f"- combined_raw：`{COMBINED_RAW_PATH}`",
                f"- combined_features：`{COMBINED_FEATURES_PATH}`",
                f"- joined：`{BEFORE_JOINED_WINDOWS_PATH}`、`{AFTER_JOINED_WINDOWS_PATH}`、`{AFTER_JOINED_FEATURES_PATH}`",
                f"- fetch_manifest：`{FETCH_MANIFEST_PATH}`",
                "",
                "## 年度覆盖对比",
                "",
                _md_table(year_delta, max_rows=20),
                "",
                "## 抓取状态",
                "",
                _md_table(manifest, max_rows=40),
                "",
                "## 结论",
                "",
                f"- 本阶段结论：`{decision['decision']}`。",
                "- 是否进入下一步：只有 `coverage_ready_for_signal_audit=True` 时，才进入下一阶段信号方向/OOS 审计；本阶段不进入规则/proxy/真引擎。",
                "- 下一步：若覆盖达标，冻结补数源哈希并做会员排名特征方向审计；若不达标，关闭会员排名历史 selector。",
                "",
                "## 过拟合反思",
                "",
                "- 运行前判断：否；只补可见历史输入，不按坏窗口调规则。",
                "- 运行后判断：若后续只因 2022 左尾表现好而定制阈值，会过拟合；必须做跨年、跨品种、OOS 稳定性。",
                "- 原因：补数解决的是输入缺失，不自动证明信号有预测力。",
                "",
                "## 继续价值反思",
                "",
                "- 运行前判断：有；Stage079 已定位主要缺口在 2022。",
                "- 运行后判断：看覆盖结果决定；覆盖达标则有继续审计价值。",
                "- 原因：会员排名是外生 PIT 源，若能补齐左尾，比继续扫内部阈值更有研究价值。",
                "",
                "## 合入建议",
                "",
                "- 是否更新本线 `LINE.md`：是，记录 Stage080 覆盖变化和下一步边界。",
                "- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage080。",
                "- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 重要摘要，不改 `memory.md`。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_path


def run(*, timeout_seconds: int = 180) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    existing_raw = _read_csv(MEMBER_RANK_PATH)
    features = _read_csv(FEATURE_MATRIX_PATH)
    windows = _read_csv(WINDOW_ENTRIES_PATH)

    required_products = extract_required_member_rank_products(windows, exclude_dce=True)
    fetch_windows = build_member_rank_fetch_windows()
    fetched_raw, manifest = fetch_member_rank_backfill(
        products=required_products,
        fetch_windows=fetch_windows,
        timeout_seconds=timeout_seconds,
    )
    combined_raw = combine_member_rank_histories(existing_raw, fetched_raw)

    before_features = normalize_member_rank_history(existing_raw)
    combined_features = normalize_member_rank_history(combined_raw)
    before_joined_windows = attach_member_rank_asof(windows, before_features)
    after_joined_windows = attach_member_rank_asof(windows, combined_features)
    after_joined_features = attach_member_rank_asof(features, combined_features)

    decision = summarize_backfill_coverage_change(before_joined_windows, after_joined_windows)
    if fetched_raw.empty and manifest["status"].eq("error").any():
        decision["decision"] = "stage080_member_rank_backfill_fetch_failed_keep_stage079_boundary"
        decision["coverage_ready_for_signal_audit"] = False

    before_stage079 = summarize_member_rank_coverage(
        attach_member_rank_asof(features, before_features),
        before_joined_windows,
    )
    after_stage079 = summarize_member_rank_coverage(after_joined_features, after_joined_windows)
    decision.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "required_products": required_products,
            "fetch_window_count": len(fetch_windows),
            "fetch_ok_count": int(manifest["status"].eq("ok").sum()) if not manifest.empty else 0,
            "fetch_error_count": int(manifest["status"].eq("error").sum()) if not manifest.empty else 0,
            "excluded_dce_summary": _excluded_dce_summary(windows),
            "source_summary": _source_summary(existing_raw, fetched_raw, combined_raw),
            "before_stage079_summary": before_stage079,
            "after_stage079_summary": after_stage079,
            "external_research_sources": [
                "https://akshare.akfamily.xyz/data/futures/futures.html",
                "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=pm",
                "https://www.dce.com.cn/dce/channel/list/166.html",
                "https://www.czce.com.cn/cn/jysj/lshqxz/H077003019index_1.htm",
            ],
        }
    )

    year_delta = _year_coverage_delta(before_joined_windows, after_joined_windows)
    fetched_raw.to_csv(FETCHED_RAW_PATH, index=False, encoding="utf-8-sig")
    manifest.to_csv(FETCH_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    combined_raw.to_csv(COMBINED_RAW_PATH, index=False, encoding="utf-8-sig")
    combined_features.to_csv(COMBINED_FEATURES_PATH, index=False, encoding="utf-8-sig")
    before_joined_windows.to_csv(BEFORE_JOINED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    after_joined_windows.to_csv(AFTER_JOINED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    after_joined_features.to_csv(AFTER_JOINED_FEATURES_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, year_delta, manifest)
    stage_path = _write_stage_record(decision, year_delta, manifest)
    decision["stage_record_path"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
