# Recap HTML Contract

## Canonical Paths

- Renderer: `research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py`
- Top30 minute enrichment for the registered Stage061 Top10+fu page only: `research/lines/futures_trend_winner_trade_forensics/tools/stage050_enrich_profit_top30_minutes.py`
- Python: `.py311/bin/python`

Run commands from the repository root. Read `research/registry.md`, the active line's `LINE.md`, and the source stage record before choosing a profile.

## Checkout capability check

The command matrix below is inherited from the handoff reference. Check the
selected renderer's supported source profiles and all frozen input files in this
checkout before running it. The handoff migration on 2026-10-15 found Stage038
in Git, but did not find `stage050_enrich_profit_top30_minutes.py` in this
checkout or the handed-off source tree. Stage050 commands therefore remain
unavailable until that exact tool and its matching cached inputs are restored
and verified. Do not claim the Stage061 Top30 minute enrichment is installed or
complete, and do not substitute a different source or fetch data to conceal it.
This optional enrichment does not prevent rendering a supported frozen source
with the available canonical renderer and honest missing-minute disclosures.

## Source Identity

A source is usable only when trades, equity or strategy-daily series, and summary belong to the same completed run. Prefer an explicit immutable run receipt or manifest. Otherwise require consistent version, parameters, interval, record counts, metrics, and source commit/hash across all members.

Selection precedence:

1. Explicit user version, artifact path, run id, or stage.
2. A completed backtest produced and verified in the current task.
3. One unique completed bundle in the active research line.

Do not select by highest stage number, newest modification time, filename similarity, or production wording alone. If two candidates remain, ask which one to use.

## Registered Command Matrix

| Source | Base command | Notes |
| --- | --- | --- |
| Frozen current-C9 artifacts | `.py311/bin/python research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py --source-profile official_c9 --episode-scope all --end YYYY-MM-DD --reuse-strategy --reuse-market --no-market-download` | Reuse only an already materialized strategy bundle and local market file. |
| Frozen Stage037 C | `.py311/bin/python research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py --source-profile stage037c --episode-scope all --end YYYY-MM-DD --no-market-download` | Display-only frozen research source. |
| Frozen Stage061 Top10+fu | `.py311/bin/python research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py --source-profile stage061_top10 --episode-scope all --end 2026-08-28 --no-market-download` | Base all-trade page; source profile and cutoff are frozen. |

For the Stage061 Top10+fu page, restore the cached long/short price-move Top30 minute layer after the base render only when Stage050 and its identity-matched cache have been restored and verified. Otherwise disclose that this optional minute layer is unavailable:

```bash
.py311/bin/python research/lines/futures_trend_winner_trade_forensics/tools/stage050_enrich_profit_top30_minutes.py --publish
```

Only after explicit authorization to fetch missing historical bars:

```bash
.py311/bin/python research/lines/futures_trend_winner_trade_forensics/tools/stage050_enrich_profit_top30_minutes.py --download-missing --publish
```

Stage050 is bound to the Stage061 output identity. Do not run it for another source until its binding is generalized or a tested source-specific enrichment adapter is added.

## New Backtest Bundle

When a completed run is not registered:

1. Freeze or reference its immutable trades, equity/daily, summary, parameters, date interval, and provenance.
2. Add one explicit source profile or adapter to Stage038; reuse its pairing, aggregation, renderer, selector, and validation functions.
3. Add behavior tests that fail before the adapter exists and cover incomplete evidence, residual open positions, and output isolation.
4. Write to `research/lines/futures_trend_winner_trade_forensics/outputs/<versioned-recap-name>/`; do not overwrite another version's page.
5. Do not rerun the strategy merely to fit the renderer. Adapt the frozen results into the renderer's input contract.

## Frozen Display Contract

- Include every completed trade episode by default; disclose residual positions that lack a final exit.
- Period selector: 30-day K, 10-day K, monthly, weekly, daily, and 15-minute when available.
- Defaults: 30-day K plus daily K.
- Daily visible window: 300 trading bars before entry through 50 after final exit, bounded by real history.
- Monthly visible window: 10 months before entry through 10 after final exit.
- MA5/10/20/40 use hidden real history for warmup; no synthetic padding.
- All selected periods share the same x-range and linked zoom while keeping their own bar boundaries.
- Preserve entry/final-exit markers, holding interval, direction, lots, PnL, R when present, and underlying price change percentage.
- Price change percentage is raw underlying movement `(weighted_exit / weighted_entry - 1) * 100`; it is not direction-adjusted account return.
- Missing exact-contract history, proxy context, truncated listing history, and incomplete post-exit history remain visible disclosures.
- Fifteen-minute data never blocks valid non-minute charts. Show its absence honestly; do not manufacture bars.

## Event Placement Default

Open/close lines and fill-price markers use the **center of the execution date's containing candle in each panel**, rather than one daily x-coordinate drawn through every panel. This is a display mapping; actual execution dates, prices, volumes, trade pairing, and PnL remain unchanged.

| Panel | Event x-coordinate |
| --- | --- |
| Daily | The exact execution trading day's candle center. |
| Weekly | The center of the existing weekly bucket containing the execution date. |
| Monthly | The center of the execution calendar month's candle. |
| 10-day / 30-day | The center of the existing product-calendar bucket containing the execution date; keep the fixed non-overlapping bucket boundaries. |
| 15-minute, exact execution time available | The center of the candle containing that timestamp, using the declared trading-day/session convention. |
| 15-minute, only daily execution evidence available | Retain the original daily execution-day x-coordinate and explicitly label the event as day-level; do not infer an exact fill minute. If minute bars are unavailable, disclose and skip that panel. |

- Give each selected panel its own entry/exit lines and fill-price markers. Bind them to that panel's x-axis and restrict lines and holding shading to its price/volume area. Draw labels per panel, not as page-wide lines using daily x-coordinates.
- When entry and final exit belong to the same candle, keep both events at the same x and use a combined opening/closing label with both actual dates available in the details or hover. If their prices also coincide, retain both underlying fill records and use that combined label/details to distinguish them; do not move either event into a neighboring candle to separate labels.
- Match by the period's actual membership bounds. If no containing candle exists, leave the marker absent and disclose the gap; do not snap to the nearest candle or invent bars.
- Preserve shared x-ranges and linked zoom. The same event may have different x-coordinates in different periods because those candles have different centers; that difference is expected.
- Reuse this behavior through the canonical renderer and source adapter. Keep old frozen pages intact; create a new versioned output when re-rendering an existing recap.

## Verification Gate

Before delivery, verify observable outcomes:

1. `summary.json`, `chart_manifest.csv`, and `index.html` exist in the same output bundle.
2. Completed-trade count and profit/loss/flat counts reconcile to the frozen source.
3. Frozen equity, return, drawdown, Sharpe, slippage, trade count, and win-rate fields remain unchanged when present.
4. Every rendered entry/final-exit date and price reconciles to the source pairings.
5. MA warmup has no avoidable leading nulls in visible bars.
6. Embedded JavaScript parses successfully.
7. A browser check confirms default periods, filters, next/previous navigation, and synchronized zoom, plus the event-placement checks below.
8. Missing-data and proxy disclosures match the manifest.
9. `git diff --check` passes and unrelated dirty files remain untouched.

Event-placement acceptance:

- Check every rendered non-minute entry/final-exit date against its containing period candle and compare the line and fill marker x with that candle's x; verify actual source date/price fields independently.
- In a real browser, inspect a weekday execution in weekly plus daily view: the weekly line must cross that week's candle center while the daily line remains on the actual day's candle. Also switch to monthly and 10/30-day views, single-period view, and a different panel order.
- Confirm panel-local line extents, same-candle opening/closing labels, and no nearest-candle fallback on a missing bucket. Zooming must still synchronize all visible periods.
- When available, verify exact minute timestamps against session-aware candle membership. With daily-only fill evidence, check the precision disclosure instead of claiming minute accuracy.

Return a clickable absolute path to `index.html`, plus a concise statement of source identity and whether any rerun, download, production access, or strategy change occurred.

## Common Mistakes

| Mistake | Correct action |
| --- | --- |
| Selecting the highest Stage or newest file | Resolve one complete run from receipt/provenance and all source members. |
| Copying the last HTML and replacing labels | Run the canonical renderer against the new frozen source adapter. |
| Claiming complete Stage061 Top30 minute enrichment after only Stage038 | Run the bound Stage050 `--publish` step only after its tool and cache are restored and verified; otherwise disclose the unavailable minute layer. |
| Applying Stage050 to another source | Add and test an explicit enrichment binding first. |
| Rerunning a strategy because the renderer lacks an adapter | Adapt the already completed frozen result instead. |
| Downloading bars merely to make every panel look complete | Keep truthful gaps unless the user explicitly authorizes historical download. |
| Calling a research page the current live version | Match read-only production release identity to frozen provenance first. |
| Drawing one daily-coordinate entry/exit line through weekly or monthly panels | Map each execution to that panel's containing candle center; keep actual dates in details and hover. |
| Moving K lines, fill dates, or neighboring markers to make the picture line up | Preserve the frozen bars and fills; change only the display mapping of event lines and markers. |
