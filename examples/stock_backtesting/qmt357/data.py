"""Offline, immutable-input snapshots for the isolated QMT 357 stock backtest.

Prices are unadjusted execution prices; ``adj_factor`` is used by the strategy
for indicators. Volume is shares and cash_dividend is cash per pre-event share.
No broker, vn.py database, environment configuration, or market API is used.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
INDEX_SYMBOL = "000300.SSE"
REQUIRED_COLUMNS = (
    "date", "vt_symbol", "open", "high", "low", "close", "volume",
    "adj_factor", "limit_up", "limit_down", "is_st", "is_member",
)


def _data_root() -> Path:
    """Disallow a data directory redirected outside this module by a symlink."""
    if DATA_DIR.is_symlink():
        raise ValueError("The stock data directory must not be a symlink")
    return DATA_DIR.resolve()


def _snapshot_path(name: str) -> Path:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Snapshot name must be a single safe directory name")
    path = _data_root() / name
    if path.is_symlink() or path.resolve().parent != _data_root():
        raise ValueError("Snapshot path escapes the isolated stock data directory")
    return path


def _boolean(value: object) -> bool:
    """Unknown status is an error, never a tradable default."""
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1"}:
            return True
        if token in {"false", "0"}:
            return False
    elif not pd.isna(value):
        if value == 1:
            return True
        if value == 0:
            return False
    raise ValueError(f"Boolean status must be true/false or 0/1, got {value!r}")


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"Missing stock panel columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("Stock panel is empty")
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate column names in stock panel")
    panel = frame.copy()
    panel.attrs = {}
    for column, default in (("cash_dividend", 0.0), ("split_ratio", 1.0)):
        if column not in panel:
            panel[column] = default
    panel = panel[list(REQUIRED_COLUMNS) + ["cash_dividend", "split_ratio"]].copy()
    try:
        dates = pd.to_datetime(panel["date"].astype(str), format="mixed", errors="raise")
        if dates.isna().any() or dates.dt.tz is not None or not dates.eq(dates.dt.normalize()).all():
            raise ValueError("Dates must be timezone-naive daily dates without intraday time")
    except (TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Dates must be valid daily dates") from exc
    panel["date"] = dates
    panel["vt_symbol"] = panel["vt_symbol"].astype(str).str.strip().str.upper().replace(
        {r"\.SH$": ".SSE", r"\.SZ$": ".SZSE"}, regex=True
    )
    if not panel["vt_symbol"].str.fullmatch(r"\d{6}\.(SSE|SZSE)").all():
        raise ValueError("Only six-digit SSE/SZSE stock symbols are supported")
    if panel.duplicated(["date", "vt_symbol"]).any():
        raise ValueError("Duplicate symbol/date in stock panel")
    for column in ("is_st", "is_member"):
        panel[column] = panel[column].map(_boolean).astype(bool)
    numeric = ("open", "high", "low", "close", "volume", "adj_factor", "cash_dividend", "split_ratio")
    for column in numeric + ("limit_up", "limit_down"):
        try:
            panel[column] = pd.to_numeric(panel[column], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{column} must be numeric") from exc
    for column in numeric:
        if not panel[column].map(math.isfinite).all():
            raise ValueError(f"{column} must contain finite values")
    positive = ("open", "high", "low", "close", "adj_factor", "split_ratio")
    if (panel[list(positive)] <= 0).any().any():
        raise ValueError("Prices, adjustment factors and split ratios must be positive")
    if (panel[["volume", "cash_dividend"]] < 0).any().any():
        raise ValueError("Volume and cash dividends must be non-negative")
    if (panel["high"] < panel[["open", "close"]].max(axis=1)).any():
        raise ValueError("High must be at least open and close")
    if (panel["low"] > panel[["open", "close"]].min(axis=1)).any():
        raise ValueError("Low must be no greater than open and close")
    index = panel["vt_symbol"].eq(INDEX_SYMBOL)
    stocks = ~index
    if not index.any() or not stocks.any():
        raise ValueError("Panel needs both the 000300.SSE index and stock rows")
    if panel.loc[index, ["is_st", "is_member"]].any().any():
        raise ValueError("Index rows must have is_st=False and is_member=False")
    if not panel.loc[stocks, "date"].isin(panel.loc[index, "date"]).all():
        raise ValueError("Every stock date must exist in the index calendar")
    for column in ("limit_up", "limit_down"):
        values = panel.loc[stocks, column]
        if not values.map(math.isfinite).all() or (values <= 0).any():
            raise ValueError("Stock price limits must be finite positive values")
        index_values = panel.loc[index, column].dropna()
        if not index_values.map(math.isfinite).all() or (index_values <= 0).any():
            raise ValueError("Index limits must be absent or finite positive values")
    if (panel.loc[stocks, "limit_down"] >= panel.loc[stocks, "limit_up"]).any():
        raise ValueError("Stock limit_down must be below limit_up")
    return panel.sort_values(["date", "vt_symbol"], kind="stable").reset_index(drop=True)


def _summary(panel: pd.DataFrame) -> dict:
    stocks = panel.loc[panel["vt_symbol"] != INDEX_SYMBOL].sort_values(["vt_symbol", "date"])
    previous_factor = stocks.groupby("vt_symbol")["adj_factor"].shift()
    unexplained = (
        previous_factor.notna()
        & ~stocks["adj_factor"].combine(previous_factor, lambda a, b: math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12))
        & stocks["cash_dividend"].eq(0)
        & stocks["split_ratio"].eq(1)
    )
    index_days = int(panel.loc[panel["vt_symbol"] == INDEX_SYMBOL, "date"].nunique())
    min_stock_rows = int(stocks.groupby("vt_symbol").size().min())
    return {
        "rows": len(panel),
        "stock_symbols": int(stocks["vt_symbol"].nunique()),
        "start_date": panel["date"].min().strftime("%Y-%m-%d"),
        "end_date": panel["date"].max().strftime("%Y-%m-%d"),
        "index_trading_days": index_days,
        "min_stock_history_rows": min_stock_rows,
        "insufficient_history": index_days < 60 or min_stock_rows < 60,
        "factor_changes_without_actions": int(unexplained.sum()),
        "corporate_actions_required": bool(unexplained.any()),
    }


def prepare_snapshot(source: Path, name: str, universe_mode: str = "historical") -> Path:
    """Validate and freeze a user-supplied CSV/parquet inside ``DATA_DIR/name``.

    A parquet source may declare historical membership through pandas attrs
    ``historical_membership_verified=True`` and nonempty ``membership_source``.
    Such a declaration is recorded as source testimony, not independent proof.
    Source bytes are read once and are never written or consulted on replay.
    """
    target = _snapshot_path(name)
    if target.exists():
        raise FileExistsError(f"Snapshot already exists: {target}")
    if universe_mode not in {"historical", "static_snapshot", "custom"}:
        raise ValueError("universe_mode must be historical, static_snapshot or custom")
    source = Path(source).expanduser().resolve(strict=True)
    if source.suffix.lower() not in {".csv", ".parquet"} or not source.is_file():
        raise ValueError("Source must be a local CSV or parquet file")
    source_bytes = source.read_bytes()
    if source.suffix.lower() == ".csv":
        frame = pd.read_csv(io.BytesIO(source_bytes), dtype={"vt_symbol": str})
    else:
        frame = pd.read_parquet(io.BytesIO(source_bytes))
    declared = frame.attrs.get("historical_membership_verified") is True
    membership_source = frame.attrs.get("membership_source", "")
    if not isinstance(membership_source, str):
        raise ValueError("membership_source declaration must be text")
    declared = declared and bool(membership_source.strip())
    source_metadata = json.loads(json.dumps(frame.attrs, ensure_ascii=False, allow_nan=False))
    panel = _normalise(frame)
    panel_bytes = panel.to_parquet(index=False)
    manifest = {
        "schema_version": 1,
        "snapshot_name": name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "panel_file": "panel.parquet",
        "panel_sha256": hashlib.sha256(panel_bytes).hexdigest(),
        "universe_mode": universe_mode,
        "historical_membership_verified": declared and universe_mode == "historical",
        "membership_verification_basis": "source_declaration" if declared else "unverified",
        "membership_source": membership_source,
        "source_metadata": source_metadata,
        "provider": source_metadata.get("provider", "user_supplied"),
        "data_limitations": source_metadata.get("data_limitations", []),
        "execution_semantics": source_metadata.get("execution_semantics", {}),
        "price_basis": "unadjusted_execution_prices_with_separate_adj_factor",
        "volume_unit": "shares",
        "cash_dividend_unit": "cash_per_pre_event_share",
        "split_ratio_semantics": "post_event_shares_per_pre_event_share",
        "corporate_action_policy": "Held factor changes without explicit cash_dividend or split_ratio must fail replay; adjustment factors do not replace event accounting.",
        **_summary(panel),
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _data_root().mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    try:
        (target / "panel.parquet").write_bytes(panel_bytes)
        (target / "manifest.json").write_bytes(manifest_bytes)
    except BaseException:
        # Only remove files created by this failed import, never an existing snapshot.
        for filename in ("panel.parquet", "manifest.json"):
            (target / filename).unlink(missing_ok=True)
        target.rmdir()
        raise
    return target


def load_snapshot(path: Path) -> tuple[pd.DataFrame, dict]:
    """Read and validate a frozen local copy without touching its original source."""
    path = Path(path).expanduser()
    if path.is_symlink() or path.resolve().parent != _data_root():
        raise ValueError("Snapshot must be directly inside the isolated stock data directory")
    path = _snapshot_path(path.name)
    manifest_path = path / "manifest.json"
    panel_path = path / "panel.parquet"
    if manifest_path.is_symlink() or panel_path.is_symlink():
        raise ValueError("Snapshot files must not be symlinks")
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1 or metadata.get("panel_file") != "panel.parquet":
        raise ValueError("Unsupported or redirected snapshot manifest")
    if metadata.get("snapshot_name") != path.name:
        raise ValueError("Snapshot name does not match manifest")
    content = panel_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata.get("panel_sha256"):
        raise ValueError("Snapshot panel SHA256 hash mismatch")
    panel = _normalise(pd.read_parquet(io.BytesIO(content)))
    if any(metadata.get(key) != value for key, value in _summary(panel).items()):
        raise ValueError("Snapshot manifest data summary mismatch")
    return panel, metadata
