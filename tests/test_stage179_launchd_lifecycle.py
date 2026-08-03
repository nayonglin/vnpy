from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
LAUNCHD_DIR = PORTFOLIO_DIR / "launchd"
SUPERVISOR = PORTFOLIO_DIR / "run_qmt_roll_stage930_official_live_c9_session_supervisor.sh"
CHILD_HELPER = PORTFOLIO_DIR / "run_qmt_roll_stage930_supervisor_child.py"


def _plist(name: str) -> dict[str, object]:
    with (LAUNCHD_DIR / name).open("rb") as handle:
        return plistlib.load(handle)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return bool(result.stdout.strip()) and not result.stdout.lstrip().startswith("Z")


class Stage179LaunchdLifecycleTest(unittest.TestCase):
    def test_c9_production_live_jobs_use_one_shared_runtime_and_exact_launcher(self) -> None:
        names = (
            "local.qmt-roll.official-live.15w.c9-production-live-day-session.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-night-session.plist",
        )
        payloads = [_plist(name) for name in names]
        self.assertEqual(2, len({item["Label"] for item in payloads}))
        runtime_roots: set[str] = set()
        output_roots: set[str] = set()
        signal_roots: set[str] = set()
        for payload in payloads:
            arguments = payload["ProgramArguments"]
            environment = payload["EnvironmentVariables"]
            self.assertTrue(
                arguments[1].endswith(
                    "run_qmt_roll_stage945_official_live_production_session_launcher.py"
                )
            )
            self.assertNotIn("run_qmt_roll_stage930", arguments[1])
            self.assertEqual("1", environment["OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED"])
            self.assertEqual("1", environment["OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED"])
            self.assertNotIn("CTP_PASSWORD", environment)
            self.assertNotIn("CTP_AUTH_CODE", environment)
            self.assertEqual({"SuccessfulExit": False}, payload["KeepAlive"])
            self.assertEqual(60, payload["ThrottleInterval"])
            self.assertEqual("Interactive", payload["ProcessType"])
            self.assertFalse(payload["AbandonProcessGroup"])
            runtime_roots.add(
                arguments[arguments.index("--stage179-runtime-root") + 1]
            )
            output_roots.add(environment["OFFICIAL_LIVE_OUTPUT_DIR"])
            signal_roots.add(environment["OFFICIAL_LIVE_SIGNAL_INPUT_DIR"])
        self.assertEqual(1, len(runtime_roots))
        self.assertEqual(1, len(output_roots))
        self.assertEqual(1, len(signal_roots))

    def test_production_support_jobs_are_serialized_and_never_enable_submit(self) -> None:
        names = (
            "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-health.plist",
        )
        payloads = {name: _plist(name) for name in names}
        expected_jobs = {
            names[0]: "day-close-readonly",
            names[1]: "postclose-precompute",
            names[2]: "postclose-report",
            names[3]: "monthly-ai-pool",
            names[4]: "health",
        }
        for name, payload in payloads.items():
            joined = " ".join(payload["ProgramArguments"])
            environment = payload.get("EnvironmentVariables", {})
            self.assertNotIn("--mode live-real", joined, name)
            self.assertNotIn("--submit-mode live-real", joined, name)
            self.assertNotIn(
                "OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED",
                environment,
                name,
            )
            self.assertNotIn(
                "OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED",
                environment,
                name,
            )
            self.assertFalse(
                any(str(key).startswith("CTP_") for key in environment),
                name,
            )
            self.assertEqual(
                "/Users/bytedance/Desktop/person/vnpy_production_live",
                payload["WorkingDirectory"],
                name,
            )
            self.assertTrue(
                payload["ProgramArguments"][1].endswith(
                    "run_qmt_roll_stage947_official_live_production_support_launcher.py"
                ),
                name,
            )
            self.assertEqual(
                ["--job", expected_jobs[name]],
                payload["ProgramArguments"][2:],
                name,
            )
        precompute = payloads[
            "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist"
        ]
        report = payloads[
            "local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist"
        ]
        monthly_retry = payloads[
            "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist"
        ]
        precompute_minutes = {
            item["Hour"] * 60 + item["Minute"]
            for item in precompute["StartCalendarInterval"]
        }
        report_minutes = {
            item["Hour"] * 60 + item["Minute"]
            for item in report["StartCalendarInterval"]
        }
        monthly_retry_minutes = {
            item["Hour"] * 60 + item["Minute"]
            for item in monthly_retry["StartCalendarInterval"]
        }
        self.assertEqual({16 * 60 + 35}, precompute_minutes)
        self.assertEqual({16 * 60 + 55}, report_minutes)
        self.assertEqual({18 * 60 + 20}, monthly_retry_minutes)

        health = payloads[
            "local.qmt-roll.official-live.15w.c9-production-live-health.plist"
        ]
        self.assertTrue(
            health["ProgramArguments"][1].endswith(
                "run_qmt_roll_stage947_official_live_production_support_launcher.py"
            )
        )
        health_minutes = {
            item["Hour"] * 60 + item["Minute"]
            for item in health["StartCalendarInterval"]
        }
        self.assertEqual({9 * 60 + 3, 13 * 60 + 33, 21 * 60 + 3}, health_minutes)

    def test_all_seven_production_plists_bind_exact_stable_root_and_labels(self) -> None:
        names = (
            "local.qmt-roll.official-live.15w.c9-production-live-day-session.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-night-session.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist",
            "local.qmt-roll.official-live.15w.c9-production-live-health.plist",
        )
        expected_root = "/Users/bytedance/Desktop/person/vnpy_production_live"
        payloads = [_plist(name) for name in names]
        self.assertEqual(7, len({payload["Label"] for payload in payloads}))
        self.assertEqual(
            {name.removesuffix(".plist") for name in names},
            {payload["Label"] for payload in payloads},
        )
        for payload in payloads:
            arguments = payload["ProgramArguments"]
            self.assertEqual("077", payload["Umask"])
            self.assertEqual(expected_root, payload["WorkingDirectory"])
            self.assertEqual(f"{expected_root}/.py311/bin/python", arguments[0])
            self.assertTrue(arguments[1].startswith(f"{expected_root}/"))
            self.assertFalse(
                any("ctp_live.local.env" in str(item) for item in arguments)
            )
            intervals = payload["StartCalendarInterval"]
            if isinstance(intervals, dict):
                intervals = [intervals]
            weekdays = {int(item["Weekday"]) for item in intervals}
            self.assertEqual({1, 2, 3, 4, 5}, weekdays)
            self.assertNotIn(6, weekdays)
    def test_invalid_pgid_handshake_attempts_fail_before_child_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            marker = temp / "daemon-started"
            daemon = temp / "marker_daemon.py"
            daemon.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[1]).write_text('started', encoding='utf-8')\n",
                encoding="utf-8",
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "STAGE930_PYTHON_PATH": sys.executable,
                    "STAGE930_DAEMON_SCRIPT": str(daemon),
                    "STAGE930_SUPERVISOR_CHILD_HELPER": str(CHILD_HELPER),
                    "STAGE930_SUPERVISOR_PGID_HANDSHAKE_ATTEMPTS": "invalid",
                    "STAGE930_LOG_DIR": str(temp),
                }
            )

            result = subprocess.run(
                [str(SUPERVISOR), str(marker)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=environment,
                timeout=5,
                check=False,
            )

        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("invalid PGID handshake attempts", result.stdout)
        self.assertFalse(marker.exists())

    def test_c9_readonly_jobs_are_isolated_and_never_enable_submit(self) -> None:
        names = (
            "local.qmt-roll.official-live.15w.c9-readonly-day-session.plist",
            "local.qmt-roll.official-live.15w.c9-readonly-night-session.plist",
        )
        payloads = [_plist(name) for name in names]

        self.assertEqual(2, len({item["Label"] for item in payloads}))
        self.assertEqual(
            {"day_am", "night"},
            {
                item["ProgramArguments"][
                    item["ProgramArguments"].index(
                        "--require-current-session-name"
                    )
                    + 1
                ]
                for item in payloads
            },
        )
        runtime_roots: list[str] = []
        output_roots: list[str] = []
        signal_input_roots: list[str] = []
        for payload in payloads:
            arguments = payload["ProgramArguments"]
            joined = " ".join(arguments)
            self.assertEqual("Interactive", payload["ProcessType"])
            self.assertEqual(15, payload["ExitTimeOut"])
            self.assertFalse(payload["AbandonProcessGroup"])
            self.assertIn("--execution-profile c9-15w", joined)
            self.assertIn("--mode dry-run", joined)
            self.assertIn("--submit-mode disabled", joined)
            self.assertIn("--runtime-profile production-readonly", joined)
            self.assertIn("--stage179-execution-mode warm", joined)
            self.assertIn("--release-manifest", joined)
            self.assertIn("--tick-refresh-mode stream", joined)
            self.assertNotIn("live-real", joined)
            self.assertNotIn("--confirm-live-real", joined)
            self.assertNotIn("--confirm-stage179-activation", joined)
            self.assertNotIn(
                "OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED",
                payload.get("EnvironmentVariables", {}),
            )
            runtime_root = arguments[arguments.index("--stage179-runtime-root") + 1]
            runtime_roots.append(runtime_root)
            output_roots.append(
                payload["EnvironmentVariables"]["OFFICIAL_LIVE_OUTPUT_DIR"]
            )
            signal_input_roots.append(
                payload["EnvironmentVariables"][
                    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR"
                ]
            )

        self.assertEqual(2, len(set(runtime_roots)))
        self.assertEqual(2, len(set(output_roots)))
        self.assertEqual(1, len(set(signal_input_roots)))
        self.assertTrue(
            all(signal_input_roots[0] != root for root in output_roots)
        )
        self.assertNotEqual(
            payloads[0]["StandardOutPath"], payloads[1]["StandardOutPath"]
        )
        self.assertNotEqual(
            payloads[0]["StandardErrorPath"], payloads[1]["StandardErrorPath"]
        )

    def test_stage372_postclose_job_precomputes_without_ctp_or_submit(self) -> None:
        payload = _plist(
            "local.qmt-roll.official-live.20w.stage372-postclose-precompute.plist"
        )
        arguments = payload["ProgramArguments"]
        joined = " ".join(arguments)

        self.assertEqual("Interactive", payload["ProcessType"])
        self.assertTrue(
            arguments[1].endswith(
                "run_qmt_roll_stage909_official_live_shadow_refresh_gate.py"
            )
        )
        self.assertIn("--execution-profile stage372-20w", joined)
        self.assertIn("--target-date-mode latest-completed", joined)
        self.assertIn("--mode run", joined)
        self.assertNotIn("stage903_official_live_phase_d_controller", joined)
        self.assertNotIn("readonly-refresh", joined)
        self.assertNotIn("intraday-tick", joined)
        self.assertNotIn("live-real", joined)
        self.assertNotIn("--confirm-live-real", joined)
        self.assertEqual(
            payload["EnvironmentVariables"][
                "OFFICIAL_LIVE_PHASE_D_SHADOW_REFRESH_ENABLED"
            ],
            "1",
        )
        self.assertEqual(payload["StartCalendarInterval"], {"Hour": 16, "Minute": 35})
        self.assertEqual(
            payload["EnvironmentVariables"]["OFFICIAL_LIVE_SIGNAL_INPUT_DIR"],
            "/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/stage179_stage372/signal-input",
        )

    def test_legacy_armed_c9_job_definitions_are_removed(self) -> None:
        for name in (
            "local.qmt-roll.official-live.15w.c9-day-session.plist",
            "local.qmt-roll.official-live.15w.c9-night-session.plist",
        ):
            with self.subTest(name=name):
                self.assertFalse((LAUNCHD_DIR / name).exists())

    def test_canary_paths_are_independent_and_have_no_live_submit(self) -> None:
        direct = _plist("local.qmt-roll.stage179.no-submit-direct.plist")
        supervisor = _plist("local.qmt-roll.stage179.no-submit-supervisor.plist")
        canonical_readonly = [
            _plist(
                "local.qmt-roll.official-live.15w.c9-readonly-day-session.plist"
            ),
            _plist(
                "local.qmt-roll.official-live.15w.c9-readonly-night-session.plist"
            ),
        ]

        canary_arguments = [direct["ProgramArguments"], supervisor["ProgramArguments"]]
        joined = [" ".join(arguments) for arguments in canary_arguments]
        canonical_readonly_text = " ".join(
            " ".join(item["ProgramArguments"]) for item in canonical_readonly
        )
        self.assertNotEqual(direct["Label"], supervisor["Label"])
        self.assertNotIn("StartCalendarInterval", direct)
        self.assertNotIn("StartCalendarInterval", supervisor)
        self.assertNotIn("RunAtLoad", direct)
        self.assertNotIn("RunAtLoad", supervisor)
        self.assertIn("--runtime-profile production-readonly", joined[0])
        self.assertIn("--runtime-profile offline", joined[1])
        self.assertTrue(all("live-real" not in item for item in joined))
        self.assertTrue(all("--submit-mode disabled" in item for item in joined))
        self.assertTrue(all("--execution-profile c9-15w" in item for item in joined))
        self.assertTrue(all("--release-manifest" in item for item in joined))
        self.assertTrue(
            all("--stage179-execution-mode warm" in item for item in joined)
        )

        roots: list[str] = []
        for arguments in canary_arguments:
            root_index = arguments.index("--stage179-runtime-root") + 1
            roots.append(arguments[root_index])
        self.assertEqual(2, len(set(roots)))
        self.assertTrue(all(root not in canonical_readonly_text for root in roots))
        output_roots = [
            item["EnvironmentVariables"]["OFFICIAL_LIVE_OUTPUT_DIR"]
            for item in (direct, supervisor)
        ]
        self.assertEqual(2, len(set(output_roots)))
        self.assertTrue(
            all(root not in canonical_readonly_text for root in output_roots)
        )
        self.assertNotEqual(direct["StandardOutPath"], supervisor["StandardOutPath"])
        self.assertNotEqual(direct["StandardErrorPath"], supervisor["StandardErrorPath"])

    def test_output_root_override_is_import_time_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["OFFICIAL_LIVE_OUTPUT_DIR"] = directory
            environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        f"sys.path.insert(0, {str(PORTFOLIO_DIR)!r}); "
                        "from run_qmt_alignment_backtest import OUTPUT_DIR; "
                        "print(OUTPUT_DIR)"
                    ),
                ],
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )
        self.assertEqual(str(Path(directory).resolve()), result.stdout.strip())

    def test_phase_d_runtime_and_stage901_signal_roots_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            output_root = temp / "official-live"
            signal_root = temp / "signal-input"
            environment = dict(os.environ)
            environment.update(
                {
                    "OFFICIAL_LIVE_OUTPUT_DIR": str(output_root),
                    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(signal_root),
                    "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1",
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json,sys; "
                        f"sys.path.insert(0, {str(PORTFOLIO_DIR)!r}); "
                        "import qmt_roll_official_live_phase_d_config as c; "
                        "print(json.dumps({"
                        "'output': str(c.OUTPUT_DIR), "
                        "'pending': str(c.STAGE901_PENDING_ORDERS_PATH), "
                        "'trades': str(c.STAGE901_TRADES_PATH), "
                        "'risk': str(c.STAGE901_ENTRY_RISK_PATH)}))"
                    ),
                ],
                text=True,
                capture_output=True,
                env=environment,
                check=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(str(output_root.resolve()), payload["output"])
        for key in ("pending", "trades", "risk"):
            self.assertTrue(
                Path(payload[key]).is_relative_to(signal_root.resolve()),
                payload,
            )

    def test_cooperative_child_exits_on_term_without_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            daemon_path = temp / "cooperative.py"
            ready_path = temp / "cooperative.ready"
            daemon_path.write_text(
                "from pathlib import Path\n"
                "import signal,sys,time\n"
                "stop = False\n"
                "def request_stop(*_):\n"
                "    global stop\n"
                "    stop = True\n"
                "signal.signal(signal.SIGTERM, request_stop)\n"
                "Path(sys.argv[1]).write_text('ready', encoding='utf-8')\n"
                "while not stop:\n"
                "    time.sleep(0.01)\n",
                encoding="utf-8",
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "STAGE930_PYTHON_PATH": sys.executable,
                    "STAGE930_DAEMON_SCRIPT": str(daemon_path),
                    "STAGE930_SUPERVISOR_CHILD_HELPER": str(CHILD_HELPER),
                    "STAGE930_SUPERVISOR_TERM_TIMEOUT_SECONDS": "1",
                    "STAGE930_SUPERVISOR_KILL_WAIT_SECONDS": "1",
                    "STAGE930_LOG_DIR": str(temp),
                }
            )
            supervisor = subprocess.Popen(
                [str(SUPERVISOR), str(ready_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=environment,
            )
            deadline = time.monotonic() + 5
            while not ready_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(
                ready_path.exists(), "cooperative daemon never became signal-ready"
            )
            supervisor.send_signal(signal.SIGTERM)
            output, _ = supervisor.communicate(timeout=4)

        self.assertEqual(143, supervisor.returncode, output)
        self.assertNotIn("escalating PGID", output)
        self.assertEqual(1, output.count("starting daemon"), output)

    def test_term_ignoring_child_and_grandchild_are_killed_without_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            state_path = temp / "pids.json"
            daemon_path = temp / "ignore_term.py"
            daemon_path.write_text(
                """
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGINT, signal.SIG_IGN)
grandchild = subprocess.Popen([
    sys.executable,
    "-c",
    "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.signal(signal.SIGINT, signal.SIG_IGN); time.sleep(300)",
])
Path(sys.argv[1]).write_text(json.dumps({
    "child": os.getpid(),
    "pgid": os.getpgid(0),
    "grandchild": grandchild.pid,
}), encoding="utf-8")
while True:
    time.sleep(1)
""".lstrip(),
                encoding="utf-8",
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "STAGE930_PYTHON_PATH": sys.executable,
                    "STAGE930_DAEMON_SCRIPT": str(daemon_path),
                    "STAGE930_SUPERVISOR_CHILD_HELPER": str(CHILD_HELPER),
                    "STAGE930_SUPERVISOR_TERM_TIMEOUT_SECONDS": "0.3",
                    "STAGE930_SUPERVISOR_KILL_WAIT_SECONDS": "1",
                    "STAGE930_SUPERVISOR_RESTART_DELAY_SECONDS": "0.1",
                    "STAGE930_SUPERVISOR_MAX_RESTARTS": "3",
                    "STAGE930_LOG_DIR": str(temp),
                }
            )
            supervisor = subprocess.Popen(
                [str(SUPERVISOR), str(state_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=environment,
            )
            def cleanup() -> None:
                if supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait(timeout=2)
                if state_path.exists():
                    published = json.loads(state_path.read_text(encoding="utf-8"))
                    try:
                        os.killpg(int(published["pgid"]), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

            self.addCleanup(cleanup)
            deadline = time.monotonic() + 5
            while not state_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(state_path.exists(), "daemon never published child PIDs")
            pids = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(pids["child"], pids["pgid"])

            supervisor.send_signal(signal.SIGTERM)
            output, _ = supervisor.communicate(timeout=5)

            self.assertEqual(143, supervisor.returncode, output)
            self.assertFalse(_process_alive(pids["child"]), output)
            self.assertFalse(_process_alive(pids["grandchild"]), output)
            self.assertEqual(1, output.count("starting daemon"), output)
            self.assertIn("escalating PGID", output)


if __name__ == "__main__":
    unittest.main()
