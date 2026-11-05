"""Render the sealed Stage034 tables as a standalone Plotly chart."""
import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def render(source, output):
    bands = pd.read_csv(source / "equity_fan.csv")
    events = pd.read_csv(source / "event_frequencies.csv")
    primary = bands.loc[bands.block_days.eq(63)]
    figure = make_subplots(rows=2, cols=1, vertical_spacing=.15,
                           subplot_titles=("63 日块 · 权益路径分位带", "收盘保证金缺口 · 至少发生一次"))
    days = primary.trading_days
    for low, high, color, label in [
        ("p05", "p95", "rgba(47,100,171,.17)", "P5–P95"),
        ("p25", "p75", "rgba(47,100,171,.35)", "P25–P75"),
    ]:
        figure.add_trace(go.Scatter(x=days, y=primary[low] / 10_000, line=dict(width=0),
                                    hoverinfo="skip", showlegend=False), row=1, col=1)
        figure.add_trace(go.Scatter(x=days, y=primary[high] / 10_000, line=dict(width=0),
                                    fill="tonexty", fillcolor=color, hoverinfo="skip", name=label), row=1, col=1)
    figure.add_trace(go.Scatter(x=days, y=primary.p50 / 10_000, line=dict(color="#295d99", width=3),
                                name="权益中位数", hovertemplate="第 %{x} 日 · %{y:.2f} 万元<extra></extra>"),
                     row=1, col=1)
    figure.add_hline(y=30, line=dict(color="#65758a", dash="dash"), row=1, col=1)
    for block, color in [(63, "#295d99"), (21, "#a8572e")]:
        part = events.loc[events.block_days.eq(block) & events.event.eq("margin_breach")]
        percent = part.frequency * 100
        figure.add_trace(go.Bar(x=["1 年", "3 年", "5 年"], y=percent, name=f"{block} 日块",
                                marker_color=color, text=[f"{v:.2f}%" for v in percent],
                                textposition="outside", hovertemplate="%{y:.3f}%<extra></extra>"),
                         row=2, col=1)
    figure.update_yaxes(title_text="账户权益（万元）", row=1, col=1)
    figure.update_xaxes(title_text="交易日", row=1, col=1)
    figure.update_yaxes(title_text="模拟路径占比", range=[0, 55], ticksuffix="%", row=2, col=1)
    figure.update_layout(title="S19 蒙特卡洛 · 初始资金 30 万元",
                         template="plotly_white", height=720, barmode="group",
                         legend=dict(orientation="h", y=-.14), margin=dict(l=86, r=35, t=99, b=100))
    figure.write_html(output, full_html=True, include_plotlyjs=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.source, args.output)
