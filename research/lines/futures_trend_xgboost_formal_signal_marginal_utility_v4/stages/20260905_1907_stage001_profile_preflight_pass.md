# Stage001 正式profile构建预检通过

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 记录时间：2026-09-05 19:07 CST
- 是否重要突破：否；属于工程准备，尚无XGBoost绩效。
- 结果：`passed`；A1/A2 PID不同、配置和metadata可移植合同完全一致。
- 合约801、品种19；两个派生CSV与冻结文件逐bytes一致。
- 输入1446项；逻辑键SHA `f0f5500929a833b7af4b7d0a2e4a6770aa91e31934a06b725960e98b6c1ec7b6`。
- 文件合同SHA `9afdc7860c020be8ec4f900170283c191b23c0bd259c9c2d3ae444d748c9fd0c`。
- runtime SHA `04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`。
- 正式release仍为m0005、执行身份C9/15w；生产worktree检查为空。
- `_c9_profile`返回的中间capital为30w；`_run_live_c9`源码随后用正式15w替换capital。预检未执行这一步，后续事件runner须硬验证实际返回的15w live spec。

## 工程修正与测试

- 第一次集成测试发现比较器把A1/A2私有派生文件路径的差异计入参数SHA。
- 修正：只将已逐bytes通过的两个派生文件精确路径映射到冻结文件身份；不替换目录前缀，不忽略其他路径或参数。
- 这是无回放测试期间的比较器修复，未消费事件claim、未观察事件或标签；经济假设和统计门槛均未变。
- 验证：8项测试通过（48.54秒），涵盖独立路径等价、参数变化仍不等、未知路径变化仍不等、异常恢复、真实双冷进程。
- 持久执行命令：`.py311/bin/python -B research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage001_replay_profile_preflight.py --run --output-dir research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v4/artifacts/stage001_replay_profile_side_effect_preflight`。
- 结果路径：本线`artifacts/stage001_replay_profile_side_effect_preflight/summary.json`。
- 正式回放0、网络0、全部敏感计数0；runtime清理完成；reviewer未启动。

## 变更与回测字段

- 新增：profile预检工具与测试；修改：私有路径的精确身份规范化；删除：无。
- 策略参数新增/修改/删除：均无。
- 回测结果新增/修改/删除：均无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、胜率：不适用；本阶段零回放。
- 总交易次数：未生成交易。

## 反思与下一步

- 运行前/后过拟合判断：本工程修复不属于收益拟合；历史研究整体仍有多重试验风险。
- 运行前/后继续价值：是；已通过完整profile准备链，可推进固定事件与12特征提取。
- 下一步：预注册V4 Stage002，重定向覆盖整个正式回放生命周期，复用冻结数据/特征/样本门和协议。
