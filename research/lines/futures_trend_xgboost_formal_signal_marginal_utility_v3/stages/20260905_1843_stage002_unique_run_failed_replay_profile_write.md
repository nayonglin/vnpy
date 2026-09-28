# Stage002唯一执行失败：回放profile再次触发派生文件写入

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v3`
- 记录时间：2026-09-05 18:43 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage002唯一无标签事件资格执行结果
- 是否重要突破：否；属于执行链副作用反证，没有策略收益证据
- 是否触发A/B：否
- 是否触发reviewer：否；没有事件结果或有价值回测候选

## 冻结身份

- campaign nonce：`dfc1ccc40d57b9d9d1c1f0dd5ca5e048de1ef795bed3a00f1db38c7088d75199`
- 输入文件数：`1433`
- 逻辑key SHA256：`10484e319e3b5cc1f223658469ab88cd8c5d978c1e8d152bf3776f84d53a8c19`
- file contract SHA256：`077bcb61d7d9800c6ea8b787346e7711d84848dd8fed78104cb943f8720a4c99`
- runtime contract SHA256：`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`

## 唯一执行结果

- 结果：失败，A1退出码1，A2未启动。
- A1已成功完成私有`_metadata()`构造，两份派生CSV保留在失败证据目录并与冻结期望文件逐bytes一致。
- `_run_live_c9`入口被调用一次，但尚未完成profile构造、策略回放或事件提取。
- 精确错误：`file_write_forbidden:/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv`。
- 新调用链：`_run_live_c9 -> stage827._profile -> stage825._profile -> stage819_cfg.build_official_candidate_stage819_30w_overrides -> stage813 -> stage777.build_official_candidate_stage777_paths -> build_static18_plus_fu_universe -> DataFrame.to_csv`。
- 根因：V3只在显式`_metadata()`调用期间保持两个Path重定向；退出上下文后恢复正式Path。正式回放的profile构造会再次调用相同派生构造函数，因此第二次写入落回workspace符号链接目标并被守卫阻断。
- 安全判断：阻断正确，不能通过把workspace加入写白名单或修改已冻结runner来补跑。
- claim已创建且`replay_permitted=false`，V3 Stage002执行机会永久消费。

## 完整性复核

- 失败后、写本记录前，重新生成1433文件manifest并与冻结manifest逐项比较，结果一致。
- A1临时runtime和112537600 bytes数据库副本已删除；A2目录不存在。
- A1没有`event_features.csv`或成功receipt，顶层没有事件输出。
- workspace正式品种池仍为size `6272`、mtime_ns `1788569431316444830`、SHA256 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`。
- workspace正式post-signal eligibility仍为size `51303`、mtime_ns `1788569431333731097`、SHA256 `fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`。
- 生产仓保持clean detached HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- 没有标签、模型、预测、候选策略、收益曲线或绩效结果。

## 回测结果字段

- 期末权益：不适用；回放未开始执行策略
- 总收益：不适用；无组合结果
- 最大回撤：不适用；无组合结果
- Sharpe：不适用；无组合结果
- 总滑点：不适用；无交易结果
- 总交易次数：不适用；无事件或交易结果
- 胜率：不适用；无标签或交易结果

## 过拟合与继续价值

- 当前是否过拟合：否。失败发生在事件与绩效不可见阶段，没有按结果调整特征、资格门、年份、方向或品种。
- V3是否值得继续：否。Stage002唯一执行已消费，任何同线修复后重跑都会违反预注册。
- 新方向是否值得继续：有条件值得。下一条线必须先静态枚举`_run_live_c9`前置profile调用图，证明两个Path重定向需要覆盖的完整生命周期，并用不进入策略回放的profile-only预检验证；不能直接再开一次完整事件回放。

## 后续规划

1. 新建独立V4 replay-profile副作用预检线，不修改V3任何执行产物或claim。
2. 静态枚举`stage827._profile`及下游全部写入口，确认是否仍只有已知两个派生CSV。
3. 先运行零策略回放的profile-only双worker预检，保持路径重定向覆盖`_metadata + _profile`完整生命周期。
4. 只有profile-only输出和返回语义双worker一致后，才讨论新的事件资格合同；reviewer继续关闭。
