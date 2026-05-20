---
name: stage78-simnow-shadow-sop
description: Use for Stage78-1 futures trend daily CTP/SimNow/broker-test shadow or virtual trading SOP, monthly AI pool cadence, CTP read-only checks, Phase B pre-submit gates, risk-level interpretation, smoke-order tests, and daily execution/reconciliation discipline. Trigger when the user asks about Stage78-1 virtual trading, shadow trading, SimNow, broker-test CTP, daily reports, AI pool timing, review/yellow-light risk status, order drafts, smoke orders, or whether a Stage78-1 signal may be submitted. Do not use for unrelated stock/range strategies or alpha optimization.
---

# Stage78-1 CTP/SimNow Shadow SOP

## Core Positioning

This skill is an execution-discipline guide, not an alpha-research guide.

- Line: `futures_trend`.
- Strategy: Stage78-1 official trend baseline.
- Capital: `500000` only. Treat old `30w` paths as historical references unless the user explicitly creates a new independent deployment variant.
- Account state source for virtual/live execution: CTP broker/SimNow snapshot, not historical shadow holdings.
- Python: use `.py311/bin/python`.
- Secrets: never write, print, or store CTP/SimNow passwords in repo files, reports, stage records, or chat. Read credentials only from local environment variables or local secure config.

Before running anything, read:

1. `work-type.txt`
2. `research/registry.md`
3. `research/lines/futures_trend/LINE.md`
4. `research/lines/futures_trend/SOP_stage78_monthly_ai_pool.md` when AI pool timing matters

State at the start and end:

- Overfitting judgment: yes/no and why.
- Continued-value judgment: yes/no and why.

## Daily Shadow Workflow

Use this after a completed trading day, normally after market data for that day is available.

1. Identify the latest completed trading day. Do not assume calendar today is a complete trading day.
2. Update main-contract mapping and daily bars:
   - `examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py`
3. Use the current month AI pool for daily signals. Do not retrain or rerank the AI pool every day.
4. Run the canonical 50w Stage78-1 latest-AI-pool shadow runner:
   - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_1_2026_cold_start_latest_ai_pool.py`
5. Read the generated daily report and signal plan.
6. Interpret risk level:
   - `base` or normal status: signal may proceed to broker-state gates.
   - `review`: shadow records continue, but SimNow/live execution may only close, reduce risk, or reconcile; do not open new positions.
   - missing/unknown risk state: fail closed.
7. Write a Chinese stage record under `research/lines/futures_trend/stages/`.

## Daily 7x24 Dry-Run Gate

Use this after the daily shadow report when the goal is to decide whether the next SimNow session has an actionable Stage78-1 order. This workflow is still dry-run; it must not call `send_order`.

1. Update data to the latest completed trading day:
   - `examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py --mapping-start YYYY-MM-01 --bar-start YYYY-MM-DD --end YYYY-MM-DD`
2. Run the 50w latest-AI-pool shadow report for the same target date:
   - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_1_2026_cold_start_latest_ai_pool.py --target-date YYYY-MM-DD`
3. Refresh SimNow 7x24 read-only broker state:
   - `SIMNOW_FRONT=7x24 examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 90`
4. Run the daily execution gate:
   - `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py --max-snapshot-age-seconds 300`
5. Interpret the gate result:
   - `simnow_executable`: may proceed to Stage251 fresh pre-submit gate; this still does not submit an order.
   - `skip_broker_flat_for_close`: do not submit; the strategy has a theoretical close signal but SimNow has no matching position.
   - `blocked`: do not submit; fix the stated gate failure first.
6. Required invariants:
   - `order_api_called_count` must be `0`.
   - `review` allows close/reduce/reconcile only; it blocks new opens.
   - Broker/SimNow positions override historical shadow positions.
   - A close signal requires a matching SimNow position in the opposite direction.
7. Record a Chinese stage file under `research/lines/futures_trend/stages/` with the target date, AI pool eval date, risk level, signal list, broker snapshot state, gate action, order API count, and next step.

## Monthly AI Pool Cadence

The AI pool is monthly, not daily.

- Run monthly live inference only after the previous month last trading day has complete data.
- Daily reports should use the current month pool.
- If the month changed but the pool was not refreshed, say so and either refresh it or mark the daily report as stale-input risk.
- Do not modify the AI ranking logic during daily operations.

## SimNow Gate Workflow

Use this before any virtual order can be submitted.

1. Network probe:
   - `examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`
2. Read-only CTP/vn.py probe during the intended SimNow service window:
   - `examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 90`
3. Require:
   - market login success,
   - trading auth success,
   - trading login success,
   - settlement confirmation success,
   - fresh account snapshot,
   - position snapshot state is `confirmed_flat` or a concrete non-empty position snapshot.
4. If the snapshot is stale, missing, ambiguous, or login fails, stop.
5. Run the Phase B fresh pre-submit gate:
   - `examples/portfolio_backtesting/run_qmt_roll_stage251_phaseb_fresh_pre_submit_gate.py`
6. Confirm total real submit/send-order calls are still zero unless the user explicitly asked for a test-environment virtual order and the broker-test/SimNow adapter is being used.

## Broker-Test CTP Workflow

Use this when the user has provided a broker CTP test/simulation account and explicitly says the environment is a test environment.

1. Refresh a broker-test read-only snapshot:
   - `bash examples/portfolio_backtesting/run_ctp_stage267_broker_test_readonly_probe.sh --connect --wait-seconds 20`
2. Require:
   - market login success,
   - trading auth success,
   - trading login success,
   - settlement confirmation success,
   - account snapshot,
   - position snapshot state is `confirmed_flat` or `positions_received`,
   - contract snapshot is present.
3. Before any broker-test submit, run dry-run first:
   - `bash examples/portfolio_backtesting/run_ctp_stage268_broker_test_smoke_order.sh --mode dry-run --vt-symbol <vt_symbol> --direction long --volume 1`
4. For a one-lot submit-cancel smoke test, only proceed when all are true:
   - user has explicitly confirmed this is a test environment,
   - read-only snapshot age is within `300` seconds,
   - dry-run has `dry_run_request_ready`,
   - volume is `1`,
   - price is passive or otherwise intentionally chosen,
   - the command uses `CTP_SMOKE_ORDER_ENABLED=1`,
   - the command includes `--confirm-submit I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS`.
5. Submit-cancel command shape:
   - `CTP_SMOKE_ORDER_ENABLED=1 bash examples/portfolio_backtesting/run_ctp_stage268_broker_test_smoke_order.sh --mode submit-cancel --vt-symbol <vt_symbol> --direction long --volume 1 --confirm-submit I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS`
6. After submit-cancel, verify and report:
   - `send_order_api_called_count`,
   - `cancel_order_api_called_count`,
   - `vt_orderid`,
   - latest target order status,
   - traded volume,
   - trade row count,
   - whether a residual position exists.
7. A clean smoke test usually ends as `Cancelled` with `traded=0`. If it fills, immediately record the fill and reconcile the new test position; do not pretend it was only a connectivity test.
8. Never use the smoke-order path for normal Stage78-1 strategy sizing. It only proves the broker adapter can submit and cancel one tiny test order.

## Broker CP Mac SDK / 414xx Isolated Workflow

Use this only when a broker asks to test the CTP CP/evaluation front such as `414xx` with the SimNow Mac CP SDK.

1. Do not overwrite `.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs`.
2. Download and unpack the Mac CP SDK outside the repo or in a local ignored directory. Current verified package:
   - file: `TraderapiMduserapi_6.7.7_MacOS_CP.zip`
   - md5: `bbb85d8789008ee81094aca87b2c9715`
   - version string: `v6.7.7_MacOS_CP_20240716 15:00:00`
   - broker-provided `v6.6.7_CP_tradeapi.zip` is not a Mac package: it contains Linux `.so` and Windows `.dll/.lib`, but no macOS `.framework/.dylib`.
3. Remove quarantine only from the isolated extracted copy if macOS blocks loading:
   - `xattr -dr com.apple.quarantine <sdk_dir>`
4. Run read-only only, with `CTP_MAC_CP_SDK_DIR` pointing to the extracted directory that directly contains both frameworks:
   - `CTP_MAC_CP_SDK_DIR=<sdk_dir> CTP_BROKERID=1010 CTP_TD_ADDRESS=tcp://182.140.218.46:41407 CTP_MD_ADDRESS=tcp://182.140.218.46:41415 bash examples/portfolio_backtesting/run_ctp_stage271_broker_cp_mac_sdk_readonly_probe.sh --connect --wait-seconds 25`
   - If the combined vn.py gateway crashes or mixes MD/TD symptoms, isolate TD with:
     `CTP_MAC_CP_SDK_DIR=<sdk_dir> bash examples/portfolio_backtesting/run_ctp_stage273_cp_mac_td_only_probe.sh`
   - To isolate MD subscription only:
     `CTP_MAC_CP_SDK_DIR=<sdk_dir> CTP_MD_SUBSCRIBE_SYMBOLS=MA609,ru2609 bash examples/portfolio_backtesting/run_ctp_stage274_cp_mac_md_subscribe_probe.sh`
5. Interpret results:
   - old `decode err / 4097`: likely wrong API/front pairing or wrong TD/MD address.
   - `客户端未认证` / code `64`: CP SDK reached the front, but AppID/AuthCode/account authorization is not accepted for that front; ask broker to register/confirm CP AppID/AuthCode and account permission.
   - `exit_code=139` or TD-only exit-time segfault: fail closed; treat as native API/Python wrapper/front compatibility risk until broker provides a matching Python/vn.py binding or a confirmed Mac CP runtime path.
   - MD subscription `ErrorID=0` with stale/last ticks during closed sessions means market-data subscription is accepted, but continuous real-time push still needs a night/day session retest.
   - read-only snapshots received: only then consider a 1-lot smoke-order path, and still use explicit submit confirmation gates.
   - Native C++ direct `CThostFtdcTraderApi` success while `vnpy_ctp`/Python TD-only fails means the front/account/AppID/AuthCode/CP SDK are likely OK and the active blocker is the Python wrapper/ABI compatibility layer.
6. The normal broker-test route remains `41207/41215` with the existing vnpy_ctp framework unless the broker explicitly requires the CP SDK path.
7. Current confirmed Stage278 result:
   - Native C++ direct TD-only probe to `tcp://182.140.218.46:41407` with SimNow Mac CP SDK `v6.7.7_MacOS_CP_20240716 15:00:00` completed authentication, login, settlement confirmation, account query, and position query.
   - The probe is read-only and must not be extended to order submission without the normal fresh snapshot, dry-run, 1-lot smoke-order, and explicit confirmation gates.
   - If `414xx/CP` becomes mandatory for deployment, prefer either rebuilding/replacing `vnpy_ctp` against the matching CP Mac SDK or creating a minimal native C++ bridge, rather than patching strategy logic around an unstable wrapper.
8. Current confirmed Stage279 result:
   - Broker-provided `DataCollectforMacOS0719.zip` can collect terminal info on this Mac.
   - `run_ctp_stage278_native_cpp_td_login_probe.sh` now auto-runs `DataCollectforMacOS` when available and passes the collected data to `ReqUserLogin` as non-empty `systemInfo`.
   - Latest `41407` native C++ TD-only login completed with `ReqUserLogin system_info_len=100`, authentication/login/settlement/account/position all successful, and zero order APIs called.
   - Do not print raw `CollectData`; it contains local MAC and device identifiers. Report only the length plus CTP session fields unless the user explicitly asks to share raw terminal collection data with the broker.
   - `RegisterUserSystemInfo` remains opt-in via `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=1` because the broker contact said it was not required.
9. Current confirmed Stage280 result:
   - Broker-provided new test account also completed `41407` native C++ TD-only login with `CTP_CLIENT_SYSTEM_INFO=set(len=100)`.
   - Session fields for broker lookup: `FrontID=15`, `SessionID=1715607367`, `TradingDay=20260520`, `LoginTime=15:44:05`.
   - Account and position snapshots were received; zero order APIs were called.
   - Use sanitized evidence under `examples/portfolio_backtesting/backtest_outputs/ctp_evidence/stage280_41407_new_account_datacollect_login_evidence_sanitized.*` when sharing with the broker.
10. Current confirmed Stage281 result:
   - `41407` native C++ + DataCollect route reached the order API in a broker test environment.
   - Smoke order was `MA609.CZCE` buy-open, price `1.0000`, volume `1`.
   - Session fields for broker lookup: `FrontID=15`, `SessionID=1768626185`, `TradingDay=20260520`, `LoginTime=15:57:36`, `OrderRef=779263855588`.
   - `ReqOrderInsert ret=0` and `send_order_api_called_count=1`.
   - CTP then returned `OnRspOrderInsert ErrorID=21`; there was no `OnRtnOrder`, no `OnRtnTrade`, no active order, and no fill.
   - `cancel_order_api_called_count=0` because CTP rejected the insert before an active order existed.
   - Use sanitized evidence under `examples/portfolio_backtesting/backtest_outputs/ctp_evidence/stage281_41407_native_cpp_smoke_order_evidence_sanitized.*` when sharing with the broker.
   - Do not treat this as a successful submit-cancel order. It proves the order API can be called; the broker still needs to explain or clear `ErrorID=21` before this route can become a normal execution adapter.
11. Current confirmed Stage282 result:
   - Local Mac CP headers expose `RegisterUserSystemInfo`, `SubmitUserSystemInfo`, and extended `ReqUserLogin(..., length, systemInfo)`.
   - CTP docs classify `RegisterUserSystemInfo` as relay multi-connection mode and `SubmitUserSystemInfo` as relay operator mode; direct-investor apps should not blindly use those relay-reporting calls.
   - `ReqUserLogin system_info_len=100` proves the probe passed terminal info bytes into login, but login success does not prove compliance reporting because `system_info_len=0` also logged in successfully.
   - Explicit `RegisterUserSystemInfo` with the current `DataCollectforMacOS` output returned `ret=-6`; session then logged in as `SessionID=1816074420`.
   - Explicit `SubmitUserSystemInfo` with the current `DataCollectforMacOS` output returned `ret=-6`; session then logged in as `SessionID=1820006595`.
   - Empty-system-info control logged in as `SessionID=1822628046`.
   - Treat `414xx/CP` terminal-reporting as unresolved until the broker confirms the AppType for `client_hermanna_1.0` and whether the printable `DataCollectforMacOS` `CollectData` can be passed directly to extended `ReqUserLogin`, or a linkable Mac `DataCollect.h`/library and raw `CTP_GetSystemInfo` bytes are required.
12. Current confirmed Stage283 result:
   - Broker confirmed `client_hermanna_1.0` AppType is direct investor.
   - Normal `414xx/CP` route should not proactively call relay APIs `RegisterUserSystemInfo` or `SubmitUserSystemInfo`.
   - Keep Stage282 `ret=-6` relay-call results as diagnostic evidence only.
   - The normal direct-investor path is extended `ReqUserLogin(req, request_id, systemInfoLen, systemInfo)`.
   - Remaining blocker is the `systemInfo` byte source/format: confirm whether printable `DataCollectforMacOS` `CollectData` can be passed directly, or whether the broker must provide Mac `DataCollect.h`/library or C++ demo to obtain raw `CTP_GetSystemInfo` bytes.

## Order Discipline

Default posture: dry-run first.

- A backtest, daily report, or shadow script must never directly call a real broker `send_order`.
- Do not submit a close order if SimNow confirms the account is flat and there is no matching position.
- If the strategy has historical shadow holdings but SimNow is flat, start SimNow virtual trading from the actual flat broker state and record the divergence.
- If risk is `review`, only close/reduce/reconcile orders can proceed.
- For first virtual execution after a connectivity change, use a 1-lot smoke test before normal strategy sizing.
- For broker-test smoke orders, prefer `CTP_SMOKE_ORDER_ENABLED=1`; legacy `SIMNOW_SMOKE_ORDER_ENABLED=1` is accepted only for old SimNow runs.
- Real-money execution is out of scope for this skill unless the user explicitly asks for a separate live-trading gate review.

## Reconciliation

After SimNow execution or a dry-run gate:

- Compare theoretical target position, SimNow position, submitted order, fills, cancel state, average fill price, slippage, missed orders, and abnormal returns.
- Mark whether account state is aligned, divergent but explainable, or fail-closed.
- Record all output files and the exact command line used.
- Do not silently fix divergence by backfilling positions.

## User-Facing Report

When reporting results, include:

- latest completed data date,
- AI pool month/source,
- risk level and what it permits,
- target signal list,
- CTP/SimNow account state,
- gate status,
- whether any order API was called,
- whether tonight/next session has actionable orders,
- output file paths,
- overfitting judgment,
- continued-value judgment,
- next step.

## Stop Conditions

Stop and ask or fail closed when:

- credentials are requested in chat,
- the command would send a real-money order,
- broker state is missing or stale,
- old `30w` Stage78 paths appear in an active execution route,
- `review` risk tries to open a new position,
- SimNow is flat but the proposed action is close-only,
- AI pool is stale and the user is asking for an executable order.
- smoke-order submit-cancel is requested without explicit test-environment confirmation, a fresh read-only snapshot, and the required confirmation text.
