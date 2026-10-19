# Stage029：可选并行复盘适配器样本验证与冻结测试

- 时间：2026-10-18 21:09 CST。
- 研究线：`futures_trend_full_market_noai_one_lot`。
- 不是重要突破版本；本阶段仅处理冻结复盘上下文的只读计算，新增金融回测次数 0、下载次数 0、源数据修改 0；未修改 canonical Stage038 函数、金融入口或任何旧输出。
- 新增可选入口：`tools/stage025_parallel_context_recap.py`，最多 4 个 spawn worker；按品种/交易所分发该组 mapping 与可能引用的精确/主力合约日线。Stage001 默认串行；可选 callback 由新入口使用，记录入口/适配器运行代码 SHA，运行期间变动则拒绝写页。

## 真实冻结样本验证

- 来源：`outputs/run_20261018_lifecycle_unlimited_v2/`。
- manifest SHA256：`b0893921b612ed284458625bd6405fef5a994a36beb9214839a8a4a7b27be983`。
- 完成证据：`stages/stage025_parallel_real_sample_validation_v1.json`，结论 **PASS**。
- 12 笔、10 个品种，包含多头/空头、实际 execution-only 退出报价覆盖，合计 26 个背景缺口日、4,382 个主力代理背景日。样本按产品、方向、报价覆盖和缺口结构选择，没有按利润选择。
- 串行与 4 worker 并行：所有 context DataFrame 值、attrs、日期序列逐值相同；最终 canonical records 与 chart manifest 完全相同。
- 样本 context：串行 `1.265416s`，并行 `0.985233s`；单次串行 records `0.691523s`。样本偏早期且进程启动开销占比较高，不能据此宣称四倍加速，也不把粗线性外推当可靠全量耗时预测。
- 与完整 PASS 证据一致的验证脚本已保留为 `tools/stage025_validate_parallel_contexts_v1.py`，SHA256 为 `449589ce61c346031ab4c4e87ef03570c0170bfc4db973ec1ba2b83a25fb5142`，与 JSON 的 validator SHA 一致。扩展采样脚本 `tools/stage025_validate_parallel_contexts.py` 也保留在本线。
- 在收到继续原串行且停止额外验证的指令前，第二组长历史样本验证已开始；收到后已中断（exit 130），没有第二组 PASS 结果、没有 `validation_v2.json`、没有生成任何真实复盘页。不得把这次中断描述成完成验证。

## 本次交付决策与最终测试

- **并行入口未用于本次正式交付。** 根任务决定继续原串行 session `92688`；本阶段没有中断它或写同名 output。旧进程加载的是 callback 增强前的适配代码，其原 summary 只记录 canonical SHA，不宣称含新 adapter 自 SHA。最终页仍由根任务完成独立逐笔/MA/JavaScript/浏览器验收与通用 finalizer。
- 文件冻结后运行：`/Users/mac/Desktop/fian/.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_*.py'`。
- 最终结果：**86 tests，11.501 秒，全部通过**。其中新增并行 fixture 3 项先 RED 再 GREEN，包含 serial/parallel 最终 records 等价、最多 4 worker 闸门、独立输出与代码 provenance。
- `git diff --check` 通过。测试导入第三方模块会打印 TqSDK 免责声明，本阶段没有创建 TqApi、执行金融回放或下载行情。
- 参数/金融结果：没有新增、修改或删除策略参数；没有新增、替换或删除任何金融绩效结果。worker 数只属于可选展示计算参数。

## 反思

- 开始与结束过拟合判断：**否**。没有调整交易政策、信号、阈值、品种或收益目标；要求图表结果逐值等价，性能不能以牺牲数据边界换取。
- 继续价值判断：**是，限于保留可复验的可选工具**。样本证明可安全复用，但当前串行已取得进展，重启全量不保证缩短总交付时间，因此本次不切换；不追加性能扫描或金融重跑。
