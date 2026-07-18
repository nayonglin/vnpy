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
    def test_stage372_readonly_jobs_are_isolated_and_never_enable_submit(self) -> None:
        names = (
            "local.qmt-roll.official-live.20w.stage372-day-session.plist",
            "local.qmt-roll.official-live.20w.stage372-night-session.plist",
        )
        payloads = [_plist(name) for name in names]
        c9_text = " ".join(
            " ".join(
                _plist(name)["ProgramArguments"]
            )
            for name in (
                "local.qmt-roll.official-live.15w.c9-day-session.plist",
                "local.qmt-roll.official-live.15w.c9-night-session.plist",
            )
        )

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
            self.assertIn("--execution-profile stage372-20w", joined)
            self.assertIn("--mode dry-run", joined)
            self.assertIn("--submit-mode disabled", joined)
            self.assertIn("--runtime-profile production-readonly", joined)
            self.assertIn("--stage179-execution-mode warm", joined)
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
            self.assertNotIn(runtime_root, c9_text)
            self.assertNotIn(output_roots[-1], c9_text)

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

    def test_production_session_jobs_keep_direct_python_owner(self) -> None:
        for name in (
            "local.qmt-roll.official-live.15w.c9-day-session.plist",
            "local.qmt-roll.official-live.15w.c9-night-session.plist",
        ):
            with self.subTest(name=name):
                payload = _plist(name)
                arguments = payload["ProgramArguments"]
                self.assertTrue(arguments[0].endswith("/.py311/bin/python"))
                self.assertTrue(
                    arguments[1].endswith(
                        "run_qmt_roll_stage930_official_live_c9_session_daemon.py"
                    )
                )
                self.assertEqual(15, payload["ExitTimeOut"])
                self.assertFalse(payload["AbandonProcessGroup"])
                joined = " ".join(arguments)
                self.assertNotIn("--stage179-execution-mode", joined)
                self.assertNotIn("--confirm-stage179-activation", joined)

    def test_canary_paths_are_independent_and_have_no_live_submit(self) -> None:
        direct = _plist("local.qmt-roll.stage179.no-submit-direct.plist")
        supervisor = _plist("local.qmt-roll.stage179.no-submit-supervisor.plist")
        production = [
            _plist("local.qmt-roll.official-live.15w.c9-day-session.plist"),
            _plist("local.qmt-roll.official-live.15w.c9-night-session.plist"),
        ]

        canary_arguments = [direct["ProgramArguments"], supervisor["ProgramArguments"]]
        joined = [" ".join(arguments) for arguments in canary_arguments]
        production_text = " ".join(
            " ".join(item["ProgramArguments"]) for item in production
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

        roots: list[str] = []
        for arguments in canary_arguments:
            root_index = arguments.index("--stage179-runtime-root") + 1
            roots.append(arguments[root_index])
        self.assertEqual(2, len(set(roots)))
        self.assertTrue(all(root not in production_text for root in roots))
        output_roots = [
            item["EnvironmentVariables"]["OFFICIAL_LIVE_OUTPUT_DIR"]
            for item in (direct, supervisor)
        ]
        self.assertEqual(2, len(set(output_roots)))
        self.assertTrue(all(root not in production_text for root in output_roots))
        self.assertNotEqual(direct["StandardOutPath"], supervisor["StandardOutPath"])
        self.assertNotEqual(direct["StandardErrorPath"], supervisor["StandardErrorPath"])

    def test_output_root_override_is_import_time_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["OFFICIAL_LIVE_OUTPUT_DIR"] = directory
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

    def test_cooperative_child_exits_on_term_without_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            daemon_path = temp / "cooperative.py"
            daemon_path.write_text(
                "import signal,time\n"
                "stop = False\n"
                "def request_stop(*_):\n"
                "    global stop\n"
                "    stop = True\n"
                "signal.signal(signal.SIGTERM, request_stop)\n"
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
                [str(SUPERVISOR)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=environment,
            )
            time.sleep(0.2)
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
