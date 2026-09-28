"""Read immutable Stage061 evidence; summarize only, never run a strategy."""
import hashlib
import io
import json
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

ROOT = Path('/Users/bytedance/Desktop/person/vnpy')
LIVE = Path('/Users/bytedance/Desktop/person/vnpy_production_live')
OUT = Path(__file__).resolve().parent
COMMIT = '6750783fe7aab92e6dbdd6820fa212e2e53ea353'
BASE = 'research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage061_ai_top10_to_top19_fullperiod/'
ARM = 'stage061_top10_plus_fu'
CAPITAL = 150000.0
source_hashes = {}

def read_csv(name):
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{COMMIT}:{BASE}{name}'])
    source_hashes[name] = hashlib.sha256(raw).hexdigest()
    return pd.read_csv(io.BytesIO(raw))

current = json.loads((LIVE / 'official_strategy_materials/CURRENT.json').read_text())
assert current['strategy_version'] == 'ai_top10_plus_fu_official_live_v1'
assert current['ruleset_version'] == 'stage037_stage034_long_short_mirror_hard_block_v1'
release = LIVE / 'official_strategy_materials' / current['strategy_version'] / 'releases' / current['release_id']
frozen = json.loads((release / 'payload/ai/stage182/summary.json').read_text())
assert frozen['source']['commit'] == COMMIT
assert hashlib.sha256((release / 'payload/ai/stage182/source/stage061_top10_eligibility.csv').read_bytes()).hexdigest() == frozen['source']['sha256']
curve = read_csv('stage061_equity_curve.csv').query('variant == @ARM').copy()
curve['date'] = pd.to_datetime(curve['date'])
curve = curve.sort_values('date').reset_index(drop=True)
summary = read_csv('stage061_summary.csv').query('variant == @ARM').iloc[0]
trades = read_csv('stage061_trades.csv').query('variant == @ARM')
equity = curve.account_equity
dd = (equity / equity.cummax() - 1) * 100
assert len(curve) == 2101 and curve.date.is_unique
assert curve.date.iloc[0] == pd.Timestamp('2018-01-02')
assert curve.date.iloc[-1] == pd.Timestamp('2026-08-28')
checks = {
    'end_equity': equity.iloc[-1],
    'total_return_pct': (equity.iloc[-1] / CAPITAL - 1) * 100,
    'max_drawdown_pct': dd.min(),
    'sharpe': summary.sharpe,
    'total_slippage': curve.total_slippage.sum(),
    'trade_count': len(trades),
    'win_rate_pct': (curve.net_pnl > 0).sum() / (curve.net_pnl != 0).sum() * 100,
    'broker10_peak_pct': curve.broker10_margin_to_equity_pct.max(),
}
for key, value in checks.items():
    assert abs(float(value) - frozen['research_evidence']['Stage061']['top10_full_period'][key]) < 0.00001, key
np.testing.assert_allclose(dd, curve.drawdown_pct, atol=1e-10)
np.testing.assert_allclose(CAPITAL + curve.net_pnl.cumsum(), equity, atol=1e-7)
assert int(curve.trade_count.sum()) == len(trades) == 798
cagr = ((equity.iloc[-1] / CAPITAL) ** (365.25 / (curve.date.iloc[-1] - curve.date.iloc[0]).days) - 1) * 100
assert abs(cagr - summary.cagr_pct) < 1e-9
trough = int(dd.idxmin())
peak = int(equity.iloc[:trough+1].idxmax())
recoveries = curve.index[(curve.index > trough) & (equity >= equity.iloc[peak])]
recovery = int(recoveries[0])
fmtdate = lambda i: curve.date.iloc[i].strftime('%Y-%m-%d')
rows = []
previous = CAPITAL
for year, group in curve.groupby(curve.date.dt.year):
    values = np.r_[previous, group.account_equity.values]
    rows.append({'year': int(year), 'starting_equity': previous, 'ending_equity': values[-1],
                 'return_pct': (values[-1] / previous - 1) * 100,
                 'within_year_drawdown_pct': (values / np.maximum.accumulate(values) - 1).min() * 100})
    previous = values[-1]
annual = pd.DataFrame(rows)
curve.to_csv(OUT / 'daily_equity.csv', index=False)
annual.to_csv(OUT / 'annual_metrics.csv', index=False)

plt.rcParams.update({'font.family': 'Arial Unicode MS', 'axes.unicode_minus': False, 'font.size': 11})
fig, (ax, dx) = plt.subplots(2, 1, figsize=(14, 8.7), sharex=True,
                            gridspec_kw={'height_ratios': [2.2, 1]}, layout='constrained')
fig.suptitle('当前实盘策略的历史回测｜Stage037 · Top10+fu', fontsize=20, fontweight='bold')
ax.set_title('2018-01-02 — 2026-08-28｜初始15万元｜冻结Stage061结果，非实际实盘收益', fontsize=11, color='#536174')
ax.plot(curve.date, equity / 10000, color='#1769c2', lw=1.7, label='账户权益（万元）')
ax.set_ylabel('账户权益（万元）')
ax.legend(loc='upper left', frameon=False)
ax.annotate(f'期末 {equity.iloc[-1]/10000:,.2f}万', (curve.date.iloc[-1], equity.iloc[-1]/10000),
            xytext=(-150, 25), textcoords='offset points', color='#1769c2', fontsize=12,
            arrowprops={'arrowstyle': '-', 'color': '#1769c2'})
ax.axvspan(curve.date.iloc[peak], curve.date.iloc[recovery], color='#e69543', alpha=0.12)
ax.annotate('最大回撤阶段：655.17万 → 393.66万', (curve.date.iloc[trough], equity.iloc[trough]/10000),
            xytext=(-135, 65), textcoords='offset points', fontsize=11,
            arrowprops={'arrowstyle': '->', 'color': '#7e623a'})
dx.fill_between(curve.date, dd, 0, color='#d64a48', alpha=0.22)
dx.plot(curve.date, dd, color='#bd3439', lw=1.2)
dx.axhline(dd.min(), color='#8a2835', ls='--', lw=0.9, label=f'最大回撤 {dd.min():.2f}%')
dx.set_ylabel('距历史前高回撤（%）')
dx.set_ylim(-46, 2)
dx.legend(loc='lower right', frameon=False)
dx.xaxis.set_major_locator(mdates.YearLocator())
dx.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
dx.set_xlabel('交易日期')
for a in (ax, dx):
    a.grid(alpha=0.17)
    a.spines[['top', 'right']].set_visible(False)
fig.savefig(OUT / 'equity_drawdown.png', dpi=160)
plt.close(fig)

table = '\n'.join(f"| {int(r.year)}{'（截至8/28）' if r.year == 2026 else ''} | {r.ending_equity/10000:,.2f} | {r.return_pct:+.2f}% | {r.within_year_drawdown_pct:.2f}% |" for r in annual.itertuples())
report = f'''# 当前实盘版本全周期收益与回撤报告

报告时间：{datetime.now().astimezone().isoformat(timespec='minutes')}。本报告复核现有冻结回测，不重跑、不改参数、不连接CTP、不调用订单API。

## 结论

当前已安装的是 **Stage037 + AI Top10非fu＋固定fu，共11品种**。对应正式物料保存的全周期回测：15万元起步，期末权益 **{equity.iloc[-1]:,.2f}元（{equity.iloc[-1]/10000:,.2f}万元）**，总收益 **{checks['total_return_pct']:,.2f}%**，最大回撤 **{dd.min():.2f}%**。

这是历史组合回测，不是实盘账户已赚到的金额，也不是将来收益或最大亏损的保证。实际生产冷启动边界为2026-07-23，不能把2018年以来的回测收益记入真实账户。

## 核心指标

| 指标 | 结果 |
| --- | ---: |
| 首末交易日 | {fmtdate(0)} — {fmtdate(len(curve)-1)} |
| 交易日数 | {len(curve):,} |
| 初始资金 | 150,000.00元 |
| 期末权益 | {equity.iloc[-1]:,.2f}元 |
| 净利润 | {equity.iloc[-1]-CAPITAL:,.2f}元 |
| 总收益率 | {checks['total_return_pct']:,.2f}% |
| 期末资金/初始资金 | {equity.iloc[-1]/CAPITAL:.2f}倍 |
| 复合年化收益（365.25日） | {cagr:.2f}% |
| 最大回撤（日度权益） | {dd.min():.2f}% |
| Sharpe（原引擎口径） | {summary.sharpe:.6f} |
| 累计滑点成本 | {curve.total_slippage.sum():,.2f}元 |
| 成交记录数（含开、平、加减仓） | {len(trades)} |
| 盈利日比例（非零盈亏日） | {checks['win_rate_pct']:.2f}%（705/1,312） |
| broker10保证金/权益峰值（回测压力口径） | {checks['broker10_peak_pct']:.2f}% |
| broker10超过100%的交易日 | {int(summary.days_over_100pct)} |

“53.73%”是非零盈亏日胜率，**不是逐笔交易胜率**；798条成交也不是798笔完整开平仓。Sharpe沿用原引擎统计，本次未另换收益定义。权益为原引擎扣手续费、滑点后的日度净权益；日内最大回撤可能高于日度统计。

## 资金曲线与回撤

![全周期权益与回撤]({OUT / 'equity_drawdown.png'})

- 最大百分比回撤起点：**{fmtdate(peak)}，{equity.iloc[peak]/10000:,.2f}万元**。
- 谷底：**{fmtdate(trough)}，{equity.iloc[trough]/10000:,.2f}万元**；损失{(equity.iloc[peak]-equity.iloc[trough])/10000:,.2f}万元，回撤{abs(dd.min()):.2f}%。
- 首次恢复该前高：**{fmtdate(recovery)}**，从前高到恢复共{(curve.date.iloc[recovery]-curve.date.iloc[peak]).days}个自然日。
- 截至回测末日，仍低于全周期历史前高 **{abs(dd.iloc[-1]):.2f}%**；期末不是历史最高权益。
- 全周期最大现金回撤为{abs((equity-equity.cummax()).min())/10000:,.2f}万元，和上述最大百分比回撤并非同一段，不能混用。

39.91%的回撤意味着从一个权益高点出发，约四成权益曾被回吐；要从该谷底恢复前高，需要约{(1/(1+dd.min()/100)-1)*100:.2f}%的上涨。因此它属于高收益、高波动的策略路径，不能只看终值。

## 逐年表现

| 年份 | 年末权益（万元） | 当年收益 | 年内最大回撤 |
| --- | ---: | ---: | ---: |
{table}

逐年表是同一条全周期连续持仓/复利路径的切片，**不是每年重新用15万元冷启动**。年内最大回撤将年初权益纳入峰值并在年初重置；跨年最大回撤以全周期指标为准。2026年只到8月28日，不能视为完整年度。

收益集中在2020—2021与2024年的较强阶段；2023年全年亏损，2026年截至回测末日也为负收益。2022年虽全年盈利，年内仍有37.65%回撤，说明年度收益为正并不等于持有过程平稳。

## 稳健性与解释边界

1. 本报告采用**正式物料引用的Stage061冻结全周期**，不是把当前可变数据库重跑后的其他研究结果混进来。当前AI合同与Stage061源资产SHA已核对；m0004是治理发布，未更改该冻结回测的数值。
2. Top10的全周期滑点为同源Stage037 Top8基线的130.36%，超过预先冻结的105%成本门。固定、随机多周期还保留回撤、成本、broker容量失败；正式晋升属于用户明确授权，不代表这些自然研究门已经通过。
3. 随机192窗中，Top10相对历史Stage037 Top8的回撤非劣率为72.92%、聚合滑点比113.66%；不能用单一全周期39.91%回撤作为未来风险上限。
4. 历史55个AI月使用10个模型非fu＋固定fu；2019-12-31前AI静态边界为18品种且不含fu。部分2026历史排名不足的月份保留原Top8后补足排名，这属于冻结研究数据的已知限制，不等于每个历史月份都保存了完整原始排名。

## 版本与证据

- 当前策略：`{current['strategy_version']}`。
- 当前规则：`{current['ruleset_version']}`；不含Stage076周线/ER豁免。
- 当前正式物料：`{current['release_id']}`。
- 生产HEAD：`{subprocess.check_output(['git','-C',str(LIVE),'rev-parse','HEAD'], text=True).strip()}`。
- 回测来源提交：`{COMMIT}`，Git内路径：`{BASE}`。
- [当前正式物料回测摘要]({release / 'payload/ai/stage182/summary.json'})。
- [每日权益原始列提取]({OUT / 'daily_equity.csv'})、[年度指标]({OUT / 'annual_metrics.csv'})、[复核与来源SHA]({OUT / 'audit.json'})。

## 本次判断

外部调研：本次是内部冻结结果审计，不新增策略研究；收益、回撤结论只依据原始Git曲线和正式物料，不以外网信息替代。

过拟合：本次报告不调参、不筛选窗口，不新增拟合；策略本身经过多轮历史筛选，已有选择偏差风险仍在。

继续价值：有，后续以实盘成交、实际滑点和新增样本跟踪风险；不把已有历史高收益当作继续调参或收益承诺。
'''
(OUT / 'REPORT.md').write_text(report)
audit = {'generated_at': datetime.now().astimezone().isoformat(), 'source_commit': COMMIT,
         'current_material': current['release_id'], 'source_sha256': source_hashes,
         'verified_metrics': {k: float(v) for k, v in checks.items()},
         'curve_recomputation_pass': True, 'new_backtests': 0, 'order_api_called_count': 0,
         'peak_date': fmtdate(peak), 'trough_date': fmtdate(trough), 'recovery_date': fmtdate(recovery)}
(OUT / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
print(json.dumps(audit, ensure_ascii=False, indent=2))
print(OUT / 'REPORT.md')
