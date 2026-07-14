# Stage136 AP010 canary 成交窗口原子补数结果

- 时间：`2026-07-11 19:30 -> 20:15 CST`
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 阶段：`Stage136`
- 是否重要突破：否；这是 Stage135 固定 canary 的单一数据阻塞修复，同时暴露并修复了 Stage052 分钟 producer 的闭合态采集 bug。
- 性质：历史分钟数据工程；不改策略、正式实盘、CTP、邮件、launchd 或订单路径。

## 外部调研与判断

- TqSdk 官方 `DataDownloader`/回测接口允许按明确 datetime 边界下载历史分钟序列，但序列更新过程中的首个快照不天然等价于该分钟最终闭合态。
- Python `os.replace` 在同一文件系统内可用于原子替换；本阶段因此保持 temp 严格验收、旧文件备份、同设备 replace、发布后再验收的四段链。
- 判断：Stage135 只读取成交窗口第一根 `open`，但数据文件一旦命名为 minute backtest，就不能默许 `high/low/close/volume/OI` 全部停留在首快照。producer 必须保存同一 `bar_id` 的最新闭合状态。

参考：

- TqSdk DataDownloader：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html>
- TqSdk TqBacktest：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>
- Python `os.replace`：<https://docs.python.org/3/library/os.html#os.replace>

## 根因与修复

### 初始阻塞

- Stage135 的 `2020-09-02` 固定目标篮子需要 `AP010.CZCE` 成交窗口。
- 冻结下载边界：`2020-09-01 20:55:00 <= bar_datetime < 2020-09-02 15:15:00`。
- 苹果当时无夜盘，因此必须取得 `2020-09-02 09:00-09:05` 的真实日盘 open，禁止日线 close、相邻日期或 fallback anchor。

### 独立审查发现的 P1

- 初版文件虽然有 `225` 行，但 `225/225` 行均为 `open=high=low=close`、`volume=0`，只是分钟首个快照，不是完整闭合 K 线。
- 根因在 `stage052_tqsdk_jd_minute_backfill.py`：首次看到 `bar_id` 后立即加入 `seen_bar_ids`，后续同一 bar 的 high/low/close/volume/OI 更新被忽略。

### TDD 修复

- 新增 `upsert_bar_snapshot`：同一 `bar_id` 持续覆盖为最新快照，不再首见即锁死。
- 捕获 `BacktestFinished` 时再读取一次 serial，确保最后一根 bar 的最终状态被保存。
- Stage136 增加 `closed_state_ready` 闸门，并保留 status/temp/publish/post 四处 SHA 链。
- 旧错误 AP010 文件先进入 `quarantine/replaced_previous`，再同设备 `os.replace` 发布新文件。

## 参数变更

- 新增参数：固定 `AP010.CZCE`、固定下载边界、`closed_state_ready`、同设备原子发布与四段 SHA 一致性。
- 修改参数：无策略参数；修改的是 Stage052 producer 对同一 `bar_id` 的采样语义。
- 删除参数：无。
- 正式策略/实盘参数：无任何修改。

## 最终数据结果

- 状态：`downloaded=1/1`、temp strict `1/1`、publish `1/1`、post audit `1/1`。
- 行数：`225`；区间 `2020-09-02 09:00:00 -> 14:59:00`。
- 日级 OHLC：`6876 / 6917 / 6750 / 6768`。
- 成交量合计：`178,576`。
- `225/225` 行为非平 OHLC，`225/225` 行成交量为正。
- 首根 open OI：`151,578`；末根 close OI：`159,149`；连续性断点 `0`。
- 重复键、越界、null、负 volume/OI、OHLC 关系错误：均为 `0`。
- 最终 SHA256：`5a019bd740451f0cbff930f065464e996a71bd0658dfbd178547510d7fa05ad1`。
- status/temp/publish/post SHA 完全一致，`publish_device_match=True`，旧文件已备份。
- 决策：`stage136_ap010_fill_window_ready_resume_stage135_canary`。

## 旧 Stage052 文件降级边界

- 全量只读扫描：`48` 个文件、`391,095` 行。
- 只有当前 AP010 `1` 个文件、`225` 行观察到闭合态。
- 其余 `47` 个文件、`390,870` 行均为 `open_only_legacy_snapshot`：OHLC 全平、volume 为 0。
- 这些旧文件仍可用于 Stage135 的第一根 `open` 成交价，因为 Stage135 不读取其 high/low/close/volume/OI；不得再把它们描述为完整 OHLCV/OI 分钟数据，也不得用于日内路径、止损穿价、成交量或持仓量研究。
- 当前 Stage208 路线已由 Stage135 canary 闸门决定是否继续，因此不为已关闭路线继续批量重下这 47 份文件。

## 独立 Agent 评估

- 独立 reviewer：`Plato`。
- 最终问题：`P0=0 / P1=0 / P2=3`，批准 AP010 最终文件作为 Stage135 成交输入。
- P2 边界：通用 closed-state gate 只要求至少一行非平/正 volume；测试以合成数据为主、缺最终文件集成断言；normalize 理论上会静默去重。
- 这些 P2 不阻断当前 AP010：本文件实际 `225/225` 行均非平且正 volume，重复键为 `0`，四段 SHA 一致。
- 数字与数据语义置信度：高；不能外推为其余 47 个旧文件也有闭合 OHLCV/OI。

## 回测记录字段

- 本阶段没有运行策略收益回测。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 验证

- Stage052/130/131/132/133/134/135/136 联合回归：`96/96` 通过。
- Stage052、Stage134、Stage135、Stage136 工具 `py_compile` 通过。
- `git diff --check` 通过。

## 反思

- 运行前过拟合判断：否。AP010 合约、日期和窗口由 Stage135 第一笔真实成交缺口机械确定，没有读取收益。
- 运行后过拟合判断：否。producer 修复是数据状态语义修正，不按品种表现、坏窗口或结果调参。
- 运行前继续价值判断：有。缺少 AP010 真实 open 时 Stage135 必须 fail-close。
- 运行后继续价值判断：Stage136 本身已完成；继续重下 47 个旧 open-only 文件对已关闭路线价值低。只在未来研究确实需要它们的 high/low/close/volume/OI 时，按具体数据合同重新下载并逐份闭合态验收。

## 输出

- 决策：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage136_ap010_canary_fill_window_backfill/rebuilt_c9_v2_stage136_ap010_canary_fill_window_backfill_decision_stage136_ap010_canary_fill_window_backfill_v1.json`
- 报告：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage136_ap010_canary_fill_window_backfill/rebuilt_c9_v2_stage136_ap010_canary_fill_window_backfill_report_stage136_ap010_canary_fill_window_backfill_v1.md`
- 旧文件审计：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage136_ap010_canary_fill_window_backfill/rebuilt_c9_v2_stage136_legacy_stage052_producer_content_audit_v1.csv`
