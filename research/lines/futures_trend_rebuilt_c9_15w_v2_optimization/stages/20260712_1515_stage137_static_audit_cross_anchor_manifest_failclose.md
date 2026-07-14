# Stage137 四锚点 source manifest 跨起点集合误判 fail-close

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`audit`
- 记录时间：`2026-07-12 15:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：运行前静态身份审计失败归因
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Python `hashlib` 文件摘要文档；in-toto Attestation Framework 的 `ResourceDescriptor` / materials 规范及 bit-for-bit artifact identity 说明。
- 我的判断：每次执行实际读取的材料应按唯一 path/name 与 SHA256 绑定；不同历史起点允许读取不同的文件子集。正确合同应要求锚点内双 worker 的路径集合和 size/SHA 完全一致，跨锚点仅对重叠路径要求 size/SHA 一致，最终 manifest 则覆盖四锚点路径并集并重新逐字节验证。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：四个冻结锚点 `2020-01`、`2022-01`、`2022-07`、`2026-01`，统一终点 `2026-06-30`
- 账户规模：冻结 C9 `150,000`；本次未进入卫星账本
- 成本口径：未运行绩效或成本计算
- 样本过滤：冻结 current-AI snapshot，SHA256 `fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc`
- 策略/归因口径：每个锚点两个独立 current-C9 subprocess；14 组 raw/derived frame canonical identity；在 satellite replay 前 `continue`

## 结果

- 期末权益：未计算
- 总收益：未计算
- 最大回撤：未计算
- Sharpe：未计算
- 总滑点：未计算
- 总交易次数：未计算
- 胜率：未计算
- 其他关键指标：前三个锚点完成各自双 worker 身份审计；第四个锚点运行后，最终跨锚点汇总在 `final_source_manifest` 阶段 fail-close。未生成完整 Stage137 output，未进入 satellite replay/canary/full。

## 输出文件

- report：无
- summary：无
- orders：无
- daily：无
- quality：`outputs/stage137_current_c9_quality_one_way_satellite_failures/20260712_151443_938018_66121_audit_failclose.json`

## 结论

- 本阶段结论：`finalize_worker_source_manifest()` 把 8 份 worker manifest 全部与第一个 `2020-01` manifest 做完整路径集合相等比较；而后启动的锚点按区间自然不读取早期合约日线/分钟文件，因此大量路径只存在于较早锚点。当前证据指向跨锚点合同误写，不是已证明的源文件内容漂移。
- 是否进入下一步：否；canary/full 继续关闭。
- 下一步：等待独立 agent 复核根因；若批准，先以 adversarial tests 冻结“锚点内相等、跨锚点重叠一致、final 为并集且重哈希”的合同，再修改生产代码并重新独立审查。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只验证输入身份、可重复性和血缘，没有查看或使用 Stage137 收益来调整 selector、`25%`、锚点或绩效门槛。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：fail-close 在收益计算前暴露了身份合同的集合语义问题；修复后才能可信地判断 Stage137 是否有效。若不修复，任何后续绩效结论都没有可审计来源闭环。

## 合入建议

- 是否更新本线 `LINE.md`：暂不，Stage137 尚未形成绩效结论
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
