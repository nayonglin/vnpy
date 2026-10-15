---
name: futures-recap-html
description: Use when a user asks to generate a futures backtest recap HTML, 复盘HTML, 逐笔复盘, 多周期K线复盘, or requests the current recap page format for a completed vn.py backtest.
---

# Futures Backtest Recap HTML

## Overview

Generate the recap from one identity-closed frozen backtest through the repository's canonical renderer. Reuse the renderer; never copy its HTML or plotting implementation into a new generator.

**REQUIRED REFERENCE:** Read [references/recap-contract.md](references/recap-contract.md) before selecting data or running a command.

## Workflow

1. Resolve one source bundle in this order: user-specified version/path, artifacts produced in the current task, then one uniquely identifiable completed run in the active research line. A stage number or modification time alone is not identity evidence.
2. Verify the bundle's trades, equity/daily series, summary, interval, parameters, source commit or run id, and hashes when supplied. Stop on ambiguity rather than mixing runs.
3. Use `.py311/bin/python` and the command matrix in the reference. The canonical renderer is `research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py`.
4. If the source is not registered, add a narrow frozen-source adapter to the canonical renderer with tests. Keep the chart contract unchanged and write to a new versioned output directory.
5. Validate the generated manifest, summary, trade counts, frozen metrics, JavaScript, browser rendering, and linked zoom before returning the absolute clickable `index.html` path.

## Authority Boundaries

- Existing backtest artifacts authorize visualization only. They do not authorize a strategy rerun, market-data download, CTP connection, order API call, production read, or production write.
- Download missing historical data only when the user explicitly authorizes it. Never invent, forward-fill, or substitute missing exact-contract bars without labeling the proxy.
- When the request itself names the current live/formal version, use `futures-live-execution-sop` for read-only release identity only. That request does not authorize account access, CTP connection, order APIs, or production writes. Do not describe a page as current-live unless production identity and frozen backtest provenance match.
- This workflow does not create new strategy evidence. Do not present selected winners, chart patterns, or a successful render as promotion evidence.

## Deliverable

Report the source identity, output path, trade count, available periods, missing-data disclosures, and verification result. State explicitly whether strategy rerun, market download, or production access occurred.
