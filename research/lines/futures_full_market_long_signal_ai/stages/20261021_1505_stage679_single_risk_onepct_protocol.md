# Stage679：单族1%风险固定A/C实验协议与实施计划

- line_id：futures_full_market_long_signal_ai；day；2026-10-21 15:05 CST；branch codex/ai-training-data-expansion；非重要突破。
- 用户已授权当前研究版单族风险.25%→1%。按version-ab-experiment做原研究A(.25%)与C(1%)，显式以用户指定675为对照，不是正式C9晋级，不改变总2%上限。
- 完整合同：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage679_single_risk_onepct_protocol/protocol.json)；最多0fit/2新cash/0旧账重跑/SQL下载，不扫风险网格。

## 固定设计

2015-01-05—2026-10-16连续2862日，100万，复用675完整5246条prebudget signals；模型/标签/选合约/K/entry/exit/.25N/20low不变。TOTAL_RISK2%、margin25%/buffer1.1、原base/stress费滑和1%毛容量均不变；.01raw预算后统一scale取整容量截断，D仅减量。未用预算不再分配，已有仓initialrisk占用不随止损降低。

## 任务

- [ ] 680私有三层FunctionType适配，旧code/defaults不改、旧globals不写；必要5类预算/cap/隔离fixture，source_ready。
- [ ] 681 source_GO绑定实际ready及隔离/预算实效；root唯一actual_run1，0fit2cash，不因观测超时重启。
- [ ] 681终态一次独立会计+新1%公式+容量/unknown/summary/年度/curve审，0策略重放/旧账全审。
- [ ] 682离线Plotly4账户对比和CSV，root浏览器导PNG并视觉核对。
- [ ] root683记录全部指标与风险收益判断，一次更新LINE/registry，day交付，不晋级/加注或扩大总风险。

## 判定与反思

不预设好结果。仅两成本收益/DD/Sharpe均不差才记同史点值占优；更高收益更深DD记风险交换，不当稳定增强。继承历史容量/入场/stale及非PIT边界，保留所有负结果。开始新增按本次收益寻优过拟合否；长期同史选择风险高；检验这个用户指定单点有价值，结果后不继续扫小数/总风险/保证金救参。

新增参数0；修改SINGLE_RISK .0025→.01，删除0；新资金结果待运行，权益/收益/DD/Sharpe/滑点/笔数/胜率N/A。累计588fit/296完成cash+1旧partial，本次最多新增2cash。仅本线目录，无新分支/工作树/Git/正式/生产/CTP/邮件/任务变更；普通结果不写根总账。
