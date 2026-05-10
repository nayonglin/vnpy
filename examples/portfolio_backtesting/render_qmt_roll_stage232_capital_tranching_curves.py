from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage232_deployment_capital_tranching_v1"
INPUT_CURVES = OUTPUT_DIR / f"qmt_roll_stage232_deployment_capital_tranching_curves_{MODEL_TAG}.csv"
OUTPUT_HTML = OUTPUT_DIR / f"qmt_roll_stage232_deployment_capital_tranching_curves_{MODEL_TAG}.html"
OUTPUT_PNG = OUTPUT_DIR / f"qmt_roll_stage232_deployment_capital_tranching_curves_{MODEL_TAG}.png"

WINDOW_ORDER = [
    "since_2020",
    "since_2021",
    "since_2022",
    "since_2023",
    "since_2024",
    "since_2025",
    "phase_2020_2021",
    "phase_2022_2023",
    "phase_2024_2025",
    "phase_2026_latest",
]
POLICY_ORDER = [
    "baseline_full_reinvest",
    "balanced_tranche_v1",
    "profit_tranche_v1",
]
POLICY_LABELS = {
    "baseline_full_reinvest": "全复利",
    "balanced_tranche_v1": "balanced_tranche_v1",
    "profit_tranche_v1": "profit_tranche_v1",
}
COLORS = {
    "baseline_full_reinvest": "#2563eb",
    "balanced_tranche_v1": "#059669",
    "profit_tranche_v1": "#dc2626",
}


def _load_curves() -> pd.DataFrame:
    df = pd.read_csv(INPUT_CURVES)
    df["date"] = pd.to_datetime(df["date"])
    df["normalized_total_equity"] = df.groupby(["window_name", "policy"])["total_equity"].transform(lambda s: s / s.iloc[0])
    return df


def _plot_png(df: pd.DataFrame) -> None:
    windows = [w for w in WINDOW_ORDER if w in set(df["window_name"])]
    fig, axes = plt.subplots(5, 2, figsize=(16, 20), constrained_layout=True)
    axes = axes.flatten()
    for idx, window_name in enumerate(windows):
        ax = axes[idx]
        subset = df[df["window_name"].eq(window_name)].copy()
        display_label = subset["display_label"].iloc[0]
        for policy in POLICY_ORDER:
            part = subset[subset["policy"].eq(policy)]
            if part.empty:
                continue
            ax.plot(part["date"], part["normalized_total_equity"], label=POLICY_LABELS[policy], color=COLORS[policy], linewidth=1.8)
        ax.set_title(display_label)
        ax.grid(alpha=0.25)
        ax.tick_params(axis="x", rotation=30)
    for ax in axes[len(windows) :]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.suptitle("Stage232 资金分层多周期权益曲线", fontsize=16)
    fig.savefig(OUTPUT_PNG, dpi=180)
    plt.close(fig)


def _render_html(df: pd.DataFrame) -> None:
    rows = []
    windows = [w for w in WINDOW_ORDER if w in set(df["window_name"])]
    for window_name in windows:
        subset = df[df["window_name"].eq(window_name)].copy()
        display_label = subset["display_label"].iloc[0]
        table_rows = []
        for policy in POLICY_ORDER:
            part = subset[subset["policy"].eq(policy)].copy()
            if part.empty:
                continue
            end_equity = part["total_equity"].iloc[-1]
            nav = part["normalized_total_equity"].iloc[-1]
            locked = part["locked_equity"].iloc[-1]
            table_rows.append(
                f"<tr><td>{POLICY_LABELS[policy]}</td><td>{end_equity:,.0f}</td><td>{nav:.2f}</td><td>{locked:,.0f}</td></tr>"
            )
        rows.append(
            f"""
            <section class="card">
              <h2>{display_label}</h2>
              <img src="{window_name}.png" alt="{display_label}" />
              <table>
                <thead><tr><th>策略</th><th>期末总权益</th><th>NAV</th><th>期末锁盈</th></tr></thead>
                <tbody>{''.join(table_rows)}</tbody>
              </table>
            </section>
            """
        )

    # Generate per-window inline PNGs
    images: dict[str, str] = {}
    for window_name in windows:
        subset = df[df["window_name"].eq(window_name)].copy()
        fig, ax = plt.subplots(figsize=(8, 3.5), constrained_layout=True)
        for policy in POLICY_ORDER:
            part = subset[subset["policy"].eq(policy)]
            if part.empty:
                continue
            ax.plot(part["date"], part["normalized_total_equity"], label=POLICY_LABELS[policy], color=COLORS[policy], linewidth=2.0)
        ax.grid(alpha=0.25)
        ax.tick_params(axis="x", rotation=30)
        ax.legend(frameon=False, fontsize=8)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=160)
        plt.close(fig)
        images[window_name] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        rows = [row.replace(f'{window_name}.png', images[window_name]) for row in rows]

    html = f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <title>Stage232 资金分层多周期权益曲线</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #111827; }}
        h1 {{ margin-bottom: 8px; }}
        p {{ color: #4b5563; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, minmax(420px, 1fr)); gap: 18px; }}
        .card {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; background: #fff; }}
        img {{ width: 100%; border-radius: 8px; border: 1px solid #f3f4f6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ text-align: right; padding: 6px 8px; border-bottom: 1px solid #f3f4f6; }}
        th:first-child, td:first-child {{ text-align: left; }}
      </style>
    </head>
    <body>
      <h1>Stage232 资金分层多周期权益曲线</h1>
      <p>对比 `全复利`、`balanced_tranche_v1`、`profit_tranche_v1` 三种账户部署制度在各窗口下的归一化权益曲线。</p>
      <div class="grid">
        {''.join(rows)}
      </div>
    </body>
    </html>
    """
    OUTPUT_HTML.write_text(html, encoding="utf-8")


def main() -> None:
    df = _load_curves()
    _plot_png(df)
    _render_html(df)
    print(OUTPUT_HTML)
    print(OUTPUT_PNG)


if __name__ == "__main__":
    main()
