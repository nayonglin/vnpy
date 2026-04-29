# stock_range_paper_v1 - 股票震荡paper线

## 定位

- 资产：A股。
- 策略类型：横截面震荡/超跌修复。
- 核心口径：`stock_range_reversion_liquid_q3` paper / monitor suite。
- 当前状态：paper监控，黄灯继续观察，不自动实盘。

## 最近稳定口径

- paper monitor suite状态：`yellow_caution_continue_paper`。
- 最新目标执行日：`2026-04-27`。
- 最新订单：`24`行。
- 阻断：`0`。
- 未成交权重：`0.00%`。
- 全历史填充率：`99.73%`。
- 期末权益：`2.2225`。
- 总收益：`122.25%`。
- 最大回撤：`-15.16%`。
- Sharpe：`0.7373`。

## 当前判断

- 这条线是已建立paper ledger和monitor suite的股票震荡监控线。
- 继续paper，不升级实盘。
- 新增样本要单独做OOS归因，不能混在历史回测里解释。

## 下一步

- 定期补齐数据。
- 运行latest packet、paper ledger、OOS归因和paper monitor suite。
- 若连续出现阻断、填充率下滑或新增回撤扩大，再做执行归因，不先调信号。
