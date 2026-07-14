# Stage001 候选边际风险贡献静态审计通过

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 当前模式：研究候选 / 回测前静态闸门
- 记录时间：`2026-07-12 19:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：实现、数据合同和单元测试审计；尚未运行收益回测
- 是否重要突破：否
- 是否触发A/B：是；当前仅定义冻结的 A/C canary，不接入正式版

## 外部调研与判断

- 参考资料：Alexander/Fabozzi 的 leave-one-out 风险贡献分解、Roncalli 风险预算、Ledoit/Wolf 收缩协方差、scikit-learn `LedoitWolf` 官方文档、`pysystemtrade` 风险配置实践。
- 我的判断：本阶段应使用标准可加总的 component risk contribution，而不是把 leave-one-out 方差差直接当成边际贡献；风险输入必须使用实际合约严格 T-1 收益，不能用当前主力映射回填历史，也不能跨合约拼接收益。

## 本次变更

- 新增脚本：`tools/stage001_candidate_marginal_risk_contribution_engine.py`
- 新增测试：`tests/test_candidate_marginal_risk_contribution_stage001.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：精确共同窗口 `63` 日；Ledoit-Wolf 收缩协方差；`scale=min(1, IC/RC)`；整数手数 `max(1, floor(before*scale))`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：实际合约收益面板 `2018-01-02` 至 `2026-06-30`
- 账户规模：计划 canary 为 `150,000`；本阶段未运行回测
- 成本口径：计划沿用 Stage137 冻结的真引擎 1x 成本；本阶段未产生收益统计
- 样本过滤：仅 current-AI 历史允许的 `567` 个实际合约；所有收益日期严格早于候选日；每个日批次要求全部暴露有精确 `63` 个共同有效日
- 策略/归因口径：Stage847 原始 planner 完成后只缩减当批候选手数，不放大、不清零、不替补、不改变候选集合；历史不足时整批 no-op

## 静态审计结果

- 收益面板：`116,445` 行、`567` 合约、`2,058` 日期
- 有效收益：`115,877` 行
- 合约覆盖：`567/567`
- 重复键：`0`
- 未来日期：`0`
- 读前/读后源文件漂移：`0`
- 面板 SHA256：`f7309d2ea3709731c2cbcebd8bf6b57e92309ec20367a885426421da86b04da9`，连续两次构建一致
- 2020 锚点基准 would-open 批次：`265`
- 可计算批次：`264/265`
- 唯一 unavailable：`2021-04-09 lh2109.DCE`，共同有效历史 `58` 日；按事前规则整批 no-op
- 单元测试：`.py311/bin/python tests/test_candidate_marginal_risk_contribution_stage001.py`，`17/17` 通过
- 语法检查：通过

## 回测结果

- 期末权益：N/A（未运行）
- 总收益：N/A（未运行）
- 最大回撤：N/A（未运行）
- Sharpe：N/A（未运行）
- 总滑点：N/A（未运行）
- 总交易次数：N/A（未运行）
- 胜率：N/A（未运行）
- 其他关键指标：静态数据合同通过；真引擎 canary 仍受独立代码审查硬闸门约束

## 输出文件

- report：本记录
- summary：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_data_audit_stage001_candidate_marginal_risk_contribution_engine_v1.json`
- returns：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_actual_contract_returns_stage001_candidate_marginal_risk_contribution_engine_v1.csv`
- readiness：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_baseline_batch_readiness_stage001_candidate_marginal_risk_contribution_engine_v1.csv`
- source manifest：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_source_manifest_stage001_candidate_marginal_risk_contribution_engine_v1.csv`

## 结论

- 本阶段结论：静态数据和单元测试闸门通过；这不代表策略有效，也不代表允许晋级。
- 是否进入下一步：等待独立审查员确认无 P0/P1 后，才运行四锚点 1x 真引擎 canary。
- 下一步：冻结运行环境，执行 A/C 四锚点；任一预声明收益保留、回撤、水下期、来源一致性或运行时审计门槛失败即停止，不做同方向救援调参。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；本阶段没有观察候选收益。
- 原因：设计、数据合同、锚点和通过门槛均在回测前冻结；唯一短历史批次采用保守 no-op，没有补数或缩短窗口。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但仅限一次冻结 canary。
- 原因：该机制直接针对同向候选的条件相关风险，和此前按品种质量或卫星仓位救援不同；若 canary 失败，应关闭该具体实现而不是继续追逐参数。

## 合入建议

- 是否更新本线 `LINE.md`：canary 和独立结果审查后统一更新
- 是否更新 `research/registry.md`：否；新研究线已登记
- 是否追加根目录 `memory.md/back_log.md`：否；静态审计不是重要突破或正式候选
