from __future__ import annotations

import csv
import json
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage179_simnow_network_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage179_simnow_network_probe"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
CSV_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fronts_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


FRONTS = [
    {
        "front": "7x24_182",
        "role": "td",
        "address": "tcp://182.254.243.31:40001",
        "note": "SimNow 7x24 test trade front, 182 profile",
    },
    {
        "front": "7x24_182",
        "role": "md",
        "address": "tcp://182.254.243.31:40011",
        "note": "SimNow 7x24 test market front, 182 profile",
    },
    {
        "front": "trading",
        "role": "td",
        "address": "tcp://182.254.243.31:30001",
        "note": "SimNow first environment, group 1 trade front",
    },
    {
        "front": "trading",
        "role": "md",
        "address": "tcp://182.254.243.31:30011",
        "note": "SimNow first environment, group 1 market front",
    },
    {
        "front": "trading2",
        "role": "td",
        "address": "tcp://182.254.243.31:30002",
        "note": "SimNow first environment, group 2 trade front",
    },
    {
        "front": "trading2",
        "role": "md",
        "address": "tcp://182.254.243.31:30012",
        "note": "SimNow first environment, group 2 market front",
    },
    {
        "front": "trading_mobile",
        "role": "td",
        "address": "tcp://182.254.243.31:30003",
        "note": "SimNow first environment, group 3 trade front",
    },
    {
        "front": "trading_mobile",
        "role": "md",
        "address": "tcp://182.254.243.31:30013",
        "note": "SimNow first environment, group 3 market front",
    },
    {
        "front": "7x24_180",
        "role": "td",
        "address": "tcp://180.168.146.187:10130",
        "note": "SimNow 7x24 trade front from official/legacy docs",
    },
    {
        "front": "7x24_180",
        "role": "md",
        "address": "tcp://180.168.146.187:10131",
        "note": "SimNow 7x24 market front from official/legacy docs",
    },
    {
        "front": "first_180_group1",
        "role": "td",
        "address": "tcp://180.168.146.187:10201",
        "note": "SimNow first environment group 1 trade front from deployment pack",
    },
    {
        "front": "first_180_group1",
        "role": "md",
        "address": "tcp://180.168.146.187:10211",
        "note": "SimNow first environment group 1 market front from deployment pack",
    },
    {
        "front": "first_180_group2",
        "role": "td",
        "address": "tcp://180.168.146.187:10202",
        "note": "SimNow first environment group 2 trade front from deployment pack",
    },
    {
        "front": "first_180_group2",
        "role": "md",
        "address": "tcp://180.168.146.187:10212",
        "note": "SimNow first environment group 2 market front from deployment pack",
    },
]


@dataclass
class ProbeResult:
    front: str
    role: str
    address: str
    host: str
    port: int
    ok: bool
    elapsed_ms: int
    error: str
    note: str


def parse_tcp_address(address: str) -> tuple[str, int]:
    parsed = urlparse(address)
    if parsed.scheme and parsed.scheme != "tcp":
        raise ValueError(f"Unsupported scheme in {address}")
    if parsed.hostname and parsed.port:
        return parsed.hostname, int(parsed.port)
    raw = address.removeprefix("tcp://")
    host, port_text = raw.rsplit(":", 1)
    return host, int(port_text)


def probe(front: dict[str, str], timeout_seconds: float) -> ProbeResult:
    host, port = parse_tcp_address(front["address"])
    start = time.monotonic()
    ok = False
    error = ""
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            ok = True
    except Exception as exc:
        error = repr(exc)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return ProbeResult(
        front=front["front"],
        role=front["role"],
        address=front["address"],
        host=host,
        port=port,
        ok=ok,
        elapsed_ms=elapsed_ms,
        error=error,
        note=front["note"],
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    timeout_seconds = 5.0
    results = [probe(front, timeout_seconds=timeout_seconds) for front in FRONTS]
    rows = [asdict(result) for result in results]

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    reachable_fronts = sorted({result.front for result in results if result.ok})
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": generated_at,
        "timeout_seconds": timeout_seconds,
        "reachable_fronts": reachable_fronts,
        "all_tcp_reachable": all(result.ok for result in results),
        "any_tcp_reachable": any(result.ok for result in results),
        "results": rows,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "csv": str(CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Stage179 SimNow TCP 前置探针报告",
        "",
        f"- 生成时间：{generated_at}",
        f"- 超时阈值：{timeout_seconds:.1f}s",
        f"- 任一前置可达：{any(result.ok for result in results)}",
        f"- 可达 front：{', '.join(reachable_fronts) if reachable_fronts else '无'}",
        "",
        "| front | role | address | ok | elapsed_ms | error |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for result in results:
        error = result.error.replace("|", "\\|")
        lines.append(
            f"| {result.front} | {result.role} | `{result.address}` | "
            f"{result.ok} | {result.elapsed_ms} | `{error}` |"
        )
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "若全部不可达，优先换网络或等待 SimNow 服务窗口，而不是继续修改策略逻辑。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
