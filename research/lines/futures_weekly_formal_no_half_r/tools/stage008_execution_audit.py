"""Post-run acceptance audit; never changes a fill, price or execution clock."""
from __future__ import annotations
import math
from collections import defaultdict
import pandas as pd


def _local_stamp(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("missing timestamp")
    return stamp.tz_convert("Asia/Shanghai").tz_localize(None) if stamp.tzinfo else stamp


def audit_actual_minute_volumes(trades, minute_by_symbol, calendar=None):
    frames = {}
    details = []
    groups = defaultdict(lambda: {"quantity": 0.0, "minute_volume": None, "trade_ids": []})
    ratios, volumes = [], []
    mismatch = invalid = 0
    for trade in trades:
        symbol = str(trade["vt_symbol"])
        detail = {"trade_id": str(trade.get("trade_id", "")), "vt_symbol": symbol,
                  "execution_datetime": str(trade.get("execution_datetime", ""))}
        reasons = []
        try:
            stamp = _local_stamp(trade["execution_datetime"])
            if calendar is not None:
                from stage005_sessions import canonical_open_timestamp
                expected = _local_stamp(canonical_open_timestamp(symbol, trade["trading_date"], calendar))
                detail["expected_canonical_datetime"] = str(expected)
                if stamp != expected:
                    raise ValueError("noncanonical_execution_timestamp")
            if symbol not in frames:
                frame = minute_by_symbol.get(symbol)
                if frame is None or "bar_datetime" not in frame:
                    frames[symbol] = None
                else:
                    frame = frame.copy()
                    frame["_audit_stamp"] = frame["bar_datetime"].map(_local_stamp)
                    frames[symbol] = frame.set_index("_audit_stamp", drop=False)
            frame = frames[symbol]
            rows = frame.loc[[stamp]] if frame is not None and stamp in frame.index else None
            if rows is None or len(rows) != 1:
                reasons.append("missing_or_duplicate_exact_minute")
                mismatch += 1
            else:
                row = rows.iloc[0]
                raw_open = float(row["open"])
                price = float(trade["price"])
                quantity = float(trade["volume"])
                minute_volume = float(row["volume"])
                detail.update(raw_open=raw_open, fill_price=price, quantity=quantity,
                              minute_volume=minute_volume if math.isfinite(minute_volume) else None)
                if not (math.isfinite(raw_open) and raw_open > 0 and math.isfinite(price)
                        and abs(raw_open - price) <= 1e-8):
                    mismatch += 1
                    reasons.append("raw_open_price_mismatch")
                if not (math.isfinite(quantity) and quantity > 0):
                    if "raw_open_price_mismatch" not in reasons:
                        mismatch += 1
                    reasons.append("invalid_fill_quantity")
                if not (math.isfinite(minute_volume) and minute_volume > 0):
                    invalid += 1
                    reasons.append("zero_or_invalid_minute_volume")
                else:
                    volumes.append(minute_volume)
                    if math.isfinite(quantity) and quantity > 0:
                        ratio = quantity / minute_volume
                        ratios.append(ratio)
                        detail["participation_ratio"] = ratio
                        group = groups[(symbol, str(stamp))]
                        group["quantity"] += quantity
                        group["minute_volume"] = minute_volume
                        group["trade_ids"].append(detail["trade_id"])
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            mismatch += 1
            reasons.append("invalid_anchor_or_fill:" + type(exc).__name__)
        detail["reasons"] = reasons
        details.append(detail)
    aggregate = [dict(vt_symbol=key[0], execution_datetime=key[1], **value,
                      participation_ratio=value["quantity"] / value["minute_volume"])
                 for key, value in sorted(groups.items())]
    accepted = mismatch == 0 and invalid == 0
    return {
        "accepted": accepted,
        "verdict": "PASS_POSITIVE_EXECUTION_MINUTES" if accepted else (
            "REJECT_EXECUTION_ZERO_VOLUME" if invalid else "REJECT_EXECUTION_ANCHOR_MISMATCH"),
        "canonical_grid_checked": calendar is not None,
        "trade_count": len(trades), "zero_or_invalid_volume_count": invalid,
        "anchor_mismatch_count": mismatch, "minute_groups": len(aggregate),
        "minimum_positive_minute_volume": min(volumes) if volumes else None,
        "max_participation_ratio": max(ratios) if ratios else None,
        "max_aggregate_participation_ratio": max((r["participation_ratio"] for r in aggregate), default=None),
        "capacity_limitation": "Positive bar volume is necessary but does not prove executable capacity; no spread, depth or queue model.",
        "details": details, "aggregate_minutes": aggregate,
    }
