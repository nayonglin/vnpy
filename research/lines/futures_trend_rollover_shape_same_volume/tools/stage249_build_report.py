"""仅从严格重跑及审计产物生成中文最终段落；禁止诊断结果冒充完成。"""
import argparse,json
from datetime import datetime
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--stats',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--chart',type=Path,required=True);a=ap.parse_args()
src=a.source.resolve();stats=a.stats.resolve();m=json.loads((src/'metrics.json').read_text());prov=json.loads((src/'run_provenance.json').read_text());s=json.loads((stats/'summary.json').read_text());old=json.loads((a.baseline/'metrics.json').read_text());c=pd.read_csv(stats/'complete_cycles.csv').fillna('');period=pd.read_csv(stats/'year_month_results.csv')
assert not prov['diagnostic_incomplete_minutes'];assert not s['diagnostic_incomplete_minutes'];assert s['incomplete_scan_keys']==0
anchors=pd.read_csv(src/'execution_anchor_requests.csv');assert anchors['coverage_status'].eq('complete').all()
assert prov['official_parameters_match_baseline'] and prov['all_data_and_model_inputs_unchanged_during_run']
assert prov['vendor_swallowed_bar_exception_guard'] and prov['captured_bar_failure_count']==0
allstats=s['periods']['all']['entry_cohort_complete_cycles'];recent=s['periods']['since_202509'];rstats=recent['entry_cohort_complete_cycles'];eps=recent['entry_cohort_complete_episodes']
fmt=lambda x:f'{float(x):,.2f}'
body=['## 最终严格回放结果','',f'记录时间：{datetime.now().astimezone().isoformat(timespec="minutes")}。窗口2020-01-01至2026-10-14，交易日边界严格，初始本金150,000元。以下替代诊断轮作为本次重跑结果；旧Stage246/247文件保留。','',
'|指标|旧Stage246（含缺陷）|Stage249严格修复重跑|','|---|---:|---:|',
f'|期末权益|{fmt(old["end_equity"])}|{fmt(m["end_equity"])}|',f'|总收益|{old["total_return_pct"]:.2f}%|{m["total_return_pct"]:.2f}%|',f'|最大回撤|{old["max_dd_pct"]:.2f}%|{m["max_dd_pct"]:.2f}%|',f'|Sharpe|{old["sharpe"]:.6f}|{m["sharpe"]:.6f}|',f'|总滑点（元）|{fmt(old["total_slippage"])}|{fmt(m["total_slippage"])}|',f'|成交笔数（开平分计）|{int(old["total_trade_count"])}|{int(m["total_trade_count"])}|',f'|完整周期胜率|119/395 = 30.13%|{allstats["wins"]}/{allstats["closed_cycles"]} = {allstats["win_rate_pct"]:.2f}%|',f'|broker10保证金/权益峰值|{old["max_broker10_margin_to_equity_pct"]:.2f}%|{m["max_broker10_margin_to_equity_pct"]:.2f}%|',f'|保证金占用>100%的日数|{int(old["days_over_100pct"])}|{int(m["days_over_100pct"])}|','',
'胜率按合约从空仓到再次空仓的完整持仓周期计算；开仓和平仓不是两次胜率样本。同日重试单独形成周期，另提供按原订单父子关系合并的信号统计。期末未平仓不当作输赢。',f'期末仍有{s["end_open_contracts"]}个未平合约，相关净盯市盈亏{fmt(s["end_open_mtm"])}元已计入账户权益；完整周期净盈亏与净值之间的差额由此解释。',f'合并重试的未完成信号净盯市为{fmt(s["end_open_episode_net_mtm"])}元，包含同一信号已平仓腿；它与单独未平仓周期盯市口径不同。','',
'### 2025年9月以来','',f'期初权益{fmt(recent["start_equity"])}元，期末{fmt(recent["end_equity"])}元，期间净盯市盈亏{fmt(recent["net_mtm_pnl"])}元，收益{recent["return_pct"]:.2f}%，区间内峰值回撤{recent["max_dd_pct"]:.2f}%。',f'本期开仓且已平仓的周期：{rstats["wins"]}/{rstats["closed_cycles"]}盈利，胜率{rstats["win_rate_pct"]:.2f}%；净利润因子{rstats["profit_factor"]:.4f}。合并重试后的完整信号：{eps["wins"]}/{eps["closed_cycles"]}盈利，胜率{eps["win_rate_pct"]:.2f}%。这两个统计不是独立样本，也不能与按日胜率混用。','',
'|月份|月末权益|净盯市盈亏|月收益|当月平仓胜率|','|---|---:|---:|---:|---:|']
for r in period[(period.frequency=='month')&(period.period>='2025-09')].itertuples():
    rate=f'{r.exit_win_rate_pct:.2f}%' if pd.notna(r.exit_win_rate_pct) else '无平仓'
    body.append(f'|{r.period}|{fmt(r.end_equity)}|{fmt(r.net_mtm_pnl)}|{r.return_pct:.2f}%|{int(r.exit_wins)}/{int(r.exit_closed_cycles)}，{rate}|')
body+=['','### 年度结果','','|年份|年末权益|净盯市盈亏|年收益|年内回撤|成交数|','|---|---:|---:|---:|---:|---:|']
for r in period[period.frequency=='year'].itertuples():body.append(f'|{r.period}|{fmt(r.end_equity)}|{fmt(r.net_mtm_pnl)}|{r.return_pct:.2f}%|{r.max_dd_pct:.2f}%|{int(r.fill_count)}|')
body+=['','### 修复与验证','',
'1. 日初持仓、当日成交到收盘盈亏和费用分开记账；同时兼容收盘后成交，避免重复盯市和下一日漏记持仓。',
'2. 普通开平仓统一到交易日第一个实际分钟；前夜、跨午夜、周末及节后开盘按同一日历处理，修复SH漏夜盘。',
'3. 从真实入场时刻起扫描同一交易日；跳空使用可到达价格，按历史合法tick向不利方向取整。分钟内同时触发止损与进展，固定采用开盘优先、其后不利顺序；重试当根再次触及止损也计入。',
'4. T+1实际成交价按信号订单关联到正确layer，保留信号日期和持仓年龄；分批成交拆层、加权归因，同日重试独立身份避免改错层。',
'5. 完整分钟和首分钟缺失、过期状态及执行异常都阻断严格回放；诊断缺数据开关仅用于补数，不得交付为验收业绩。',
f'逐日内部权益最大残差{s["equity_max_abs_residual"]:.3g}元；候选定仓权益最大残差{s["sizing_max_abs_residual"]:.3g}元；独立成交现金流+日末仓位市值重建最大残差{s["independent_cashflow_max_abs_residual"]:.3g}元。',
'AI沿用原正式历史政策：2020年至2022-01为静态18品种池；从2022-02起采用历史月池，57个月快照完整（另有1个静态边界），Top10非fu加固定fu。未把2020年冒称为每月AI选品，也未重训。',
'模型、正式策略参数、手续费与滑点字段与冻结基线一致；数据/模型/源码在单轮回放期间hash不变。新增执行完整性开关默认True，诊断轮单独False；新增历史tick规则与审计字段不是alpha参数。正式参数删除0，模型重训0。','',
'### 每笔完整周期明细（2025-09以来入场）','',
'下表保留盈利与亏损，价格时间为实际物理时刻；月份和日账按所属交易日。手数为累计开仓量；存在分批成交时，表内首/末价格不能直接代替逐笔盈亏。完整成交、月池、候选、首分钟与止损事件证据在CSV中可按trade_id追溯。','',
'|首成交ID→末成交ID|合约/方向|物理入场→退出|首入场→末退出价|手数|净盈亏|是否重试|退出原因|','|---|---|---|---:|---:|---:|---|---|']
recent_cycles=c[c.entry_date>='2025-09-01'].sort_values('first_id')
attr=['### 近期亏损分布与重试观察','',
'以下是完整周期的描述性分组，不是移除某条规则后的因果收益；复利定仓、交易路径和组合占用会相互影响。未对规则做优化或筛选。','',
'|类别|完整周期|盈利数/胜率|净盈亏|','|---|---:|---:|---:|']
for retry,group in recent_cycles.groupby('is_retry'):
    wins=int(group.net_pnl.gt(0).sum());label='同日重试' if retry else '非重试'
    attr.append(f'|{label}|{len(group)}|{wins}/{len(group)} = {wins/len(group)*100:.2f}%|{fmt(group.net_pnl.sum())}|')
attr+=['','|品种|完整周期|盈利数/胜率|净盈亏|','|---|---:|---:|---:|']
for product,group in sorted(recent_cycles.groupby('product'),key=lambda x:x[1].net_pnl.sum()):
    wins=int(group.net_pnl.gt(0).sum());attr.append(f'|{product}|{len(group)}|{wins}/{len(group)} = {wins/len(group)*100:.2f}%|{fmt(group.net_pnl.sum())}|')
attr+=['','|最终退出标签|周期数|净盈亏|','|---|---:|---:|']
for reason,group in sorted(recent_cycles.groupby('exit_reason'),key=lambda x:x[1].net_pnl.sum()):
    attr.append(f'|{reason}|{len(group)}|{fmt(group.net_pnl.sum())}|')
attr+=['','标签说明：`initial_stop`为首次入场0.5R止损；`retry_failed`为同日重试后再触0.5R；`prev2day_stop`为前两日保护退出；`base_stop`为基础止损/保护退出；`heat_deleverage`为风险集中度减仓；`rollover_close`为换月退出。保护退出也可能实现盈利；标签是周期最后一腿的原因，不能替代该周期所有分批成交记录。','']
idx=body.index('### 每笔完整周期明细（2025-09以来入场）');body[idx:idx]=attr
for r in recent_cycles.itertuples():
    body.append(f'|{r.first_trade_id}→{r.last_trade_id}|{r.vt_symbol}/{"多" if r.direction=="long" else "空"}|{str(r.first_datetime).replace("+08:00", "")}→{str(r.last_datetime).replace("+08:00", "")}|{r.entry_price:g}→{r.exit_price:g}|{r.opened_volume:g}|{fmt(r.net_pnl)}|{"是" if r.is_retry else "否"}|{r.exit_reason}|')
body+=['','### 解释边界与结论','',
'这次修复不是过拟合：修法来自会计守恒、交易日因果和历史合约规格，未按收益筛选参数或删除亏损月份；也未改AI TopN、阈值、风险比例或重试次数。正式pairwise模型训练包含2020–2022，策略规则事后形成，因此全窗口仍不是严格样本外收益证明。',
'有继续价值：正确性与来源闭环恢复了可讨论的基准；后续应研究真实成本、严格样本外和风险承受能力。不能因修复结果某项改善就晋升或加仓。此次只完成离线修复和回放，没有修改CURRENT、发布正式物料或部署生产。',
'保留的模型限制：原正式手续费为0、滑点固定，broker10是固定保证金压力口径；OHLC无法还原tick先后、成交队列、深度、涨跌停可成交性，保守规则是明确模拟约定。',f'本轮DD40门：{"通过" if m["dd40_pass"] else "未通过"}；组合部署门：{"通过" if m["deployable_pass"] else "未通过"}。结果不得自动替代生产资格。','',
f'![修复前后与近期月度结果]({a.chart.resolve()})','',
f'- [完整逐笔周期]({stats/"complete_cycles.csv"})',f'- [全部回测成交]({src/"trades.csv"})',f'- [期末未平仓周期]({stats/"open_positions.csv"})',f'- [期末未完成信号]({stats/"open_episodes.csv"})',f'- [年度/月度结果]({stats/"year_month_results.csv"})',f'- [会计与统计审计]({stats/"summary.json"})',f'- [源码与输入溯源]({src/"run_provenance.json"})',f'- [逐日权益]({src/"daily.csv"})']
marker='<!-- STAGE249_FINAL_VERIFIED_REPLAY -->';current=a.stage.read_text().split(marker)[0].rstrip();a.stage.write_text(current+'\n\n'+marker+'\n\n'+'\n'.join(body)+'\n')
print(json.dumps({'stage':str(a.stage),'cycles':len(recent_cycles),'strict_engine_completed':True},ensure_ascii=False))
