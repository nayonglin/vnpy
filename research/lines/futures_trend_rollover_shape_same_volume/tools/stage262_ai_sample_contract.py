"""Research-only eligibility and label-time contract; no strategy/runtime changes."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

TARGET = "target_future_top_half_60d"
WEIGHT = "sample_weight_future_rank_60d"
FUTURE = "future_net_pnl_60d"


def build_window_metadata(
    daily: pd.DataFrame, coverage: pd.DataFrame, *, history: int = 120, horizon: int = 60
) -> pd.DataFrame:
    """Dates follow the source calendar. Absence is coverage failure, never zero PnL.

    listed_asof is only a LOCAL valid-mapping boundary proxy, not exchange-certified
    listing or PIT tradability. Contract coverage is not a liquidity guarantee.
    """
    keys = ["date", "product_vt_symbol"]
    if history < 1 or horizon < 1:
        raise ValueError("windows must be positive")
    if daily.duplicated(keys).any() or coverage.duplicated(keys).any():
        raise ValueError("duplicate product-date coverage")
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(daily.date).unique()))
    products = sorted(daily.product_vt_symbol.unique())
    grid = pd.MultiIndex.from_product([dates, products], names=keys)
    if len(daily) != len(grid):
        raise ValueError("daily must contain the complete source date-product grid")
    cov = coverage.set_index(keys).reindex(grid)
    flags = cov[["observed", "mapped"]].fillna(False).astype(bool).reset_index()
    n = len(dates)
    index = np.arange(n)
    results = []
    for product, group in flags.groupby("product_vt_symbol", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        valid = group.observed & group.mapped
        history_count = valid.astype(int).rolling(history, min_periods=1).sum()
        future_count = (valid.astype(int).iloc[::-1].rolling(horizon, min_periods=1)
                        .sum().iloc[::-1].shift(-1).fillna(0))
        available_future = np.minimum(horizon, n - index - 1)
        mapped_dates = group.loc[group.mapped, "date"]
        first_mapping = mapped_dates.min() if not mapped_dates.empty else pd.NaT
        frame = pd.DataFrame({
            "eval_date": dates, "product_vt_symbol": product,
            "feature_start": [dates[i-history+1] if i+1 >= history else pd.NaT for i in index],
            "feature_end": dates,
            "label_start": [dates[i+1] if i+1 < n else pd.NaT for i in index],
            "label_end": [dates[i+horizon] if i+horizon < n else pd.NaT for i in index],
            "label_observed_days": future_count.astype(int).to_numpy(),
            "label_calendar_days": available_future,
            "history_ok": index + 1 >= history,
            "feature_coverage_ok": history_count.to_numpy() == history,
            "label_complete": available_future == horizon,
            "label_coverage_ok": future_count.to_numpy() == horizon,
            "listed_asof": dates >= first_mapping,
            "tradable_asof": valid.to_numpy(),
        })
        frame["coverage_ok"] = frame.feature_coverage_ok & frame.label_coverage_ok
        frame["eligible"] = frame.history_ok & frame.coverage_ok & frame.label_complete
        results.append(frame)
    return pd.concat(results, ignore_index=True)


def mature_training(samples: pd.DataFrame, prediction_date: pd.Timestamp) -> pd.DataFrame:
    """After-close inference can use labels ending at that same close."""
    return samples.loc[samples.label_complete & samples.label_end.notna() &
                       (samples.label_end <= prediction_date) &
                       (samples.eval_date < prediction_date)].copy()


def rerank_eligible(samples: pd.DataFrame) -> pd.DataFrame:
    result = samples.loc[samples.eligible].copy()
    result["cross_section_count"] = result.groupby("eval_date")[FUTURE].transform("size")
    result["future_rank_pct_60d"] = result.groupby("eval_date")[FUTURE].rank(method="average", pct=True)
    result["future_rank_centered_60d"] = result.future_rank_pct_60d - .5
    result[TARGET] = (result.future_rank_centered_60d > 0).astype(int)
    result[WEIGHT] = result.future_rank_centered_60d.abs().clip(.20, .60)
    return result


def month_metrics(frame: pd.DataFrame, *, top_n: int = 10) -> dict:
    future_rank = frame[FUTURE].rank(method="average", pct=True)
    score_rank = frame.score.rank(method="average")
    rank_ic = float(score_rank.corr(future_rank)) if future_rank.nunique() > 1 and score_rank.nunique() > 1 else None
    ranked = frame.assign(_truth_rank=future_rank).sort_values(
        ["score", "product_vt_symbol"], ascending=[False, True], kind="stable")
    selected = ranked.head(top_n)
    target = (future_rank > .5).astype(int)
    auc = float(roc_auc_score(target, frame.score)) if target.nunique() == 2 else None
    return {"rows": len(frame), "selected": len(selected), "rank_ic": rank_ic,
            "top_rank_lift": float(selected._truth_rank.mean() - future_rank.mean()),
            "top_half_hit_rate": float((selected._truth_rank > .5).mean()), "auc": auc}


def paired_block_interval(differences: np.ndarray, *, block: int = 6, repeats: int = 2000) -> dict:
    values = np.asarray(differences, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("paired monthly differences must be finite and nonempty")
    rng = np.random.default_rng(42)
    starts = rng.integers(0, len(values), size=(repeats, int(np.ceil(len(values)/block))))
    indexes = ((starts[..., None] + np.arange(block)) % len(values)).reshape(repeats, -1)[:, :len(values)]
    means = values[indexes].mean(axis=1)
    return {"mean_difference": float(values.mean()), "ci95_low": float(np.quantile(means, .025)),
            "ci95_high": float(np.quantile(means, .975)), "months": len(values),
            "block_months": block, "repeats": repeats, "seed": 42}
