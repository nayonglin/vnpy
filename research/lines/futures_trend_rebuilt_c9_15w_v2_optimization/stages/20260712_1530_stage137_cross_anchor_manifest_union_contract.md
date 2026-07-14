# Stage137 跨锚点 source manifest 并集合约修复

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：代码与静态测试
- 记录时间：`2026-07-12 15:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：运行前数据身份合同修复
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Python `hashlib`；in-toto Attestation Framework materials/resource digest；Bazel action input/remote cache 模型。
- 我的判断：不同回测起点是不同 action，允许读取不同历史文件子集；完整性来自每个 action 的输入 digest、重叠材料一致和最终并集闭环，不来自强迫 action 输入集合相同。

## 本次变更

- 新增脚本：无
- 修改脚本：Stage137 production 与专用 unittest
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：未运行回测
- 账户规模：未运行回测
- 成本口径：未运行回测
- 样本过滤：current-AI/golden 冻结不变
- 策略/归因口径：source manifest 身份合同静态测试

## 结果

- 期末权益：未计算
- 总收益：未计算
- 最大回撤：未计算
- Sharpe：未计算
- 总滑点：未计算
- 总交易次数：未计算
- 胜率：未计算
- 其他关键指标：首轮 Stage137 `136/136`、相邻 `28/28`；独立审查后修复 mtime-only 最终复验，最新 Stage137 `137/137`、扩展相邻 `38/38`、compile/diff/未跟踪文件 whitespace 通过

## 输出文件

- report：`.superpowers/sdd/task-4-correction-7-report.md`
- summary：无
- orders：无
- daily：无
- quality：专用 unittest

## 结论

- 本阶段结论：P1 两处集合语义已按预声明修复；独立审查发现并修复最终 mtime-only 误判。合法不同锚点子集和同内容 mtime rewrite 可通过，size/SHA 漂移或并集不闭合仍 fail-close。
- 是否进入下一步：等待第二位新的独立 reviewer。
- 下一步：独立审查通过后只重跑四锚点 static audit；canary/full 继续关闭。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有读取 Stage137 收益或修改策略参数，只修复可复验输入合同。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：只有 identity/source 闭环通过，后续收益与回撤才具备可信统计口径。

## 合入建议

- 是否更新本线 `LINE.md`：暂不
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
