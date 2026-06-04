from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import ssl
from typing import Any
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage647_ec_ine_second_slot_source_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage647_ec_ine_second_slot_source_probe"

STAGE633_PRODUCT_MAP = (
    OUTPUT_DIR / "qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv"
)

FETCH_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_ledger_{MODEL_TAG}.csv"
PRODUCT_EVIDENCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_evidence_{MODEL_TAG}.csv"
PEER_BOARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peer_board_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

STRICT_CORR_THRESHOLD = 0.15
WATCH_CORR_THRESHOLD = 0.20
REQUIRED_COLLECTION_PIT_DATES = 20
REQUIRED_EPISODES = 3

SOURCE_TARGETS = [
    {
        "source_name": "INE EC product page",
        "source_authority": "exchange_official",
        "source_class": "contract_underlying_index_contract_text",
        "url": "https://www.ine.cn/products/futures/index_f/ec_f/",
        "keywords": ["SCFIS", "集运指数", "欧线", "上海航运交易所"],
        "parse_role": "contract_context",
    },
    {
        "source_name": "INE EC English market page",
        "source_authority": "exchange_official",
        "source_class": "contract_underlying_index_context",
        "url": "https://www.ine.cn/eng/market/futures/index/ec/index.html",
        "keywords": ["SCFIS", "Shanghai Shipping Exchange", "Europe", "futures"],
        "parse_role": "contract_context",
    },
    {
        "source_name": "SSE SCFIS current index query",
        "source_authority": "index_publisher_official",
        "source_class": "official_underlying_index_current_value",
        "url": "https://www.sse.net.cn/index/singleIndex?indexType=scfis",
        "keywords": ["上海出口集装箱结算运价指数", "欧洲航线", "Europe", "本期"],
        "parse_role": "current_index_value",
    },
    {
        "source_name": "SSE SCFIS methodology intro",
        "source_authority": "index_publisher_official",
        "source_class": "official_underlying_index_methodology",
        "url": "https://www.sse.net.cn/indexIntro?indexName=scfis",
        "keywords": ["SCFIS", "编制规则", "欧洲航线", "样本公司"],
        "parse_role": "methodology_context",
    },
]

REFERENCES = [
    "INE SCFIS Europe product page: https://www.ine.cn/products/futures/index_f/ec_f/",
    "INE English EC page: https://www.ine.cn/eng/market/futures/index/ec/index.html",
    "Shanghai Shipping Exchange SCFIS current query: https://www.sse.net.cn/index/singleIndex?indexType=scfis",
    "Shanghai Shipping Exchange SCFIS methodology intro: https://www.sse.net.cn/indexIntro?indexName=scfis",
    "GitHub search found no reliable dedicated SCFIS Python project; use official pages with raw hash/PIT ledger instead.",
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _fetch_url(url: str, timeout: int = 18) -> tuple[int, str, bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 qmt-roll-stage647-source-probe/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310 - explicit public sources
        payload = response.read()
        status = int(getattr(response, "status", 0) or response.getcode())
        final_url = response.geturl()
    return status, final_url, payload, payload.decode("utf-8", errors="ignore")


def _text_from_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_scfis_europe(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scfis_date": "",
        "europe_value": np.nan,
        "europe_change_pct": np.nan,
        "uswc_value": np.nan,
        "uswc_change_pct": np.nan,
        "parse_ok": 0,
    }
    date_match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if date_match:
        result["scfis_date"] = date_match.group(1)
    europe = re.search(
        r"欧洲航线[^0-9A-Za-z]{0,30}(?:Europe)?[^0-9]{0,80}点\s*([0-9]+(?:\.[0-9]+)?)\s*([+-]?[0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.I,
    )
    uswc = re.search(
        r"美西航线[^0-9A-Za-z]{0,30}(?:USWC)?[^0-9]{0,80}点\s*([0-9]+(?:\.[0-9]+)?)\s*([+-]?[0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.I,
    )
    if europe:
        result["europe_value"] = float(europe.group(1))
        result["europe_change_pct"] = float(europe.group(2))
    if uswc:
        result["uswc_value"] = float(uswc.group(1))
        result["uswc_change_pct"] = float(uswc.group(2))
    result["parse_ok"] = int(bool(result["scfis_date"]) and pd.notna(result["europe_value"]))
    return result


def _fetch_sources(generated_at: datetime) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in SOURCE_TARGETS:
        try:
            status, final_url, payload, html = _fetch_url(target["url"])
            raw_sha256 = hashlib.sha256(payload).hexdigest()
            text = _text_from_html(html)
            keyword_hits = sum(1 for keyword in target["keywords"] if keyword.lower() in text.lower())
            parsed = _parse_scfis_europe(text) if target["parse_role"] == "current_index_value" else {}
            fetch_status = "ok" if status == 200 and len(payload) > 500 else "weak_payload"
            rows.append(
                {
                    "received_at_cst": _fmt_cst(generated_at),
                    "received_pit_date": generated_at.strftime("%Y-%m-%d"),
                    "source_name": target["source_name"],
                    "source_authority": target["source_authority"],
                    "source_class": target["source_class"],
                    "source_url": target["url"],
                    "final_url": final_url,
                    "http_status": status,
                    "fetch_status": fetch_status,
                    "response_bytes": len(payload),
                    "raw_sha256": raw_sha256,
                    "raw_sha256_present": int(bool(raw_sha256)),
                    "keyword_hit_count": keyword_hits,
                    "parse_role": target["parse_role"],
                    "parse_ok": int(parsed.get("parse_ok", 0)),
                    "scfis_date": parsed.get("scfis_date", ""),
                    "europe_value": parsed.get("europe_value", np.nan),
                    "europe_change_pct": parsed.get("europe_change_pct", np.nan),
                    "uswc_value": parsed.get("uswc_value", np.nan),
                    "uswc_change_pct": parsed.get("uswc_change_pct", np.nan),
                    "usable_for_forward_monitor": int(fetch_status == "ok" and bool(raw_sha256)),
                    "usable_for_history_selector": 0,
                    "selector_allowed_now": 0,
                    "paper_or_whitelist_allowed_now": 0,
                    "trading_whitelist_allowed_now": 0,
                    "fetch_error": "",
                }
            )
        except Exception as exc:  # noqa: BLE001 - retain exact blocker
            rows.append(
                {
                    "received_at_cst": _fmt_cst(generated_at),
                    "received_pit_date": generated_at.strftime("%Y-%m-%d"),
                    "source_name": target["source_name"],
                    "source_authority": target["source_authority"],
                    "source_class": target["source_class"],
                    "source_url": target["url"],
                    "final_url": "",
                    "http_status": 0,
                    "fetch_status": "error",
                    "response_bytes": 0,
                    "raw_sha256": "",
                    "raw_sha256_present": 0,
                    "keyword_hit_count": 0,
                    "parse_role": target["parse_role"],
                    "parse_ok": 0,
                    "scfis_date": "",
                    "europe_value": np.nan,
                    "europe_change_pct": np.nan,
                    "uswc_value": np.nan,
                    "uswc_change_pct": np.nan,
                    "usable_for_forward_monitor": 0,
                    "usable_for_history_selector": 0,
                    "selector_allowed_now": 0,
                    "paper_or_whitelist_allowed_now": 0,
                    "trading_whitelist_allowed_now": 0,
                    "fetch_error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
    return pd.DataFrame(rows)


def _build_peer_board(product_map: pd.DataFrame) -> pd.DataFrame:
    peers = ["ec.INE", "CJ.CZCE", "au.SHFE", "ag.SHFE", "lc.GFEX", "SR.CZCE", "pb.SHFE", "sn.SHFE"]
    board = product_map[product_map["product_vt_symbol"].isin(peers)].copy()
    keep = [
        "product_vt_symbol",
        "product_family",
        "structural_bucket",
        "tradable_rows",
        "recent_median_volume",
        "recent_median_oi",
        "max_abs_corr_to_p0",
        "tail_abs_corr_to_p0_composite",
        "rolling_abs_corr_p75_to_p0",
        "trend_year_rate_pct",
        "trend_signal_median",
        "days_behind_latest_tradable",
        "data_pass",
        "liquidity_pass",
        "low_corr_pass",
        "watch_corr_pass",
        "commodity_scope",
    ]
    board = board[[column for column in keep if column in board.columns]].copy()
    board["exchange"] = board["product_vt_symbol"].astype(str).str.split(".").str[-1]
    for column in [
        "tradable_rows",
        "recent_median_volume",
        "recent_median_oi",
        "max_abs_corr_to_p0",
        "tail_abs_corr_to_p0_composite",
        "rolling_abs_corr_p75_to_p0",
        "trend_year_rate_pct",
        "trend_signal_median",
        "days_behind_latest_tradable",
        "data_pass",
        "liquidity_pass",
        "low_corr_pass",
        "watch_corr_pass",
        "commodity_scope",
    ]:
        if column in board.columns:
            board[column] = pd.to_numeric(board[column], errors="coerce")
    board["stage647_role"] = np.select(
        [
            board["product_vt_symbol"].eq("ec.INE"),
            board["product_vt_symbol"].eq("CJ.CZCE"),
            board["product_family"].eq("precious_metals"),
            board["product_family"].eq("base_metals"),
        ],
        ["target_new_shipping_index", "existing_cj_monitor", "prior_p2_precious", "prior_blocked_base_metals"],
        default="context_peer",
    )
    return board.sort_values(["max_abs_corr_to_p0", "recent_median_volume"], ascending=[True, False]).reset_index(drop=True)


def _build_product_evidence(product_map: pd.DataFrame, fetch_ledger: pd.DataFrame) -> pd.DataFrame:
    target = product_map[product_map["product_vt_symbol"].astype(str).eq("ec.INE")].copy()
    if target.empty:
        raise ValueError("ec.INE missing in Stage633 product map")
    row = target.iloc[0].to_dict()
    ok = fetch_ledger[fetch_ledger["fetch_status"].eq("ok")].copy()
    parsed = fetch_ledger[fetch_ledger["parse_ok"].eq(1)].copy()
    latest = parsed.sort_values("scfis_date").iloc[-1].to_dict() if not parsed.empty else {}
    evidence = {
        "product_vt_symbol": "ec.INE",
        "product_family_before": row.get("product_family", ""),
        "product_family_after": "watch_shipping_freight_index",
        "exchange": "INE",
        "stage633_structural_bucket": row.get("structural_bucket", ""),
        "tradable_rows": float(row.get("tradable_rows", 0.0)),
        "first_trade_date": row.get("first_trade_date", ""),
        "last_tradable_date": row.get("last_tradable_date", ""),
        "days_behind_latest_tradable": float(row.get("days_behind_latest_tradable", 0.0)),
        "recent_median_volume": float(row.get("recent_median_volume", 0.0)),
        "recent_median_oi": float(row.get("recent_median_oi", 0.0)),
        "max_abs_corr_to_p0": float(row.get("max_abs_corr_to_p0", 0.0)),
        "tail_abs_corr_to_p0_composite": float(row.get("tail_abs_corr_to_p0_composite", np.nan)),
        "rolling_abs_corr_p75_to_p0": float(row.get("rolling_abs_corr_p75_to_p0", np.nan)),
        "trend_year_rate_pct": float(row.get("trend_year_rate_pct", 0.0)),
        "trend_signal_median": float(row.get("trend_signal_median", 0.0)),
        "data_pass": int(float(row.get("data_pass", 0.0) or 0.0)),
        "liquidity_pass": int(float(row.get("liquidity_pass", 0.0) or 0.0)),
        "commodity_scope": int(float(row.get("commodity_scope", 0.0) or 0.0)),
        "source_probe_rows": int(len(fetch_ledger)),
        "source_ok_rows": int(len(ok)),
        "raw_hash_rows": int(fetch_ledger["raw_sha256_present"].sum()),
        "scfis_current_parse_rows": int(len(parsed)),
        "collection_pit_dates": int(fetch_ledger.loc[fetch_ledger["usable_for_forward_monitor"].eq(1), "received_pit_date"].nunique()),
        "latest_scfis_date": latest.get("scfis_date", ""),
        "latest_scfis_europe_value": float(latest.get("europe_value", np.nan)),
        "latest_scfis_europe_change_pct": float(latest.get("europe_change_pct", np.nan)),
        "selector_allowed_now": int(fetch_ledger["selector_allowed_now"].sum()),
        "paper_or_whitelist_allowed_now": int(fetch_ledger["paper_or_whitelist_allowed_now"].sum()),
        "trading_whitelist_allowed_now": int(fetch_ledger["trading_whitelist_allowed_now"].sum()),
        "status": "official_scfis_source_validated_watch_only_selector_locked",
    }
    return pd.DataFrame([evidence])


def _build_gates(evidence: pd.DataFrame) -> pd.DataFrame:
    e = evidence.iloc[0]
    rows = [
        ("ec_loaded_from_stage633", 1, "ec.INE exists in local product/correlation map"),
        ("non_dce_independent_driver", 1, "INE shipping freight index is outside DCE commodity families"),
        ("liquidity_ok_for_monitor", int(e["recent_median_volume"] >= 1000), "recent median volume >= 1000"),
        ("local_price_data_fresh_enough", int(e["data_pass"] == 1 and e["days_behind_latest_tradable"] <= 10), "local futures proxy is stale in Stage633"),
        ("watch_corr_below_020", int(e["max_abs_corr_to_p0"] <= WATCH_CORR_THRESHOLD), "watch corr gate <= 0.20"),
        ("strict_corr_below_015", int(e["max_abs_corr_to_p0"] <= STRICT_CORR_THRESHOLD), "strict corr gate <= 0.15"),
        ("tail_corr_available", int(pd.notna(e["tail_abs_corr_to_p0_composite"])), "history is short; tail corr is missing"),
        ("official_scfis_source_fetch_ok", int(e["source_ok_rows"] >= 3), "at least 3 official/context pages fetched"),
        ("official_scfis_current_value_parsed", int(e["scfis_current_parse_rows"] >= 1), "SSE SCFIS Europe current value parsed"),
        ("raw_hash_rows_present", int(e["raw_hash_rows"] >= 3), "official source raw hashes retained"),
        ("collection_pit_dates_reach_20", int(e["collection_pit_dates"] >= REQUIRED_COLLECTION_PIT_DATES), "selector requires 20 collection PIT dates"),
        ("independent_episodes_reach_3", 0, "no EC source/outcome episodes yet"),
        ("selector_rows_zero", int(e["selector_allowed_now"] == 0), "selector remains locked"),
        (
            "paper_trading_whitelist_rows_zero",
            int(e["paper_or_whitelist_allowed_now"] == 0 and e["trading_whitelist_allowed_now"] == 0),
            "paper/trading whitelist remain locked",
        ),
        ("fail_closed_discipline", 1, "source validation does not promote trading"),
    ]
    return pd.DataFrame(rows, columns=["gate", "passed", "notes"])


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 50) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _plot_chart(fetch_ledger: pd.DataFrame, evidence: pd.DataFrame, peer_board: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Stage647 ec.INE second-slot source probe: official SCFIS parsed, selector locked", fontsize=14, weight="bold")

    ax = axes[0, 0]
    peers = peer_board.sort_values("max_abs_corr_to_p0").copy()
    colors = np.where(peers["product_vt_symbol"].eq("ec.INE"), "#f5a623", "#4a90e2")
    ax.bar(peers["product_vt_symbol"], peers["max_abs_corr_to_p0"], color=colors)
    ax.axhline(STRICT_CORR_THRESHOLD, color="#d9534f", linestyle="--", linewidth=1, label="strict 0.15")
    ax.axhline(WATCH_CORR_THRESHOLD, color="#f0ad4e", linestyle=":", linewidth=1, label="watch 0.20")
    ax.set_title("Low-corr peer board: ec.INE is watch, not strict")
    ax.set_ylabel("max abs corr to P0")
    ax.tick_params(axis="x", rotation=35)
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    source = fetch_ledger.sort_values("response_bytes").copy()
    colors = np.where(source["parse_ok"].eq(1), "#66bb6a", np.where(source["fetch_status"].eq("ok"), "#4a90e2", "#d9534f"))
    ax.barh(source["source_name"], source["response_bytes"], color=colors)
    ax.set_title("Official source fetch bytes and parse status")
    ax.set_xlabel("bytes")
    ax.tick_params(axis="y", labelsize=8)
    for idx, row in source.reset_index(drop=True).iterrows():
        label = f"{row['http_status']} hash={int(row['raw_sha256_present'])} kw={int(row['keyword_hit_count'])}"
        if int(row["parse_ok"]) == 1:
            label += " parsed"
        ax.text(0, idx, label, va="center", ha="left", fontsize=8, color="white")

    ax = axes[1, 0]
    e = evidence.iloc[0]
    metrics = pd.Series(
        {
            "official source rows": e["source_ok_rows"],
            "raw hashes": e["raw_hash_rows"],
            "SCFIS parse rows": e["scfis_current_parse_rows"],
            "collection PIT dates": e["collection_pit_dates"],
            "selector rows": e["selector_allowed_now"],
        }
    )
    colors = ["#66bb6a", "#66bb6a", "#66bb6a", "#f0ad4e", "#d9534f"]
    ax.bar(metrics.index, metrics.values, color=colors)
    ax.axhline(REQUIRED_COLLECTION_PIT_DATES, color="#d9534f", linestyle="--", linewidth=1, label="20 PIT selector gate")
    ax.set_title(
        f"SCFIS Europe {e['latest_scfis_date']} value {e['latest_scfis_europe_value']:.2f}, change {e['latest_scfis_europe_change_pct']:.2f}%"
    )
    ax.tick_params(axis="x", rotation=25)
    ax.legend(fontsize=8)
    for idx, value in enumerate(metrics.values):
        ax.text(idx, max(float(value), 0.1), f"{int(value)}", ha="center", va="bottom", fontsize=8)

    ax = axes[1, 1]
    colors = ["#66bb6a" if int(item) == 1 else "#d9534f" for item in gates["passed"]]
    ax.barh(gates["gate"], [1.0] * len(gates), color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates")
    ax.tick_params(axis="y", labelsize=8)
    for idx, row in gates.iterrows():
        ax.text(0.02, idx, "PASS" if row["passed"] else "FAIL", va="center", ha="left", fontsize=8, color="white", weight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(
    generated_at: datetime,
    fetch_ledger: pd.DataFrame,
    evidence: pd.DataFrame,
    peer_board: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    e = evidence.iloc[0]
    lines = [
        "# Stage647 ec.INE Second-slot Source Probe Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: source/slot priority probe only; no strategy replay, no selector, no paper, no whitelist, no CTP.",
        "",
        "## External Research Judgement",
        "",
        "- `ec.INE` is a shipping freight index future. Its underlying SCFIS Europe index is published by Shanghai Shipping Exchange and referenced by INE.",
        "- This is economically more independent than another metal or petrochemical leg, but local futures history is short/stale and correlation is only watch-level, not strict low-corr.",
        "- GitHub search did not identify a reliable dedicated SCFIS Python package; the executable route should therefore be official-page raw-hash monitoring plus a custom parser.",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- max abs corr to P0: `{e['max_abs_corr_to_p0']:.4f}`",
        f"- rolling abs corr p75 to P0: `{e['rolling_abs_corr_p75_to_p0']:.4f}`",
        f"- tail abs corr to P0 composite: `{e['tail_abs_corr_to_p0_composite']}`",
        f"- recent median volume: `{e['recent_median_volume']:.1f}`",
        f"- days behind latest tradable: `{e['days_behind_latest_tradable']:.0f}`",
        f"- source ok rows: `{int(e['source_ok_rows'])}`",
        f"- raw hash rows: `{int(e['raw_hash_rows'])}`",
        f"- SCFIS current parse rows: `{int(e['scfis_current_parse_rows'])}`",
        f"- latest SCFIS Europe: `{e['latest_scfis_date']} {e['latest_scfis_europe_value']:.2f}, change {e['latest_scfis_europe_change_pct']:.2f}%`",
        f"- collection PIT dates: `{int(e['collection_pit_dates'])}`",
        f"- selector/paper/whitelist: `{int(e['selector_allowed_now'])}/{int(e['paper_or_whitelist_allowed_now'])}/{int(e['trading_whitelist_allowed_now'])}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Fetch Ledger",
        "",
        _md_table(
            fetch_ledger,
            [
                "source_name",
                "http_status",
                "fetch_status",
                "response_bytes",
                "raw_sha256_present",
                "keyword_hit_count",
                "parse_ok",
                "scfis_date",
                "europe_value",
                "europe_change_pct",
                "usable_for_forward_monitor",
            ],
        ),
        "",
        "## Product Evidence",
        "",
        _md_table(evidence),
        "",
        "## Peer Board",
        "",
        _md_table(
            peer_board,
            [
                "product_vt_symbol",
                "exchange",
                "stage647_role",
                "structural_bucket",
                "recent_median_volume",
                "max_abs_corr_to_p0",
                "tail_abs_corr_to_p0_composite",
                "rolling_abs_corr_p75_to_p0",
                "trend_signal_median",
                "days_behind_latest_tradable",
                "data_pass",
            ],
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- `ec.INE` has a credible official source route: INE references SCFIS, and Shanghai Shipping Exchange current SCFIS Europe value was parsed from the official page.",
        "- It is not deployable: Stage633 local futures proxy is stale/short, tail corr is unavailable, strict corr fails, and collection PIT dates are only `1`.",
        "- The practical next step is a master PIT append gate for SCFIS current values, not a trading backtest.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    product_map = _read_csv(STAGE633_PRODUCT_MAP)
    fetch_ledger = _fetch_sources(generated_at)
    peer_board = _build_peer_board(product_map)
    evidence = _build_product_evidence(product_map, fetch_ledger)
    gates = _build_gates(evidence)

    source_parse_ok = int(evidence["scfis_current_parse_rows"].iloc[0]) >= 1
    decision_text = (
        "ec_ine_scfis_official_source_validated_watch_only_selector_locked"
        if source_parse_ok
        else "ec_ine_scfis_official_source_probe_failed_selector_locked"
    )
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": decision_text,
        "source_probe_rows": int(len(fetch_ledger)),
        "source_ok_rows": int(evidence["source_ok_rows"].iloc[0]),
        "raw_hash_rows": int(evidence["raw_hash_rows"].iloc[0]),
        "scfis_current_parse_rows": int(evidence["scfis_current_parse_rows"].iloc[0]),
        "latest_scfis_date": str(evidence["latest_scfis_date"].iloc[0]),
        "latest_scfis_europe_value": float(evidence["latest_scfis_europe_value"].iloc[0]),
        "latest_scfis_europe_change_pct": float(evidence["latest_scfis_europe_change_pct"].iloc[0]),
        "max_abs_corr_to_p0": float(evidence["max_abs_corr_to_p0"].iloc[0]),
        "rolling_abs_corr_p75_to_p0": float(evidence["rolling_abs_corr_p75_to_p0"].iloc[0]),
        "collection_pit_dates": int(evidence["collection_pit_dates"].iloc[0]),
        "selector_allowed_now": int(evidence["selector_allowed_now"].iloc[0]),
        "paper_or_whitelist_allowed_now": int(evidence["paper_or_whitelist_allowed_now"].iloc[0]),
        "trading_whitelist_allowed_now": int(evidence["trading_whitelist_allowed_now"].iloc[0]),
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "outputs": {
            "fetch_ledger": str(FETCH_LEDGER_PATH),
            "product_evidence": str(PRODUCT_EVIDENCE_PATH),
            "peer_board": str(PEER_BOARD_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    _plot_chart(fetch_ledger, evidence, peer_board, gates)
    fetch_ledger.to_csv(FETCH_LEDGER_PATH, index=False, encoding="utf-8-sig")
    evidence.to_csv(PRODUCT_EVIDENCE_PATH, index=False, encoding="utf-8-sig")
    peer_board.to_csv(PEER_BOARD_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(generated_at, fetch_ledger, evidence, peer_board, gates, decision), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
