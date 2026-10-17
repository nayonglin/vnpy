# Stage018 修正等待预算后，原批次完整成功

- line_id：futures_trend_triple_screen；记录时间：2026-10-18 01:08 CST。
- 非策略突破版本；本轮只改采集等待控制流，无新增、修改或删除策略参数，AI池/0.5R/retry/风险/退出均不变。
- 调研依据：官方API文档与GitHub的wait_update语义，见本阶段冻结协议。没有按收益改变目标、接口或数据精度。

## 实际结果

- 原Stage017目标逐字节相同：8合约、39session、12945分钟；原manifest SHA `a58a875df23d2dda6c797d94e7f46275f0b832377325ef7cf68423b7601a0219`。
- root唯一真实run，exec session27598已确认terminal exit0；parent用时117.012秒、worker114.597秒，非硬杀，35项冻结输入全部未变。
- 同一正常API连接经历2次wait_update=False后继续；总update调用4次，8个series ready，12945分钟全部取得，39/39完整网格及原CSV七字段通过。没有应用层重连、重auth、接口切换或授权修改。
- AP210.CZCE/2022-04-06完整225分钟已取得，日线七字段完全一致；这是Stage016所需源资格，不是其修正表已构建或候选已可完整回放。
- 本次`tq_dl=false`仍通过正常公开回测流取得历史数据。只能据此确认该通路及目标可用，不能推定其他区间或批量下载接口可用。
- 原Stage017失败与0行raw保留。Stage018新raw及后继证明在本地独立目录，不覆盖原base或此前overlay。

## 独立复核与限制

- 独立agent检查12945行全唯一、合法OHLCV/OI、重建39个目标网格及全部逐行后继；AP210及另4session以Decimal独立聚合七字段，精确匹配原CSV/冻结参考。
- 35项输入及parent绑定6项产物SHA相符。未重复聚合其余34session、未保存provider原始ns快照；这些限制明确保留，不将有限抽核称全市场逐价认证。
- receipt：`outputs/stage018_independent_review/review_receipt.json`，SHA `b7820471cc7d84963251182b8d10cf26e82cfc009a45e70ac9a7184ab39cd0cf`。P0/P1=0，`qualified_research_data=true`、`qualified_precise_sessions=39`、`required_AP210_accepted=true`；仅限精确研究数据用途。
- Stage016须显式绑定018实际raw/证据/receipt；禁止覆盖017失败receipt或沿旧路径冒称017已通过。

## 金融与后续

- 金融attempt仍4、完整账户回放仍1；没有C0第三次、模型训练、CTP、委托、撤单、部署。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A；无新增/修改/删除金融结果。
- 过拟合判断：否，控制流修正由公开API合同决定；继续价值：是，本批确实补齐已证实源缺陷的替代数据，但尚无策略收益改善结论。
- TODO：一次构建并独立验收Stage016；随后合并必要新分钟。Stage019评估普通latest10000快照批次，优先同时减少full与anchor缺口，不为满足旧helper任意压低合理数据预算，不重跑候选碰缺口。
