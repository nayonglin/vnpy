"""Extended history contracts: real normalization/files, fake API boundary only."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def history(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root.parents[2]))
    spec = importlib.util.spec_from_file_location("examples.stock_backtesting.qmt357.history_under_test", root / "history_download.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DOWNLOADS_DIR", tmp_path / "data" / "downloads")
    return module


def bars(dates, code="sh.600000", st="0"):
    return pd.DataFrame([dict(date=date, code=code, open="10", high="10", low="10", close="10", preclose="10", volume="100", tradestatus="1", isST=st) for date in dates])


class Response:
    error_code = "0"
    error_msg = "success"

    def __init__(self, frame):
        self.fields = list(frame.columns)
        self.rows = frame.astype(str).values.tolist()
        self.index = -1

    def next(self):
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self):
        return self.rows[self.index]


class Client:
    def login(self):
        return Response(pd.DataFrame())

    def logout(self):
        return Response(pd.DataFrame())

    def query_hs300_stocks(self, date):
        rows = [dict(updateDate=date, code="sh.600000", code_name="浦发银行")]
        rows += [dict(updateDate=date, code=f"sz.{300000+i}", code_name="excluded") for i in range(299)]
        return Response(pd.DataFrame(rows))


@pytest.mark.parametrize("code", ["sh.600000", "sz.000001"])
def test_mainboard_st_limit_switches_on_actual_effective_date(history, code):
    # A constant 5%/10% implementation gives the wrong side of July 6.
    out = history.normalize_stock(bars(["2026-07-03", "2026-07-06"], code, "1"), pd.DataFrame(), pd.DataFrame())
    assert out.limit_up.tolist() == [10.5, 11.0]
    assert out.limit_down.tolist() == [9.5, 9.0]


@pytest.mark.parametrize("st,prior_up,prior_down", [("0", 11., 9.), ("1", 10.5, 9.5)])
def test_chinext_twenty_percent_begins_august_24_2020(history, st, prior_up, prior_down):
    out = history.normalize_stock(bars(["2020-08-21", "2020-08-24", "2026-07-06"], "sz.301236", st), pd.DataFrame(), pd.DataFrame())
    assert out.limit_up.tolist() == [prior_up, 12., 12.]
    assert out.limit_down.tolist() == [prior_down, 8., 8.]


def test_suspended_day_keeps_prices_and_cash_event_with_zero_volume(history):
    raw = bars(["2024-07-24", "2024-07-25"])
    raw.loc[1, ["tradestatus", "volume"]] = ["0", ""]
    events = pd.DataFrame([dict(date="2024-07-25", cash_dividend=.15, split_ratio=1.)])
    factors = pd.DataFrame([dict(dividOperateDate="2024-07-25", backAdjustFactor="1.02")])
    out = history.normalize_stock(raw, factors, events)
    assert out.volume.tolist() == [100., 0.]
    assert out.close.tolist() == [10., 10.]
    assert out.cash_dividend.tolist() == [0., .15]
    assert out.adj_factor.tolist() == [1., 1.02]
    assert history.audit_factor_gaps(out).empty


@pytest.mark.parametrize("column,value", [("volume", ""), ("isST", ""), ("tradestatus", "unknown"), ("preclose", "0"), ("open", "")])
def test_unknown_trading_fields_never_become_valid_bars(history, column, value):
    raw = bars(["2024-01-02"])
    raw.loc[0, column] = value
    with pytest.raises(ValueError):
        history.normalize_stock(raw, pd.DataFrame(), pd.DataFrame())


def test_factor_jump_without_action_is_audited_not_repaired(history):
    factors = pd.DataFrame([dict(dividOperateDate="2025-02-18", backAdjustFactor="5.975678")])
    out = history.normalize_stock(bars(["2025-02-17", "2025-02-18"], "sz.302132"), factors, pd.DataFrame())
    gap = history.audit_factor_gaps(out)
    assert len(gap) == 1
    assert gap.iloc[0].previous_factor == 1.
    assert gap.iloc[0].adj_factor == 5.975678
    assert out.split_ratio.tolist() == [1., 1.]


def test_year_segments_are_bounded_without_overlap(history):
    assert history.year_segments("20191001", "20210103") == [("2019-10-01", "2019-12-31"), ("2020-01-01", "2020-12-31"), ("2021-01-01", "2021-01-03")]


def test_retry_failure_cannot_be_cached_as_empty_success(history):
    path = history.DOWNLOADS_DIR / "test" / "bad.parquet"
    class Failed:
        error_code = "9"
        error_msg = "network failed"
        fields = []
    with pytest.raises(RuntimeError, match="network failed"):
        history.fetch_cached(path, lambda: Failed(), attempts=2)
    assert not path.exists()


def test_successful_retry_is_readable_offline_from_separate_cache(history):
    path = history.DOWNLOADS_DIR / "test" / "ok.parquet"
    attempts = []
    def transport():
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("temporary")
        return Response(pd.DataFrame([dict(date="2026-09-24", close="10")]))
    frame = history.fetch_cached(path, transport, attempts=2)
    assert frame.iloc[0].close == "10"
    def offline():
        raise RuntimeError("must not contact network for cache hit")
    assert history.fetch_cached(path, offline).equals(frame)


def test_cache_path_escape_does_not_touch_external_file(history, tmp_path):
    outside = tmp_path / "outside.parquet"
    with pytest.raises(ValueError):
        history.fetch_cached(outside, lambda: Response(pd.DataFrame()))
    assert not outside.exists()


def test_membership_is_collected_before_stock_bars_with_original_exclusions(history):
    directory, membership, symbols = history.collect_membership("20191001", "20200102", Client())
    assert directory.name == "history_20191001_20200102"
    assert symbols == ["sh.600000"]
    assert len(membership) == 1500
    manifest = json.loads((directory / "download_manifest.json").read_text())
    assert manifest["state"] == "membership_ready"
    assert manifest["snapshots"] == 5
    assert manifest["historical_union_stocks"] == 1


def test_completed_source_is_never_overwritten(history):
    directory = history.DOWNLOADS_DIR / "history_20191001_20200102"
    directory.mkdir(parents=True)
    target = directory / "source_panel.parquet"
    target.write_bytes(b"frozen source")
    with pytest.raises(FileExistsError):
        history.collect_membership("20191001", "20200102", Client())
    assert target.read_bytes() == b"frozen source"


class FullClient(Client):
    def query_history_k_data_plus(self, code, fields, start_date, end_date, frequency, adjustflag):
        if frequency != "d" or adjustflag != "3":
            raise ValueError("This source contract is raw daily prices")
        frame = bars(["2024-07-24", "2024-07-25", "2024-07-26"], code)
        if code == "sh.600000":
            frame.loc[1, ["tradestatus", "volume"]] = ["0", ""]
        frame = frame.loc[frame.date.between(start_date, end_date), fields.split(",")]
        return Response(frame)

    def query_adjust_factor(self, code, start_date, end_date):
        return Response(pd.DataFrame([dict(code=code, dividOperateDate="2024-07-25", backAdjustFactor="1.015")]))

    def query_dividend_data(self, code, year, yearType):
        return Response(pd.DataFrame(columns=["code", "dividOperateDate", "dividCashPsBeforeTax", "dividStocksPs", "dividReserveToStockPs"]))


def seed_sina_cache(history):
    directory = history.DOWNLOADS_DIR / "history_20240724_20240728"
    cache = directory / "raw" / "sina"
    cache.mkdir(parents=True)
    pd.DataFrame([{"公告日期": "2024-07-18", "送股": "0", "转增": "0", "派息": "1.5", "进度": "实施", "除权除息日": "2024-07-25", "股权登记日": "2024-07-24", "红股上市日": "--"}]).to_parquet(cache / "sina_actions_600000.parquet", index=False)
    return directory


def test_full_download_keeps_suspended_action_and_freezes_effective_index_end(history):
    directory = seed_sina_cache(history)
    output = history.download_panel("20240724", "20240728", client=FullClient())
    assert output == directory / "source_panel.parquet"
    frame = pd.read_parquet(output)
    assert len(frame) == 6
    stock = frame.loc[frame.vt_symbol.eq("600000.SSE")]
    assert stock.volume.tolist() == [100., 0., 100.]
    assert stock.cash_dividend.tolist() == [0., .15, 0.]
    assert frame.attrs["effective_end"] == "2024-07-26"
    assert frame.attrs["requested_end"] == "2024-07-28"
    assert "suspended_rows_omitted" not in frame.attrs["data_limitations"]
    assert pd.read_parquet(directory / "factor_gaps.parquet").empty
    audit = json.loads((directory / "action_audits" / "sh.600000.json").read_text())
    assert audit["sina_only_count"] == 1
    assert json.loads((directory / "download_manifest.json").read_text())["state"] == "complete"


def test_second_full_download_refuses_to_overwrite_frozen_source(history):
    seed_sina_cache(history)
    output = history.download_panel("20240724", "20240728", client=FullClient())
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        history.download_panel("20240724", "20240728", client=FullClient())
    assert output.read_bytes() == before


def test_successful_resume_archives_previous_errors_and_reports_current_empty(history):
    directory = seed_sina_cache(history)
    previous = b'[{"code":"sh.600000","error":"previous attempt failure"}]\n'
    (directory / "download_errors.json").write_bytes(previous)
    history.download_panel("20240724", "20240728", client=FullClient())
    manifest = json.loads((directory / "download_manifest.json").read_text())
    assert manifest["attempt_id"]
    assert manifest["current_failures"] == []
    assert json.loads((directory / "download_errors.json").read_text()) == []
    assert len(manifest["historical_failure_reports"]) == 1
    archived = directory / manifest["historical_failure_reports"][0]
    assert archived.read_bytes() == previous


def test_full_download_fails_if_stock_date_is_absent_from_index_calendar(history):
    directory = seed_sina_cache(history)
    class MissingIndex(FullClient):
        def query_history_k_data_plus(self, code, **kwargs):
            result = super().query_history_k_data_plus(code, **kwargs)
            if code == "sh.000300":
                result.rows = [row for row in result.rows if row[0] != "2024-07-25"]
            return result
    with pytest.raises(ValueError, match="index calendar"):
        history.download_panel("20240724", "20240728", client=MissingIndex())
    assert not (directory / "source_panel.parquet").exists()


def test_cache_symlink_never_reads_or_writes_external_resource(history, tmp_path):
    root = history.DOWNLOADS_DIR / "raw"
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "redirect").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        history.fetch_cached(root / "redirect" / "data.parquet", lambda: Response(pd.DataFrame()))
    assert not list(outside.iterdir())


def test_request_deadline_is_bounded_and_restored(history):
    import signal
    import time
    before = signal.getsignal(signal.SIGALRM)
    with pytest.raises(RuntimeError, match="deadline"):
        history.fetch_cached(history.DOWNLOADS_DIR / "slow.parquet", lambda: time.sleep(.1), attempts=1, timeout=.01)
    assert signal.getsignal(signal.SIGALRM) == before
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_positive_volume_on_suspended_bar_is_rejected_not_traded(history):
    raw = bars(["2024-07-25"])
    raw["tradestatus"] = "0"
    with pytest.raises(ValueError, match="suspended"):
        history.normalize_stock(raw, pd.DataFrame(), pd.DataFrame())


def test_logout_failure_still_restores_process_socket_default(history):
    import socket
    seed_sina_cache(history)
    class LogoutFailure(FullClient):
        def logout(self):
            raise RuntimeError("logout failed")
    before = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(13.)
        with pytest.raises(RuntimeError, match="logout failed"):
            history.download_panel("20240724", "20240728", client=LogoutFailure())
        assert socket.getdefaulttimeout() == 13.
    finally:
        socket.setdefaulttimeout(before)


def child_code(history, directory, body):
    repository = Path(__file__).resolve().parents[4]
    return f"import sys; sys.path.insert(0,{str(repository)!r})\nfrom pathlib import Path\nimport pandas as pd\nfrom examples.stock_backtesting.qmt357 import history_download as h\nh.DOWNLOADS_DIR=Path({str(history.DOWNLOADS_DIR)!r})\ndirectory=Path({str(directory)!r})\n" + body


def test_two_processes_same_stock_share_one_safe_api_cache(history, tmp_path):
    import os
    import subprocess
    import sys
    directory = history.DOWNLOADS_DIR / "history_20240724_20240728"
    directory.mkdir(parents=True)
    script = child_code(history, directory, """
import time
class Response:
 error_code='0';error_msg='success';fields=['value']
 def __init__(self): self.i=0
 def next(self): self.i+=1; return self.i==1
 def get_row_data(self): return ['verified']
def transport():
 with (directory/'api_calls.log').open('a') as log: log.write('api\\n')
 time.sleep(.15)
 return Response()
with h.stock_lock(directory,'sh.600000',timeout=5):
 frame=h.fetch_cached(directory/'raw'/'same.parquet',transport)
 assert frame.iloc[0]['value']=='verified'
""")
    env = dict(os.environ, QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD="1")
    children = [subprocess.Popen([sys.executable, "-I", "-c", script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = [child.communicate(timeout=15) for child in children]
    assert [child.returncode for child in children] == [0, 0], results
    assert (directory / "api_calls.log").read_text().splitlines() == ["api"]
    assert pd.read_parquet(directory / "raw" / "same.parquet").iloc[0]["value"] == "verified"


def test_contended_stock_lock_has_finite_timeout(history):
    import os
    import subprocess
    import sys
    directory = history.DOWNLOADS_DIR / "locked"
    script = child_code(history, directory, "with h.stock_lock(directory,'sh.600000',timeout=.05):\n raise AssertionError('must not enter held lock')\n")
    with history.stock_lock(directory, "sh.600000", timeout=1):
        result = subprocess.run([sys.executable, "-I", "-c", script], env=dict(os.environ, QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD="1"), capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "TimeoutError" in result.stderr
    assert "must not enter" not in result.stderr


def test_prefetch_writes_only_raw_and_separate_progress_not_main_manifest(history):
    directory = seed_sina_cache(history)
    history.collect_membership("20240724", "20240728", FullClient())
    manifest = (directory / "download_manifest.json").read_bytes()
    progress = history.prefetch_raw("20240724", "20240728", offset=0, client=FullClient())
    assert json.loads(progress.read_text())["complete_stocks"] == 1
    assert (directory / "download_manifest.json").read_bytes() == manifest
    assert not (directory / "events").exists()
    assert not (directory / "action_audits").exists()
    assert not (directory / "source_panel.parquet").exists()
    assert (directory / "raw" / "bars_sh.600000_2024-07-24_2024-07-28.parquet").is_file()


def test_public_share_resolution_requires_security_identity_in_integration(history):
    directory = history.DOWNLOADS_DIR / "history_20200618_20200619"
    cache = directory / "raw" / "sina"
    cache.mkdir(parents=True)
    pd.DataFrame([{"公告日期": "2020-06-12", "送股": "0", "转增": "0", "派息": "1.8", "进度": "实施", "除权除息日": "2020-06-19", "股权登记日": "2020-06-18", "红股上市日": "--"}]).to_parquet(cache / "sina_actions_600025.parquet", index=False)
    class DifferentialDividend(FullClient):
        def query_hs300_stocks(self, date):
            result = super().query_hs300_stocks(date)
            result.rows[0][1] = "sh.600025"
            return result

        def query_history_k_data_plus(self, code, fields, **kwargs):
            return Response(bars(["2020-06-18", "2020-06-19"], code)[fields.split(",")])

        def query_adjust_factor(self, **kwargs):
            return Response(pd.DataFrame())

        def query_dividend_data(self, **kwargs):
            return Response(pd.DataFrame([dict(dividOperateDate="2020-06-19", dividCashPsBeforeTax="0.14913", dividStocksPs="0", dividReserveToStockPs="")]))
    panel = pd.read_parquet(history.download_panel("20200618", "20200619", client=DifferentialDividend()))
    assert panel.loc[panel.vt_symbol.eq("600025.SSE"), "cash_dividend"].tolist() == [0., .18]
    assert panel.attrs["action_resolution_count"] == 1
    assert json.loads((directory / "action_audits" / "sh.600025.json").read_text())["action_resolution_count"] == 1
