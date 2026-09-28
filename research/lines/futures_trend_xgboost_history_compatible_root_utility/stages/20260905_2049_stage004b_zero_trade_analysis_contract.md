# Stage004B 零成交空账户的离线表示修复

- 时间：2026-09-05 20:49 CST；本线数据适配，不改变策略、标签经济公式或任何已冻结输入。
- 原因：首个根事件2020-01-08 rb.SHFE被跳过后，截至2020-01-09无成交。vnpy portfolio calculate_result在无成交时直接返回；Stage847仅生成终点零损益行，故日历完整性门失败。
- 证据：该S receipt通过；trades为空；positions包含完整2019预热至2020-01-09日历，start/end_pos、成交数、所有损益/费用全0；raw daily只有2020-01-09、权益150000、所有损益/费用0。不是行情日期缺失。
- 允许操作：只读原S七表并核验哈希；要求分析日历在S持仓账逐日有覆盖、全账无成交/仓位/损益/费用、原单行权益等于资本，才把该原单行复制为逐日空账户曲线。仅补holding_pnl/trading_pnl/total_pnl三个由零账本严格决定的0列。未知缺列、非零值、缺日或已有成交一律拒绝。
- 不允许：改原CSV、改变原failure.json、改冻结batch driver、重跑S、用A权益代替S权益或直接赋0标签。
- 重新使用原validate_job核验前缀、特征、干预身份、指标和标签；只在其read_frame读取该任务daily时提供规范化视图。其余表原样。
- 写入：本任务目录新增normalized_daily.csv.gz、normalization_receipt.json及原格式label.json、archive_receipt.json；所有原7表无损归档。label额外绑定本分析工具与合同哈希。
- canary整批原failed状态不改；另写recovery_summary证明一个分析失败已解决。下一批从已核验label状态继续。
- 运行前过拟合判断：否，无新的收益选择或阈值；继续价值：是，修正零成交结果表示是保留全样本的必要步骤。无需reviewer。

## 同根原因下的pre_close补全

- 首轮离线校验进一步发现原引擎提前返回也没有计算positions.pre_close，全部保留初始化0。原逐日close_price仍完整。
- 依据同一引擎源码calculate_result逐日把close_prices传给下一日的语义，仅从S自身前一个日历日同合约close_price重建pre_close；首次无前值为0。不使用A价格，不更改任何仓位或损益。
- 重建后原4034条目标前持仓记录的所有字段与A精确相同。新增normalized_positions.csv.gz保留视图，原positions.csv不改，仅无损归档。
