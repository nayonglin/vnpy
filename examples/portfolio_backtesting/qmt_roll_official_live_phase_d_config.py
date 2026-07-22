from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(
    os.environ.get(
        "OFFICIAL_LIVE_OUTPUT_DIR",
        str(PROJECT_DIR / "backtest_outputs"),
    )
).expanduser().resolve(strict=False)
SIGNAL_INPUT_DIR = Path(
    os.environ.get(
        "OFFICIAL_LIVE_SIGNAL_INPUT_DIR",
        str(OUTPUT_DIR),
    )
).expanduser().resolve(strict=False)


PHASE_D_REAL_ENABLED_ENV = "OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED"
PHASE_D_SESSION_DAEMON_ENV = "OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED"
PHASE_D_REAL_ADAPTER_ENV = "OFFICIAL_LIVE_PHASE_D_REAL_ADAPTER_IMPLEMENTED"
PHASE_D_READONLY_REFRESH_ENV = "OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED"
PHASE_D_SHADOW_REFRESH_ENV = "OFFICIAL_LIVE_PHASE_D_SHADOW_REFRESH_ENABLED"
PHASE_D_CONFIRM_TEXT = "I_UNDERSTAND_THIS_ENABLES_FULL_AUTO_CTP_LIVE_TRADING"
PHASE_D_READONLY_REFRESH_CONFIRM_TEXT = "I_UNDERSTAND_THIS_RUNS_CTP_READONLY_REFRESH_ONLY"
PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT = "I_UNDERSTAND_THIS_RUNS_OFFICIAL_SHADOW_REFRESH"
PHASE_D_LIVE_REAL_POLICY_ENABLED_VALUE = "explicit_live_real_enabled"
PHASE_D_LIVE_REAL_POLICY_DISABLED_VALUE = "fail_closed"
STAGE179_ACTIVATION_ENV = "OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED"
STAGE179_ACTIVATION_CONFIRM_TEXT = (
    "I_UNDERSTAND_THIS_ACTIVATES_STAGE179_WARM_CTP_EXECUTION"
)
STAGE179_ACTIVATION_RECEIPT_SCHEMA_VERSION = 2

READONLY_SUMMARY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"
)
READONLY_QUERY_BUNDLE_MANIFEST_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage174_ctp_vnpy_readonly_probe_query_bundle_manifest_"
    "stage174_ctp_vnpy_readonly_probe_v1.json"
)
STAGE901_PENDING_ORDERS_PATH = (
    SIGNAL_INPUT_DIR
    / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
STAGE901_TRADES_PATH = (
    SIGNAL_INPUT_DIR
    / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_trades_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
STAGE901_ENTRY_RISK_PATH = (
    SIGNAL_INPUT_DIR
    / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_risk_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
READONLY_TICKS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_ticks_stage608_readonly_tick_snapshot_probe_v1.csv"
)
READONLY_CONTRACTS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_contracts_stage174_ctp_vnpy_readonly_probe_v1.csv"
)
READONLY_POSITIONS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_positions_stage174_ctp_vnpy_readonly_probe_v1.csv"
)
READONLY_ORDERS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv"
)
READONLY_TRADES_PATH = (
    OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_trades_stage174_ctp_vnpy_readonly_probe_v1.csv"
)
LIVE_EXECUTION_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_official_live_phase_d_execution_ledger.ndjson"
KILL_SWITCH_PATH = OUTPUT_DIR / "qmt_roll_official_live_phase_d_kill_switch.json"
CONTROLLER_HEARTBEAT_PATH = OUTPUT_DIR / "qmt_roll_official_live_phase_d_controller_heartbeat.json"
CONTROLLER_STATE_PATH = OUTPUT_DIR / "qmt_roll_official_live_phase_d_controller_state.json"


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start: str
    end: str
    role: str


@dataclass(frozen=True)
class PhaseDHardLimits:
    max_snapshot_age_seconds: int = 300
    max_tick_age_seconds: int = 10
    max_heartbeat_age_seconds: int = 60
    max_order_count_per_cycle: int = 3
    max_order_count_per_day: int = 12
    max_cancel_count_per_day: int = 20
    max_reject_count_per_day: int = 2
    max_single_order_volume: int = 20
    max_open_order_count: int = 0
    max_slippage_ticks: int = 5
    max_controller_cycle_seconds: int = 30
    max_executor_dequeue_seconds: float = 0.5
    max_dequeue_to_send_seconds: float = 20.0
    max_ingress_to_send_seconds: float = 25.0
    readiness_heartbeat_seconds: float = 1.0
    readiness_lease_ttl_seconds: float = 3.0
    executor_spool_poll_seconds: float = 0.1


@dataclass(frozen=True)
class PhaseDConfig:
    mode_default: str
    real_submit_default: str
    gateway_name: str
    sessions: tuple[SessionWindow, ...]
    hard_limits: PhaseDHardLimits
    kill_switch_path: Path
    heartbeat_path: Path
    state_path: Path


def build_phase_d_config() -> PhaseDConfig:
    return PhaseDConfig(
        mode_default="dry-run",
        real_submit_default=PHASE_D_LIVE_REAL_POLICY_DISABLED_VALUE,
        gateway_name="CTP",
        sessions=(
            SessionWindow("night", "20:55", "23:05", "market_and_execution"),
            SessionWindow("late_night", "23:05", "02:35", "market_and_execution"),
            SessionWindow("overnight_reconcile", "02:35", "08:55", "reconcile_and_watch"),
            SessionWindow("day_am", "08:55", "11:35", "market_and_execution"),
            SessionWindow("day_pm", "13:25", "15:10", "market_and_execution"),
            SessionWindow("post_close", "15:10", "20:55", "data_shadow_reconcile"),
        ),
        hard_limits=PhaseDHardLimits(),
        kill_switch_path=KILL_SWITCH_PATH,
        heartbeat_path=CONTROLLER_HEARTBEAT_PATH,
        state_path=CONTROLLER_STATE_PATH,
    )


def phase_d_config_to_dict(config: PhaseDConfig | None = None) -> dict[str, Any]:
    config = config or build_phase_d_config()
    row = asdict(config)
    for key in ("kill_switch_path", "heartbeat_path", "state_path"):
        row[key] = str(row[key])
    return row
