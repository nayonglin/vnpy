# Stage003 独立审查修复合同

- 时间：`2026-07-13 23:50 CST`
- line_id：`futures_trend_tight_stop_quality_sizing`
- reviewer：`Kant / 019f5c1b-1f8a-7982-bc35-2619b02b09c9`
- 首轮审查：`FAIL`，P0 `0`、P1 `3`、P2 `3`，置信度 `99%`。

## 作废原因

1. 引擎 history 最后一行是信号日，即实际下一交易日成交的 T-1；首版再次 `iloc[:-1]`，把 ATR/body 错算成 T-2，直接影响分类和仓位。
2. 基类诊断表是白名单，首版 `stage003_*` 字段没有落盘，feature audit 空表却 fail-open。
3. 首版未保存 A/C trades 与 stop-retry events，无法逐笔认证 `0.5R` 重试和成交守恒。
4. 预调用 `_entry_stop_price` 重复写入 long-stop 调整诊断；参数字段与模块常量也存在脱节。

## 冻结修复

- 规则参数保持：`stop_atr14 <= 0.515281`、body Q2、quality `1.25x`、other `0.75x`，不允许调整。
- ATR/body 直接使用完整 engine history，feature date 等于 signal date/T-1。
- 用无副作用纯函数预览当前正式 long/short 初始止损，基类 sizing 只调用一次正式止损函数。
- class 运行参数显式传入特征和权重函数。
- candidate 与 entry-risk 诊断追加全部 Stage003 字段，并对字段、日期、覆盖、权重、风险金额执行 fail-close。
- 保存 A/C trades、entry candidates、entry risk、trade events、stop-retry events；逐锚点核对成交数、retry 次数和 retry 手数。
- 增加脚本、DB、正式 AI 池、分钟源、正式配置和 Stage847 入口的输入 hash manifest。
- 首轮错误输出整体移入 quarantine 目录，不删除、不覆盖其证据；修复后输出重新创建。

## 修复前反思

- 过拟合：修复本身不是参数优化，不增加过拟合；规则原有的高过拟合风险不变。
- 继续价值：有且只允许一次原参数复验；若修复后失败，Stage003 立即关闭。

