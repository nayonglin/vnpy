# Stage137 static 证据机器精度与锚点追溯修复

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：代码与静态测试
- 记录时间：`2026-07-12 16:37 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：运行前证据合同修复
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Pandas nullable integer、RFC 4180、in-toto materials digest。
- 我的判断：三个问题不改变 attempt 4 的内容门禁，但 price 锚点与机器可读表头会直接影响 canary 后的独立复算；必须在表现未知时修复。

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
- 样本过滤：冻结 AI/golden 不变
- 策略/归因口径：source mtime 精度、静态空表 schema、price anchor lineage

## 结果

- 期末权益：未计算
- 总收益：未计算
- 最大回撤：未计算
- Sharpe：未计算
- 总滑点：未计算
- 总交易次数：未计算
- 胜率：未计算
- 其他关键指标：Stage137 `139/139`、扩展相邻 `38/38`、compile/diff/whitespace 通过；独立审查后新增 post-chart 全证据 bytes binding，测试数不变且全绿

## 输出文件

- report：`.superpowers/sdd/task-4-correction-8-report.md`
- summary：无
- orders：无
- daily：无
- quality：专用 unittest 与最新 `task-3-diff.md`

## 结论

- 本阶段结论：三个 P2 均已在收益未知时 TDD 修复；随后发现并修复 post-chart 磁盘证据未绑定的 P1，交易计算未改变。
- 是否进入下一步：等待独立 reviewer。
- 下一步：审查通过后只重跑四锚点 static audit，验证真实输出 mtime 假阳性为 0、空表可读、price 锚点行数正确。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只修复证据结构和整数精度，未查看卫星收益或改变策略。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：修复后 canary raw evidence 可直接按锚点复算，减少收益已知后的口径争议。

## 合入建议

- 是否更新本线 `LINE.md`：暂不
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
