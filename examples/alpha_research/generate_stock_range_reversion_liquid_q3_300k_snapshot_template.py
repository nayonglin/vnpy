from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import write_json
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_snapshot_template_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_snapshot_template_v1"

LIVE_TARGET_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_live_target_builder_2018_2026"
).expanduser().resolve()
LIVE_TARGET_PREFIX: str = "stock_range_reversion_liquid_q3_300k_live_target_builder_v1"

SNAPSHOT_INPUT_PATH: str = (
    os.getenv("SNAPSHOT_INPUT_PATH", "").strip() or os.getenv("ORDER_RECALC_PRICE_SNAPSHOT", "").strip()
)

PRICE_COLUMNS: tuple[str, ...] = ("price", "last_price", "trade_open", "open", "reference_price", "trade_close", "close")
POSITION_SHARE_COLUMNS: tuple[str, ...] = ("broker_position_shares", "current_shares", "position_shares")
BROKER_CASH_COLUMNS: tuple[str, ...] = ("broker_cash_cny", "cash_available_cny", "available_cash_cny")
BOOL_COLUMNS: tuple[str, ...] = (
    "is_suspended",
    "is_st",
    "is_index_component",
    "eligible_research_row",
    "is_oneword_limit_up",
    "is_oneword_limit_down",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect SetHoldings calculates quantity from current price and fees",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/position-sizing",
    ),
    (
        "QuantConnect ExecutionModel receives PortfolioTarget objects and executes them",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/execution/key-concepts",
    ),
    (
        "OpenAlgo supports basket orders, smart orders and position sizing",
        "https://github.com/marketcalls/openalgo",
    ),
    (
        "SSE trading mechanism: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8}).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:
        return default
    return result


def to_int(value: Any, default: int = 0) -> int:
    try:
        result = int(float(value))
    except (TypeError, ValueError):
        return default
    return result


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value == value:
        if value in (0, 1):
            return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "是", "是的"}:
        return True
    if text in {"0", "false", "no", "n", "否", "不是"}:
        return False
    return None


def first_existing_column(frame: pl.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in frame.columns:
            return column
    return ""


def add_check(
    rows: list[dict[str, Any]],
    checkpoint: str,
    status: str,
    value: Any,
    expected: Any,
    severity: str,
    note: str,
) -> None:
    rows.append(
        {
            "checkpoint": checkpoint,
            "status": status,
            "value": "" if value is None else str(value),
            "expected": "" if expected is None else str(expected),
            "severity": severity,
            "note": note,
        }
    )


def build_universe(live_targets: pl.DataFrame, positions: pl.DataFrame, target_date: date) -> pl.DataFrame:
    target_by_symbol = {row["symbol"]: row for row in live_targets.iter_rows(named=True)}
    position_by_symbol = {row["symbol"]: row for row in positions.iter_rows(named=True)} if not positions.is_empty() else {}
    rows: list[dict[str, Any]] = []
    for symbol in sorted(set(target_by_symbol) | set(position_by_symbol)):
        target = target_by_symbol.get(symbol, {})
        position = position_by_symbol.get(symbol, {})
        in_target = bool(target)
        in_position = bool(position)
        if in_target and in_position:
            reason = "live_target_and_current_position"
        elif in_target:
            reason = "live_target"
        else:
            reason = "current_position_exit_reconciliation"
        target_shares = to_int(target.get("sidecar_target_shares"))
        position_shares = to_int(position.get("current_shares"))
        rows.append(
            {
                "target_date": target.get("target_date") or target_date,
                "symbol": symbol,
                "code_name": target.get("code_name") or position.get("code_name") or "",
                "industry": target.get("industry") or position.get("industry") or "",
                "reference_price_hint": to_float(target.get("reference_price"))
                or to_float(position.get("last_trade_open")),
                "reference_price_source_hint": target.get("reference_price_source") or "position_last_trade_open_fallback",
                "live_target_shares_hint": target_shares,
                "live_target_amount_hint_cny": to_float(target.get("sidecar_target_amount_cny")),
                "raw_target_weight_hint": to_float(target.get("raw_target_weight")),
                "repository_position_shares_hint": position_shares,
                "repository_last_trade_open_hint": to_float(position.get("last_trade_open")),
                "needs_adv20_cap_hint": bool(in_target and target_shares > position_shares),
                "latest_known_component_hint": target.get("latest_known_component", False),
                "latest_known_research_eligible_hint": target.get("latest_known_research_eligible", True),
                "latest_known_st_hint": target.get("latest_known_st", False),
                "latest_known_suspended_hint": target.get("latest_known_suspended", False),
                "latest_known_oneword_limit_up_hint": target.get("latest_known_oneword_limit_up", False),
                "latest_known_oneword_limit_down_hint": target.get("latest_known_oneword_limit_down", False),
                "adv20_turnover_hint": to_float(target.get("adv20_turnover")),
                "required_for_order_recalc": True,
                "required_reason": reason,
            }
        )
    return pl.DataFrame(rows)


def build_snapshot_template(universe: pl.DataFrame, fill_latest_known: bool) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(universe.iter_rows(named=True)):
        price = row["reference_price_hint"] if fill_latest_known else None
        rows.append(
            {
                "snapshot_date": row["target_date"],
                "symbol": row["symbol"],
                "code_name": row["code_name"],
                "industry": row["industry"],
                "price": price,
                "price_source": "latest_known_example_not_tradeable" if fill_latest_known else "",
                "is_suspended": row["latest_known_suspended_hint"] if fill_latest_known else "",
                "is_st": row["latest_known_st_hint"] if fill_latest_known else "",
                "is_index_component": row["latest_known_component_hint"] if fill_latest_known else "",
                "eligible_research_row": row["latest_known_research_eligible_hint"] if fill_latest_known else "",
                "is_oneword_limit_up": row["latest_known_oneword_limit_up_hint"] if fill_latest_known else "",
                "is_oneword_limit_down": row["latest_known_oneword_limit_down_hint"] if fill_latest_known else "",
                "adv20_turnover": row["adv20_turnover_hint"] if fill_latest_known else "",
                "broker_position_shares": row["repository_position_shares_hint"] if fill_latest_known else "",
                "broker_cash_cny": "" if index else "",
                "reference_price_hint": row["reference_price_hint"],
                "reference_price_source_hint": row["reference_price_source_hint"],
                "live_target_shares_hint": row["live_target_shares_hint"],
                "live_target_amount_hint_cny": row["live_target_amount_hint_cny"],
                "raw_target_weight_hint": row["raw_target_weight_hint"],
                "repository_position_shares_hint": row["repository_position_shares_hint"],
                "repository_last_trade_open_hint": row["repository_last_trade_open_hint"],
                "needs_adv20_cap_hint": row["needs_adv20_cap_hint"],
                "required_for_order_recalc": row["required_for_order_recalc"],
                "required_reason": row["required_reason"],
                "notes": "示例仅沿用最新已知值，不能作为真实委托快照" if fill_latest_known else "",
            }
        )
    return pl.DataFrame(rows)


def build_schema() -> pl.DataFrame:
    rows = [
        ("snapshot_date", "yes", "YYYY-MM-DD", "应等于live建议执行日；本轮为目标日快照日期。"),
        ("symbol", "yes", "string", "6位A股代码；必须覆盖模板内全部symbol。"),
        ("code_name", "no", "string", "股票名称，便于人工复核。"),
        ("industry", "no", "string", "行业名称，便于人工复核。"),
        ("price", "yes", "float > 0", "目标日可用成交/盘口/开盘参考价；订单重算优先使用此列。"),
        ("price_source", "yes", "string", "价格来源，例如broker_quote/open/last_price/manual_snapshot。"),
        ("is_suspended", "yes", "bool", "目标日是否停牌；支持true/false/1/0/是/否。"),
        ("is_st", "yes", "bool", "目标日是否ST或风险警示。"),
        ("is_index_component", "yes", "bool", "目标日是否仍在策略指数成分或允许买入池。"),
        ("eligible_research_row", "yes", "bool", "目标日是否满足研究可交易过滤。"),
        ("is_oneword_limit_up", "yes", "bool", "目标日是否一字涨停；买入应阻断。"),
        ("is_oneword_limit_down", "yes", "bool", "目标日是否一字跌停；卖出应阻断。"),
        ("adv20_turnover", "recommended", "float >= 0", "20日成交额，用于ADV参与率上限；缺失会回退到live目标内最新已知值。"),
        ("broker_position_shares", "yes", "integer >= 0", "券商真实持仓股数；会覆盖仓库内paper持仓。"),
        ("broker_cash_cny", "yes", "float > 0", "券商可用现金；任意一行填入正数即可，也可用ORDER_RECALC_BROKER_CASH_CNY覆盖。"),
        ("reference_price_hint", "no", "float", "脚本填充的信号日参考价，仅用于人工对照。"),
        ("live_target_shares_hint", "no", "integer", "live目标股数提示，仅用于人工对照。"),
        ("repository_position_shares_hint", "no", "integer", "仓库paper持仓提示，仅用于人工对照。"),
        ("required_for_order_recalc", "no", "bool", "是否属于订单重算必需覆盖的symbol。"),
        ("required_reason", "no", "string", "该symbol进入模板的原因。"),
        ("notes", "no", "string", "人工备注。"),
    ]
    return pl.DataFrame(rows, schema=["column", "required", "type", "description"], orient="row")


def read_optional_input() -> tuple[pl.DataFrame, str, str]:
    if not SNAPSHOT_INPUT_PATH:
        return pl.DataFrame(), "", "missing"
    path = Path(SNAPSHOT_INPUT_PATH).expanduser().resolve()
    if not path.exists():
        return pl.DataFrame(), str(path), "missing_path"
    frame = read_csv_with_symbol(path)
    return frame, str(path), "loaded"


def validate_snapshot(input_frame: pl.DataFrame, input_source: str, input_state: str, universe: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    required_symbols = set(universe["symbol"].to_list())
    target_date = parse_date(universe["target_date"].max()) if not universe.is_empty() else None

    if input_state == "missing":
        add_check(
            rows,
            "snapshot_input_provided",
            "warn",
            "missing",
            "SNAPSHOT_INPUT_PATH or ORDER_RECALC_PRICE_SNAPSHOT",
            "warning",
            "已生成模板，但尚未提供目标日真实快照；订单重算仍只能走估算路径。",
        )
        return pl.DataFrame(rows)
    if input_state == "missing_path":
        add_check(
            rows,
            "snapshot_input_path_exists",
            "fail",
            input_source,
            "existing csv",
            "hard_blocker",
            "环境变量指向的快照文件不存在。",
        )
        return pl.DataFrame(rows)

    add_check(rows, "snapshot_input_provided", "pass", input_source, "existing csv", "info", "已读取外部快照。")

    missing_core = [column for column in ("snapshot_date", "symbol") if column not in input_frame.columns]
    add_check(
        rows,
        "required_core_columns_present",
        "pass" if not missing_core else "fail",
        ",".join(missing_core),
        "snapshot_date,symbol",
        "hard_blocker",
        "核心列缺失时无法校验目标日和证券覆盖。",
    )
    if missing_core:
        return pl.DataFrame(rows)

    price_column = first_existing_column(input_frame, PRICE_COLUMNS)
    position_column = first_existing_column(input_frame, POSITION_SHARE_COLUMNS)
    cash_column = first_existing_column(input_frame, BROKER_CASH_COLUMNS)
    add_check(
        rows,
        "price_column_present",
        "pass" if price_column else "fail",
        price_column or "missing",
        "one of " + ",".join(PRICE_COLUMNS),
        "hard_blocker",
        "订单重算必须有目标日价格列。",
    )
    add_check(
        rows,
        "position_column_present",
        "pass" if position_column else "fail",
        position_column or "missing",
        "one of " + ",".join(POSITION_SHARE_COLUMNS),
        "hard_blocker",
        "真实持仓列缺失时无法覆盖paper持仓。",
    )
    add_check(
        rows,
        "cash_column_present",
        "pass" if cash_column else "fail",
        cash_column or "missing",
        "one of " + ",".join(BROKER_CASH_COLUMNS),
        "hard_blocker",
        "真实可用现金缺失时无法判断买入预算。",
    )

    duplicate_count = input_frame.height - input_frame.select("symbol").unique().height
    add_check(
        rows,
        "no_duplicate_symbols",
        "pass" if duplicate_count == 0 else "fail",
        duplicate_count,
        0,
        "hard_blocker",
        "快照中同一symbol重复会导致价格/持仓覆盖不确定。",
    )
    snapshot_symbols = set(input_frame["symbol"].to_list())
    missing_symbols = sorted(required_symbols - snapshot_symbols)
    extra_symbols = sorted(snapshot_symbols - required_symbols)
    add_check(
        rows,
        "covers_required_universe",
        "pass" if not missing_symbols else "fail",
        len(missing_symbols),
        0,
        "hard_blocker",
        "快照必须覆盖所有live目标和当前持仓symbol。",
    )
    add_check(
        rows,
        "no_extra_symbols",
        "pass" if not extra_symbols else "warn",
        len(extra_symbols),
        0,
        "warning",
        "额外symbol不会用于订单重算，但应人工确认不是导出范围错误。",
    )

    rows_by_symbol = {row["symbol"]: row for row in input_frame.iter_rows(named=True)}
    required_rows = [rows_by_symbol[symbol] for symbol in sorted(required_symbols) if symbol in rows_by_symbol]

    date_mismatch = sum(1 for row in required_rows if parse_date(row.get("snapshot_date")) != target_date)
    add_check(
        rows,
        "snapshot_date_matches_live_target",
        "pass" if date_mismatch == 0 else "fail",
        date_mismatch,
        f"all {target_date}",
        "hard_blocker",
        "快照日期必须对应live建议执行日。",
    )

    if price_column:
        bad_prices = sum(1 for row in required_rows if to_float(row.get(price_column)) <= 0)
        add_check(
            rows,
            "required_prices_positive",
            "pass" if bad_prices == 0 else "fail",
            bad_prices,
            0,
            "hard_blocker",
            "所有必需symbol必须有正价格。",
        )
    if position_column:
        blank_positions = sum(1 for row in required_rows if is_blank(row.get(position_column)))
        negative_positions = sum(1 for row in required_rows if not is_blank(row.get(position_column)) and to_float(row.get(position_column)) < 0)
        fractional_positions = sum(
            1
            for row in required_rows
            if not is_blank(row.get(position_column)) and to_float(row.get(position_column)) % 1 != 0
        )
        non_lot_positions = sum(
            1
            for row in required_rows
            if to_int(row.get(position_column)) > 0 and to_int(row.get(position_column)) % 100 != 0
        )
        add_check(
            rows,
            "broker_positions_filled",
            "pass" if blank_positions == 0 else "fail",
            blank_positions,
            0,
            "hard_blocker",
            "真实持仓空白会被误解为0持仓，必须显式填写。",
        )
        add_check(
            rows,
            "broker_positions_non_negative",
            "pass" if negative_positions == 0 else "fail",
            negative_positions,
            0,
            "hard_blocker",
            "真实持仓不能为负数。",
        )
        add_check(
            rows,
            "broker_positions_integer",
            "pass" if fractional_positions == 0 else "warn",
            fractional_positions,
            0,
            "warning",
            "A股普通股票持仓通常应为整数股；碎股需人工确认券商规则。",
        )
        add_check(
            rows,
            "broker_positions_board_lot_or_zero",
            "pass" if non_lot_positions == 0 else "warn",
            non_lot_positions,
            0,
            "warning",
            "买入按100股整手，持仓非100整数倍可能来自零股/拆分/历史遗留，需人工确认。",
        )
    if cash_column:
        positive_cash_values = [
            to_float(row.get(cash_column))
            for row in input_frame.iter_rows(named=True)
            if to_float(row.get(cash_column)) > 0
        ]
        unique_positive_cash = sorted(set(round(value, 2) for value in positive_cash_values))
        add_check(
            rows,
            "broker_cash_positive",
            "pass" if positive_cash_values else "fail",
            len(positive_cash_values),
            ">=1 positive value",
            "hard_blocker",
            "至少一行需要填入券商可用现金正数。",
        )
        add_check(
            rows,
            "broker_cash_single_value",
            "pass" if len(unique_positive_cash) <= 1 else "warn",
            len(unique_positive_cash),
            "<=1 unique positive value",
            "warning",
            "同一快照中出现多个不同现金值时，订单重算会取第一条正数，需人工确认。",
        )

    for column in BOOL_COLUMNS:
        if column not in input_frame.columns:
            add_check(rows, f"{column}_present", "fail", "missing", "present", "hard_blocker", "目标日状态列缺失。")
            continue
        bad_values = sum(1 for row in required_rows if parse_bool(row.get(column)) is None)
        add_check(
            rows,
            f"{column}_parseable",
            "pass" if bad_values == 0 else "fail",
            bad_values,
            0,
            "hard_blocker",
            "目标日状态必须可解析为布尔值。",
        )

    if "adv20_turnover" not in input_frame.columns:
        add_check(
            rows,
            "adv20_turnover_present",
            "warn",
            "missing",
            "present preferred",
            "warning",
            "缺少ADV列时订单重算会回退到live目标内最新已知成交额。",
        )
    else:
        needs_adv = {row["symbol"] for row in universe.filter(pl.col("needs_adv20_cap_hint")).iter_rows(named=True)}
        bad_adv = sum(
            1
            for symbol in needs_adv
            if symbol in rows_by_symbol and to_float(rows_by_symbol[symbol].get("adv20_turnover")) <= 0
        )
        add_check(
            rows,
            "buy_relevant_adv20_positive",
            "pass" if bad_adv == 0 else "warn",
            bad_adv,
            0,
            "warning",
            "潜在买入标的最好有目标日或最新可用ADV，用于参与率上限。",
        )
    return pl.DataFrame(rows)


def summarize(summary_base: dict[str, Any], validation: pl.DataFrame, input_source: str, input_state: str) -> dict[str, Any]:
    pass_count = validation.filter(pl.col("status") == "pass").height if not validation.is_empty() else 0
    warn_count = validation.filter(pl.col("status") == "warn").height if not validation.is_empty() else 0
    fail_count = validation.filter(pl.col("status") == "fail").height if not validation.is_empty() else 0
    manual_count = validation.filter(pl.col("status") == "manual").height if not validation.is_empty() else 0
    if input_state == "missing":
        state = "template_generated_no_input"
    elif input_state == "missing_path":
        state = "snapshot_input_path_missing"
    elif fail_count > 0:
        state = "snapshot_invalid"
    elif warn_count > 0:
        state = "snapshot_valid_with_warnings"
    else:
        state = "snapshot_valid"
    return {
        **summary_base,
        "snapshot_template_state": state,
        "snapshot_input_path": input_source,
        "snapshot_input_state": input_state,
        "validation_pass_count": pass_count,
        "validation_warn_count": warn_count,
        "validation_fail_count": fail_count,
        "validation_manual_count": manual_count,
    }


def write_report(
    summary: dict[str, Any],
    validation: pl.DataFrame,
    schema: pl.DataFrame,
    template: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = validation.filter(pl.col("status") == "fail") if not validation.is_empty() else pl.DataFrame()
    warned = validation.filter(pl.col("status") == "warn") if not validation.is_empty() else pl.DataFrame()
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万目标日快照模板 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：执行层快照模板/校验；不新增信号、不调参数、不发真实委托。",
        f"- live信号日：`{summary['live_latest_signal_date']}`；建议执行日：`{summary['live_proposed_target_date']}`。",
        f"- 模板状态：`{summary['snapshot_template_state']}`。",
        "- A/B判断：执行层快照约束，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 成熟执行系统会把组合目标、当前价格、真实持仓、现金和预交易风控分层处理。",
        "- 订单数量应由目标权重与当前价格/费用/持仓共同换算，不能直接沿用信号日估算价格。",
        "- A股买入整手约束必须在订单重算前显式存在；快照模板的目的就是防止人工漏填关键执行状态。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            f"- 先填模板：`{paths['template']}`。",
            "- 至少填入目标日`price`、目标日状态列、真实`broker_position_shares`和任意一行正数`broker_cash_cny`。",
            "- 校验快照：设置`SNAPSHOT_INPUT_PATH=/path/to/snapshot.csv`后运行本脚本。",
            "- 订单重算：设置`ORDER_RECALC_PRICE_SNAPSHOT=/path/to/snapshot.csv`后运行order recalc脚本；现金也可用`ORDER_RECALC_BROKER_CASH_CNY`临时覆盖。",
            f"- 示例文件：`{paths['example']}`只沿用最新已知值，不能作为真实委托快照。",
            "",
            "## 核心摘要",
            "",
            f"- 模板行数`{summary['template_rows']}`，必需symbol `{summary['required_universe_count']}`，live目标`{summary['live_target_count']}`，仓库paper持仓`{summary['repository_position_count']}`。",
            f"- 校验通过`{summary['validation_pass_count']}`项，警告`{summary['validation_warn_count']}`项，失败`{summary['validation_fail_count']}`项。",
            f"- 快照输入：`{summary['snapshot_input_state']}` `{summary['snapshot_input_path']}`。",
            "",
            "## 校验结果",
            "",
            markdown_table(validation, ["checkpoint", "status", "value", "expected", "severity", "note"], max_rows=80)
            if not validation.is_empty()
            else "无数据",
            "",
            "## 失败项",
            "",
            markdown_table(failed, ["checkpoint", "status", "value", "expected", "severity", "note"], max_rows=80)
            if not failed.is_empty()
            else "无数据",
            "",
            "## 警告项",
            "",
            markdown_table(warned, ["checkpoint", "status", "value", "expected", "severity", "note"], max_rows=80)
            if not warned.is_empty()
            else "无数据",
            "",
            "## 字段说明",
            "",
            markdown_table(schema, ["column", "required", "type", "description"], max_rows=80),
            "",
            "## 模板预览",
            "",
            markdown_table(
                template,
                [
                    "snapshot_date",
                    "symbol",
                    "code_name",
                    "price",
                    "broker_position_shares",
                    "broker_cash_cny",
                    "reference_price_hint",
                    "live_target_shares_hint",
                    "repository_position_shares_hint",
                    "required_reason",
                ],
                max_rows=30,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本脚本只约束执行层输入真实性，没有增加收益筛选、状态阈值或选股参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：校验标准来自交易可执行性和数据完整性，不会按回测收益调整。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：目标日价格、现金和真实持仓是从paper走向可实盘paper的关键缺口。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：模板把人工/券商API需要补齐的字段固定下来，下一步order recalc可以直接消费同一份快照。",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    live_summary = load_json(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json")
    live_targets = read_csv_with_symbol(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_live_targets.csv")
    positions = read_csv_with_symbol(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_positions.csv")
    target_date = parse_date(live_summary.get("proposed_target_date")) or parse_date(live_targets["target_date"].max())
    if target_date is None:
        raise ValueError("Cannot infer live proposed target date.")

    universe = build_universe(live_targets, positions, target_date)
    template = build_snapshot_template(universe, fill_latest_known=False)
    example = build_snapshot_template(universe, fill_latest_known=True)
    schema = build_schema()
    input_frame, input_source, input_state = read_optional_input()
    validation = validate_snapshot(input_frame, input_source, input_state, universe)

    summary_base = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "live_latest_signal_date": live_summary.get("latest_signal_date"),
        "live_proposed_target_date": live_summary.get("proposed_target_date"),
        "template_rows": template.height,
        "required_universe_count": universe.height,
        "live_target_count": live_targets.height,
        "repository_position_count": positions.height,
        "snapshot_template_path": str(OUTPUT_DIR / f"{PREFIX}_snapshot_template.csv"),
        "latest_known_example_path": str(OUTPUT_DIR / f"{PREFIX}_snapshot_latest_known_example.csv"),
        "schema_path": str(OUTPUT_DIR / f"{PREFIX}_schema.csv"),
        "research_sources": RESEARCH_SOURCES,
    }
    summary = summarize(summary_base, validation, input_source, input_state)

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "template": OUTPUT_DIR / f"{PREFIX}_snapshot_template.csv",
        "example": OUTPUT_DIR / f"{PREFIX}_snapshot_latest_known_example.csv",
        "schema": OUTPUT_DIR / f"{PREFIX}_schema.csv",
        "universe": OUTPUT_DIR / f"{PREFIX}_required_universe.csv",
        "validation": OUTPUT_DIR / f"{PREFIX}_validation.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    template.write_csv(paths["template"])
    example.write_csv(paths["example"])
    schema.write_csv(paths["schema"])
    universe.write_csv(paths["universe"])
    validation.write_csv(paths["validation"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "live_summary": str(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json"),
            "snapshot_input_path": SNAPSHOT_INPUT_PATH,
            "research_sources": RESEARCH_SOURCES,
            "note": "Snapshot template and validation only; no broker order is submitted.",
        },
    )
    report_path = write_report(summary, validation, schema, template, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
