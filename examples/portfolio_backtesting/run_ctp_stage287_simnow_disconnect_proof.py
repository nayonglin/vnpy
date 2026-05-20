from __future__ import annotations

import argparse
import csv
import html
import json
import os
import socket
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TRADE


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage287_simnow_disconnect_proof_v1"
OUTPUT_PREFIX = "qmt_roll_stage287_simnow_disconnect_proof"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "evidence_html": OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_{run_id}_{MODEL_TAG}.html",
        "logs_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{run_id}_{MODEL_TAG}.csv",
        "proxy_events_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_events_{run_id}_{MODEL_TAG}.csv",
        "accounts_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{run_id}_{MODEL_TAG}.csv",
        "positions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{run_id}_{MODEL_TAG}.csv",
        "orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{run_id}_{MODEL_TAG}.csv",
        "trades_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{run_id}_{MODEL_TAG}.csv",
    }


def _parse_tcp_url(value: str) -> tuple[str, int]:
    parsed = urlparse(value)
    if parsed.scheme != "tcp" or not parsed.hostname or not parsed.port:
        raise ValueError(f"invalid CTP tcp address: {value!r}")
    return parsed.hostname, int(parsed.port)


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_accountid", "available"]:
        if hasattr(obj, attr):
            row[attr] = getattr(obj, attr)
    for key, value in list(row.items()):
        if isinstance(value, (datetime, pd.Timestamp)):
            row[key] = value.isoformat()
        elif hasattr(value, "value"):
            row[key] = value.value
        elif isinstance(value, (dict, list, tuple, set)):
            row[key] = json.dumps(value, ensure_ascii=False, default=str)
        elif value is None:
            row[key] = ""
    return row


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


class TcpCutProxy:
    """Tiny TCP forwarding proxy that can close active sockets to mimic a cable pull."""

    def __init__(self, name: str, target_host: str, target_port: int) -> None:
        self.name = name
        self.target_host = target_host
        self.target_port = target_port
        self.events: list[dict[str, Any]] = []
        self._sockets: list[socket.socket] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(8)
        self.local_host, self.local_port = self._server.getsockname()
        self._thread = threading.Thread(target=self._accept_loop, name=f"{name}-proxy", daemon=True)

    @property
    def local_url(self) -> str:
        return f"tcp://{self.local_host}:{self.local_port}"

    @property
    def target_url(self) -> str:
        return f"tcp://{self.target_host}:{self.target_port}"

    def start(self) -> None:
        self._event("proxy_started", local=self.local_url, target=self.target_url)
        self._thread.start()

    def cut(self, reason: str) -> None:
        self._event("cut_requested", reason=reason)
        self._stop.set()
        self._close_socket(self._server)
        with self._lock:
            sockets = list(self._sockets)
            self._sockets.clear()
        for sock in sockets:
            self._close_socket(sock)
        self._event("cut_completed", closed_sockets=len(sockets))

    def close(self) -> None:
        self.cut("cleanup")

    def _event(self, event: str, **payload: Any) -> None:
        row = {"time": _now(), "proxy": self.name, "event": event}
        row.update(payload)
        self.events.append(row)

    def _track(self, sock: socket.socket) -> None:
        with self._lock:
            self._sockets.append(sock)

    def _untrack(self, sock: socket.socket) -> None:
        with self._lock:
            try:
                self._sockets.remove(sock)
            except ValueError:
                pass

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                client, client_addr = self._server.accept()
            except OSError:
                break
            self._event("client_connected", client=f"{client_addr[0]}:{client_addr[1]}")
            try:
                upstream = socket.create_connection((self.target_host, self.target_port), timeout=10)
            except OSError as exc:
                self._event("upstream_connect_failed", error=repr(exc))
                self._close_socket(client)
                continue
            self._event("upstream_connected")
            self._track(client)
            self._track(upstream)
            threading.Thread(target=self._pipe, args=(client, upstream, "client_to_upstream"), daemon=True).start()
            threading.Thread(target=self._pipe, args=(upstream, client, "upstream_to_client"), daemon=True).start()

    def _pipe(self, source: socket.socket, target: socket.socket, direction: str) -> None:
        total = 0
        try:
            while not self._stop.is_set():
                data = source.recv(65536)
                if not data:
                    break
                total += len(data)
                target.sendall(data)
        except OSError as exc:
            self._event("pipe_error", direction=direction, error=repr(exc), bytes=total)
        finally:
            self._event("pipe_closed", direction=direction, bytes=total)
            self._close_socket(source)
            self._close_socket(target)
            self._untrack(source)
            self._untrack(target)

    @staticmethod
    def _close_socket(sock: socket.socket) -> None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


def _ctp_setting_from_env(td_url: str, md_url: str) -> dict[str, Any]:
    return {
        "用户名": os.getenv("CTP_USERID", ""),
        "密码": os.getenv("CTP_PASSWORD", ""),
        "经纪商代码": os.getenv("CTP_BROKERID", ""),
        "交易服务器": td_url,
        "行情服务器": md_url,
        "产品名称": os.getenv("CTP_APPID", ""),
        "授权编码": os.getenv("CTP_AUTH_CODE", ""),
        "产品信息": os.getenv("CTP_PRODUCT_INFO", ""),
    }


def _missing_env() -> list[str]:
    keys = ["CTP_USERID", "CTP_PASSWORD", "CTP_BROKERID", "CTP_TD_ADDRESS", "CTP_MD_ADDRESS", "CTP_APPID", "CTP_AUTH_CODE"]
    return [key for key in keys if not os.getenv(key, "")]


def _log_flags(logs: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [str(row.get("msg", "")) for row in logs]
    return {
        "td_connected": any("交易服务器连接成功" in msg for msg in messages),
        "md_connected": any("行情服务器连接成功" in msg for msg in messages),
        "td_auth_success": any("交易服务器授权验证成功" in msg for msg in messages),
        "td_login_success": any("交易服务器登录成功" in msg for msg in messages),
        "md_login_success": any("行情服务器登录成功" in msg for msg in messages),
        "settlement_confirmed": any("结算信息确认成功" in msg for msg in messages),
        "td_disconnected": any("交易服务器连接断开" in msg for msg in messages),
        "md_disconnected": any("行情服务器连接断开" in msg for msg in messages),
        "disconnect_messages": [msg for msg in messages if "连接断开" in msg],
    }


def _render_html(path: Path, summary: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    def card(label: str, value: Any, green: bool = False) -> str:
        klass = "value ok" if green else "value"
        return f"<div class='card'><div class='label'>{esc(label)}</div><div class='{klass}'>{esc(value)}</div></div>"

    def table(title: str, data: list[dict[str, Any]], columns: list[str] | None = None, limit: int = 24) -> str:
        if not data:
            return f"<h2>{esc(title)}</h2><p class='muted'>无记录</p>"
        selected = data[:limit]
        cols = columns or list(dict.fromkeys(key for row in selected for key in row.keys()))
        head = "".join(f"<th>{esc(col)}</th>" for col in cols)
        body = []
        for row in selected:
            body.append("<tr>" + "".join(f"<td>{esc(row.get(col, ''))}</td>" for col in cols) + "</tr>")
        more = "" if len(data) <= limit else f"<p class='muted'>仅展示前 {limit} 行，共 {len(data)} 行。</p>"
        return f"<h2>{esc(title)}</h2><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>{more}"

    flags = summary.get("log_flags", {})
    cards = [
        card("断网测试状态", summary.get("status", ""), green=summary.get("status") == "disconnect_observed"),
        card("交易登录", "成功" if flags.get("td_login_success") else "未确认", green=bool(flags.get("td_login_success"))),
        card("行情登录", "成功" if flags.get("md_login_success") else "未确认", green=bool(flags.get("md_login_success"))),
        card("交易断开回报", "已收到" if flags.get("td_disconnected") else "未收到", green=bool(flags.get("td_disconnected"))),
        card("行情断开回报", "已收到" if flags.get("md_disconnected") else "未收到", green=bool(flags.get("md_disconnected"))),
        card("订单API调用", "0 / 0"),
        card("远端交易前置", summary.get("remote_td_address", "")),
        card("远端行情前置", summary.get("remote_md_address", "")),
        card("本机交易代理", summary.get("proxy_td_address", "")),
        card("本机行情代理", summary.get("proxy_md_address", "")),
        card("切断时间", summary.get("cut_at", "")),
        card("测试环境", "SimNow 普通仿真 trading"),
    ]
    important_logs = [
        row
        for row in rows["logs"]
        if any(key in str(row.get("msg", "")) for key in ["连接成功", "登录成功", "授权验证成功", "结算信息确认成功", "连接断开"])
    ]
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>SimNow 程序化断网回调证明</title>
  <style>
    body {{ margin: 0; background: #f3f6fb; color: #142033; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .page {{ max-width: 1720px; margin: 32px auto; background: white; border: 1px solid #d7e1ee; padding: 28px; box-shadow: 0 18px 60px rgba(25, 49, 84, .08); }}
    h1 {{ font-size: 34px; margin: 0 0 10px; }}
    h2 {{ font-size: 24px; margin: 28px 0 12px; }}
    .sub {{ color: #5b6d86; font-size: 18px; margin-bottom: 22px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(220px, 1fr)); gap: 14px; }}
    .card {{ border: 1px solid #d6e0ec; border-radius: 8px; padding: 16px 18px; background: #fafcff; min-height: 76px; }}
    .label {{ color: #5b6d86; font-weight: 650; margin-bottom: 8px; }}
    .value {{ font-size: 22px; font-weight: 780; overflow-wrap: anywhere; }}
    .ok {{ color: #0f7b37; }}
    .muted {{ color: #62738a; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
    th, td {{ border: 1px solid #d9e2ee; padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #ebf1f8; }}
    .note {{ margin: 20px 0; color: #4d6078; font-size: 16px; }}
  </style>
</head>
<body>
  <main class="page">
    <h1>SimNow 程序化断网回调证明</h1>
    <div class="sub">生成时间：{esc(summary.get("generated_at", ""))} | 方法：本机 TCP 代理登录成功后主动切断连接 | 全程不调用订单 API</div>
    <section class="grid">{''.join(cards)}</section>
    <p class="note">说明：本测试没有关闭整台 Mac 网络，而是在 CTP API 与 SimNow 前置之间加一层本机代理；登录成功后关闭代理 socket，用来模拟运行中网线断开/网络中断。</p>
    {table("CTP关键日志", important_logs, ["time", "gateway_name", "msg", "level"])}
    {table("本机代理事件", rows["proxy_events"], ["time", "proxy", "event", "local", "target", "client", "reason", "closed_sockets", "direction", "bytes", "error"])}
    {table("账户快照", rows["accounts"], limit=8)}
    {table("持仓快照", rows["positions"], limit=12)}
    {table("委托/成交快照：应为空", rows["orders"] + rows["trades"], limit=12)}
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    flags = summary.get("log_flags", {})
    lines = [
        "# Stage287 SimNow 程序化断网回调证明",
        "",
        f"- 生成时间：{summary.get('generated_at', '')}",
        f"- 状态：`{summary.get('status', '')}`",
        f"- 交易登录成功：`{flags.get('td_login_success')}`",
        f"- 行情登录成功：`{flags.get('md_login_success')}`",
        f"- 交易断开回报：`{flags.get('td_disconnected')}`",
        f"- 行情断开回报：`{flags.get('md_disconnected')}`",
        "- 订单 API 调用：`0`",
        "- 撤单 API 调用：`0`",
        "",
        "## 断开回报",
        "",
    ]
    for msg in flags.get("disconnect_messages", []):
        lines.append(f"- `{msg}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(pre_disconnect_wait_seconds: int, post_disconnect_wait_seconds: int, stable_after_login_seconds: int) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = _run_id()
    paths = _paths(run_id)
    missing = _missing_env()
    if missing:
        summary = {
            "model_tag": MODEL_TAG,
            "run_id": run_id,
            "generated_at": _now(),
            "status": "blocked_missing_env",
            "missing_env": missing,
            "outputs": {key: str(value) for key, value in paths.items()},
        }
        paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    remote_td = os.getenv("CTP_TD_ADDRESS", "")
    remote_md = os.getenv("CTP_MD_ADDRESS", "")
    td_host, td_port = _parse_tcp_url(remote_td)
    md_host, md_port = _parse_tcp_url(remote_md)
    td_proxy = TcpCutProxy("td", td_host, td_port)
    md_proxy = TcpCutProxy("md", md_host, md_port)
    td_proxy.start()
    md_proxy.start()

    rows: dict[str, list[dict[str, Any]]] = {
        "logs": [],
        "accounts": [],
        "positions": [],
        "orders": [],
        "trades": [],
        "proxy_events": [],
    }
    from vnpy_ctp import CtpGateway

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_log(event: Any) -> None:
        row = _object_to_row(event.data)
        row["time"] = _now()
        rows["logs"].append(row)

    def append_row(name: str):
        def handler(event: Any) -> None:
            row = _object_to_row(event.data)
            row["time"] = _now()
            rows[name].append(row)

        return handler

    event_engine.register(EVENT_LOG, on_log)
    event_engine.register(EVENT_ACCOUNT, append_row("accounts"))
    event_engine.register(EVENT_POSITION, append_row("positions"))
    event_engine.register(EVENT_ORDER, append_row("orders"))
    event_engine.register(EVENT_TRADE, append_row("trades"))

    cut_at = ""
    try:
        main_engine.connect(_ctp_setting_from_env(td_proxy.local_url, md_proxy.local_url), "CTP")
        deadline = time.time() + max(pre_disconnect_wait_seconds, 1)
        login_ready = False
        while time.time() < deadline:
            flags = _log_flags(rows["logs"])
            login_ready = bool(flags["td_login_success"] and flags["md_login_success"])
            if login_ready:
                break
            time.sleep(0.5)
        time.sleep(max(stable_after_login_seconds, 0))
        cut_at = _now()
        td_proxy.cut("stage287_simulated_network_disconnect")
        md_proxy.cut("stage287_simulated_network_disconnect")
        time.sleep(max(post_disconnect_wait_seconds, 1))
    finally:
        rows["proxy_events"] = td_proxy.events + md_proxy.events
        try:
            main_engine.close()
        finally:
            td_proxy.close()
            md_proxy.close()
            rows["proxy_events"] = td_proxy.events + md_proxy.events

    log_flags = _log_flags(rows["logs"])
    status = "disconnect_observed" if (log_flags["td_disconnected"] or log_flags["md_disconnected"]) else "disconnect_not_observed"
    if not (log_flags["td_login_success"] and log_flags["md_login_success"]):
        status = "login_not_confirmed_before_cut"

    summary = {
        "model_tag": MODEL_TAG,
        "run_id": run_id,
        "generated_at": _now(),
        "status": status,
        "remote_td_address": remote_td,
        "remote_md_address": remote_md,
        "proxy_td_address": td_proxy.local_url,
        "proxy_md_address": md_proxy.local_url,
        "cut_at": cut_at,
        "pre_disconnect_wait_seconds": pre_disconnect_wait_seconds,
        "post_disconnect_wait_seconds": post_disconnect_wait_seconds,
        "stable_after_login_seconds": stable_after_login_seconds,
        "log_flags": log_flags,
        "row_counts": {key: len(value) for key, value in rows.items()},
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "outputs": {key: str(value) for key, value in paths.items()},
    }

    _write_df(paths["logs_csv"], rows["logs"])
    _write_df(paths["proxy_events_csv"], rows["proxy_events"])
    _write_df(paths["accounts_csv"], rows["accounts"])
    _write_df(paths["positions_csv"], rows["positions"])
    _write_df(paths["orders_csv"], rows["orders"])
    _write_df(paths["trades_csv"], rows["trades"])
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(paths["report_md"], summary)
    _render_html(paths["evidence_html"], summary, rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage287 SimNow disconnect proof via local TCP proxy. No orders are sent.")
    parser.add_argument("--pre-disconnect-wait-seconds", type=int, default=35)
    parser.add_argument("--stable-after-login-seconds", type=int, default=3)
    parser.add_argument("--post-disconnect-wait-seconds", type=int, default=25)
    args = parser.parse_args()
    summary = run(
        pre_disconnect_wait_seconds=int(args.pre_disconnect_wait_seconds),
        stable_after_login_seconds=int(args.stable_after_login_seconds),
        post_disconnect_wait_seconds=int(args.post_disconnect_wait_seconds),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
