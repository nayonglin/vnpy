"""Stage062: display the frozen Stage060 full-history equity; never replay strategy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

LINE = Path(__file__).resolve().parents[1]
SOURCE = LINE / "outputs/stage060_s21_200k_touch_halfyear_20261104"
RUN = SOURCE / "S21_20w/2015-01-01"
OUT = LINE / "outputs/stage062_s21_200k_equity_2015_v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((OUT / "curve_data.json").read_text())
    summary = json.loads((RUN / "summary.json").read_text())
    daily = pd.read_csv(RUN / "daily.csv")
    assert sha(SOURCE / "SHA256SUMS") == frozen["source_manifest_sha256"]
    assert sha(RUN / "daily.csv") == frozen["source_daily_sha256"]
    assert sha(RUN / "summary.json") == frozen["source_summary_sha256"]
    assert summary == frozen["summary"]
    points = frozen["points"]
    assert len(daily) == len(points) == summary["days"] == 2875
    assert daily.date.iloc[0] == "2015-01-05"
    assert daily.date.iloc[-1] == "2026-11-04"
    assert daily.equity.iloc[-1] == summary["equity"] == 1249535
    assert summary["initial"] == daily.equity.iloc[0] == 200000
    assert abs(daily.net_pnl.sum() - summary["net_pnl"]) < 1e-7
    assert (daily.date == [p["date"] for p in points]).all()
    assert all(abs(e / 10000 - p["equity_wan"]) < 1e-10
               for e, p in zip(daily.equity, points))
    dd = (daily.equity / daily.equity.cummax() - 1) * 100
    assert all(abs(d - p["drawdown_pct"]) < 1e-8 for d, p in zip(dd, points))
    assert abs(dd.min() - summary["max_dd_pct"]) < 1e-8
    assert daily.loc[dd.idxmin(), "date"] == frozen["maximum_drawdown_date"]
    assert round(summary["return_pct"], 2) == 524.77
    assert round(summary["sharpe"], 3) == 0.802
    assert round(summary["max_dd_pct"], 2) == -39.73

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.74, 0.26], vertical_spacing=0.10,
                        subplot_titles=["账户权益（万元）", "历史高点回撤（%）"])
    fig.add_trace(go.Scatter(x=daily.date, y=daily.equity / 10000,
                            name="账户权益", line=dict(color="#215cab", width=2),
                            hovertemplate="%{x}<br>权益 %{y:.4f} 万元<extra></extra>"), row=1, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="#999", row=1, col=1)
    fig.add_trace(go.Scatter(x=daily.date, y=dd, name="回撤", fill="tozeroy",
                            line=dict(color="#c34042", width=1.5),
                            hovertemplate="%{x}<br>回撤 %{y:.2f}%<extra></extra>"), row=2, col=1)
    fig.update_layout(
        title=dict(text="21 品种 · 20 万元 · 回测资金曲线"
                        "<br><sup>2015-01-05 至 2026-11-04 · 周 K 信号 · 固定一手 · 全品种触价止损</sup>"),
        template="plotly_white", height=850, showlegend=False, hovermode="x unified",
        margin=dict(t=125, b=70, l=80, r=35),
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif", size=14),
    )
    fig.update_xaxes(dtick="M12", tickformat="%Y")
    fig.update_yaxes(range=[0, 140], row=1, col=1)
    fig.update_yaxes(range=[-45, 0], ticksuffix="%", row=2, col=1)
    fig.add_annotation(xref="paper", yref="paper", x=0, y=-0.12, showarrow=False,
                       text="已计滑点，手续费为零 · 日线 OHLC 模拟触价 · 含期末持仓市值 · Stage060 冻结账本")
    fig.write_html(OUT / "equity_curve.html", include_plotlyjs=True, config={"displaylogo": False})
    result = {
        "status": "PASS_FROZEN_CURVE_DISPLAY_ONLY",
        "daily_points": len(points), "start": summary["start"], "end": summary["end"],
        "equity": summary["equity"], "return_pct": summary["return_pct"],
        "max_dd_pct": summary["max_dd_pct"], "max_dd_date": frozen["maximum_drawdown_date"],
        "source_daily_sha256": sha(RUN / "daily.csv"),
        "source_summary_sha256": sha(RUN / "summary.json"),
        "source_manifest_sha256": sha(SOURCE / "SHA256SUMS"),
        "source_audit_sha256": sha(LINE / "reviews/stage060_s21_200k_audit.json"),
        "strategy_replayed": False, "source_mutated": False,
    }
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
