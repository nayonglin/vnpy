# Stage001 全市场源重建截止日开盘快照失败

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 当前模式：day
- 记录时间：2026-09-04 11:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：无标签数据源重建与覆盖资格审计。
- 是否重要突破：否；这是冻结失败与根因定位，不是策略收益突破。
- 是否触发A/B：否。

## 外部调研与判断

- TqBacktest 官方文档：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>。
- TqApi/query_quotes 官方文档：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html>。
- TqSdk 上游实现：<https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py>。
- 我的判断：Stage001 的唯一失败月不是全市场源不可得，而是日K serial 在 cutoff-day 回测刚创建时即被复制；官方生命周期和单合约复现均表明，应推进到 `BacktestFinished` 后才能取得完整截止日日K。

## 本次变更

- 新增脚本：`tools/full_market_source_rebuild.py`、`tools/stage001_full_market_source_rebuild.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：截止日 `2026-06-30`、源起点 `2021-01-18`、商品交易所白名单、54个月覆盖硬门、增量批量大小。
- 修改参数：无。
- 删除参数：无。
- 数据隔离：所有新文件只写本研究线；共享映射、行情数据库、生产 release、CTP 与订单入口均未修改。

## 回测/归因参数

- 数据区间：`2021-01-18..2026-06-30`；评估月 `2022-01-28..2026-06-30`，共54月。
- 账户规模：`150,000`，仅用于一手保证金资格计算，不是策略回测本金。
- 成本口径：不适用；未运行策略回测。
- 样本过滤：商品交易所 `CZCE/DCE/GFEX/INE/SHFE`；CFFEX排除；映射日数 `>=252`、有效close日数 `>=241`、60日活动率 `>=90%`、同日曲线合约 `>=2`。
- 策略/归因口径：每月合格品种 `>=30`；有正式A-rank10的合格月 `>=36`；每个该月池外挑战者 `>=10`。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 源结果：4,603个标准合约、80个品种、105,440条PIT映射；计划增量986个合约，`922 fetched / 64 empty / 0 failed`。
- 覆盖结果：54月、3,836行、2,840合格、1,947池外挑战；正式替换合格月47、动作就绪月47。
- 唯一失败：`2026-06-30` 合格品种与挑战者均为0；其余53个月合格品种均为 `50..59`。
- 根因复现：`SHFE.cu2607` 创建快照 volume=`0`，推进到 `BacktestFinished` 后 volume=`23,802`，OHLC/OI同时补全。
- 决策：`stage001_source_rebuild_coverage_fail_close_no_model`。

## 输出文件

- report：`artifacts/stage001_full_market_source_rebuild/report.md`。
- summary：`artifacts/stage001_full_market_source_rebuild/stage001_summary.json`，SHA256=`a9ba8d212aa0f40587fedca7ac50667a8fee23799e8a9e6a320706f246ef67fc`。
- monthly：`artifacts/stage001_full_market_source_rebuild/monthly_coverage.csv`，SHA256=`3d864f14a1f858be796cef2e0c1abcc054a082f954a4e143db2a23adf5162bb6`。
- manifest：`artifacts/stage001_full_market_source_rebuild/artifact_manifest.json`，SHA256=`d40046f9ef81aeca66849bfdcfc75093e650b286e478357f42f270859c09fc3b`。
- orders/daily：不适用；没有订单或策略权益序列。

## 结论

- 本阶段结论：Stage001 按冻结门失败并保留，不得覆盖；失败由采集时序缺陷造成。
- 是否进入下一步：是，但仅允许另发一次 Stage002 端-of-day时序修复，目录、映射、计划和硬门必须完全不变。
- 下一步：整批订阅后推进到回测结束再复制 serial；若仍失败则关闭本线。

## 过拟合反思

- 运行前判断：否；未读取标签或收益结果。
- 运行后判断：否；根因由同一合约生命周期对照直接复现，没有按月份、品种或门槛救参。
- 原因：失败修复只涉及数据完整性语义，覆盖门和截止日保持冻结。

## 继续价值反思

- 运行前判断：有；旧源末段断层是全市场研究的必要前置缺口。
- 运行后判断：有，但只限一次明确的端-of-day修复。
- 原因：其余53个月均大幅通过，唯一失败月与 cutoff-day volume=0 一一对应，具有清晰可证伪性。

## 合入建议

- 是否更新本线 `LINE.md`：是，连同Stage002结果统一收口。
- 是否更新 `research/registry.md`：是，登记新线最终资格结论。
- 是否追加根目录 `memory.md/back_log.md`：否；尚无模型或策略效果突破。
