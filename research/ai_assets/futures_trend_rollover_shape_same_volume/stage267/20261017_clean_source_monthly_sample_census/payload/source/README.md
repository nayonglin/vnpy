# Stage267 统一研究训练来源

固定原18池Floor35/20万元/risk0.045，从已验收clean库重算2010-01-04—2026-10-14。一轮金融源回放，无新训练或扫参。它不是当前C9实盘正式回测。

- `source_summary.json`：执行代码/模型/数据SHA、冻结口径、来源财务诊断与输出指纹。
- `source_opportunity_by_year.csv` / `source_utility_description.json`：各年信号、交易、缺口和严格资格解释。
- `source_position_changes.csv`：逐合约日PNL（大文件，仅本机）；`source_entry_candidate_snapshots.csv`：候选。
- `contract_epoch_identity.csv`：无冲突YYYYMM合约身份；`product_coverage.csv`：映射、真实bar、连续120日期覆盖、持仓缺bar。
- `source_calendar.csv`：RQ真实交易日历包含未来月尾，仅用于识别月末；未来行情没有加入。
- `pairwise_input_audit.csv` / `real_bar_fill_audit.csv`：asof与真实成交证据。
- 最终月度样本在 `../stage267_monthly_samples_final/`，535有信息行/54月；初版 `../stage267_monthly_samples/` 只保留构造过程证据，不作为活动结果。
- 独立源结果 `../stage267_independent_review/source_only_review.json`；月度结果 `../../tools/stage267_monthly_independent_review.json`。

语义限制：上游固定pairwise权重2020—2022训练，早期是后验政策重算；完整120/60标签不等于历史PIT/OOS。固定现代18池、共享账户路径、原未定义衍生统计置0及缺bar估值传播边界均见最终中文阶段记录。不改主库/原映射/正式池/生产。
