# Stage002唯一执行失败：metadata写副作用

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 记录时间：2026-09-05 17:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage002唯一无标签事件资格执行结果
- 是否重要突破：否；属于基础设施合同反证，没有策略收益证据
- 是否触发A/B：否
- 是否触发reviewer：否；没有真实回测候选，更没有收益与回撤双改善

## 冻结身份

- campaign nonce：`54a45743c008d93eb695e01b8faa3466fceef53c4ce97d428c5ba9ad05dbd7cf`
- 输入文件数：`1416`
- 逻辑key SHA256：`8987c5c62fd8758fa6076c94bbdea3ce5b5f6d40405529c48a7ad5f875f94312`
- file contract SHA256：`5e0786df548061361f0ad8266b6cdc7a443eeddf88f64b3d522c5f192af9a453`
- runtime contract SHA256：`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`

## 唯一执行结果

- 结果：失败，A1退出码1，A2未启动。
- 失败阶段：`context["s901"].s513._metadata()`，位于唯一`_run_live_c9`调用之前。
- 精确错误：`file_write_forbidden:/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv`
- 调用链：`_metadata -> _c3_overrides -> build_official_stage78_overrides -> build_official_stage78_paths -> build_static18_plus_fu_universe -> DataFrame.to_csv`。
- 判定：正式metadata构造带有确定性派生品种池写副作用，违反Stage002“worker只写自身目录”的冻结合同；安全守卫行为正确。
- claim：已创建且`replay_permitted=false`，本线执行机会永久消费。

## 完整性复核

- 失败后、写本记录前，重新生成完整manifest并与冻结manifest逐项比较，结果为`true`。
- 目标品种池当前与冻结身份一致：size `6272`、mtime_ns `1788569431316444830`、SHA256 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`。
- 生产仓仍为detached HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`且clean。
- A1临时runtime与108MB数据库副本已删除；失败证据目录约552KB。
- 没有事件特征CSV、标签、模型、预测、候选策略或回测绩效产物。

## 回测结果字段

- 期末权益：不适用；未进入回测
- 总收益：不适用；未进入回测
- 最大回撤：不适用；未进入回测
- Sharpe：不适用；未进入回测
- 总滑点：不适用；未进入回测
- 总交易次数：0；正式回放未调用
- 胜率：不适用；未进入回测

## 过拟合与继续价值

- 当前是否过拟合：否。失败发生在事件和绩效不可见阶段，没有按结果修改特征、阈值、年份或样本门。
- V2是否值得继续：否。唯一执行已消费，任何修复后重跑都会违反预注册。
- 新方向是否值得继续：有条件值得。V3必须先在零正式回放下完成metadata写路径枚举和worker内重定向，并证明派生品种池与冻结文件逐bytes相等；否则停止生产模块直载。

## 后续规划

1. 新建独立V3 metadata纯读预检线，不修改V2任何执行产物或claim。
2. 静态读取完整metadata调用链，枚举所有文件写入口；不得通过放宽workspace写权限绕过。
3. 在V3先运行A1/A2 metadata-only冷进程，不调用`_run_live_c9`；只有全部写入worker目录、输出字节一致且敏感计数为0时，才重新预注册事件资格。
