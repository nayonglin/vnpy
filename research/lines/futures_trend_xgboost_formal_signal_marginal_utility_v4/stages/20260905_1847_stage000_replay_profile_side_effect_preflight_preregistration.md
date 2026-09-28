# Stage000 replay-profile写副作用预检预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 记录时间：2026-09-05 18:47 CST
- 阶段性质：正式回放profile准备链的零回放I/O隔离资格
- 是否重要突破：否；没有事件、标签、模型或绩效
- 是否触发A/B：否
- 是否触发reviewer：否

## 上游反证与静态调用图

- V3 Stage002的显式`_metadata()`已在私有目录成功，但重定向上下文退出后，`_run_live_c9 -> s847._c9_profile -> s830._cap_profile -> s827._profile -> s825._profile -> stage819 -> stage813 -> stage777`再次调用`build_static18_plus_fu_universe()`。
- `stage777.build_official_candidate_stage777_paths()`会依次调用`build_static18_plus_fu_universe()`和`build_ai_satellite_post_signal_eligibility()`。
- `_run_live_c9`在profile后还调用`build_official_live_strategy_overrides()`；该函数从Stage847候选配置构造正式override，必须纳入同一重定向生命周期。
- `_run_live_c9`函数体的报告CSV写入不在该函数内，而在其调用者主流程；本预检不调用主流程或引擎。

## 固定执行合同

- A1/A2每个worker只调用一次`s901.s513._metadata()`、一次`s901.s847._c9_profile(metadata)`和一次`live_config.build_official_live_strategy_overrides()`。
- 三步全部位于同一个`redirect_metadata_outputs`上下文内；退出后两个原始Path对象必须按身份恢复。
- 不调用`_ensure_c9_minute_bars`、`_run_live_c9`、`_run_profile`或策略引擎。
- 两个最终派生CSV必须与冻结正式期望文件逐bytes一致。
- profile只发布规范化身份：profile名、strategy class模块/类名、spec profile、capital关键字段、override键集合与稳定SHA；不发布绩效。
- A1/A2必须PID不同、portable receipt完全一致。
- 外部写入、网络、子进程、正式回放、标签、holdout、模型、预测、CTP、账户和订单计数全部为0。

## 停止条件

- 通过：只允许另行预注册新的事件资格；不直接回放、打标签或训练。
- 出现未枚举写点、派生bytes不等、profile不一致或路径未恢复：V4停止，不放宽workspace写权限。
- reviewer保持关闭，直至出现收益与回撤双改善的稳健回测候选。

## 回测结果字段

- 期末权益：不适用；零回放
- 总收益：不适用；零回放
- 最大回撤：不适用；零回放
- Sharpe：不适用；零回放
- 总滑点：不适用；零回放
- 总交易次数：0
- 胜率：不适用；零回放

## 调研判断

- Python `contextlib`的`try/finally`语义适合保证跨多步profile构造仍恢复模块Path：https://docs.python.org/3/library/contextlib.html
- pandas允许显式路径作为CSV目标，继续采用模块Path窄替换，不全局猴子补丁：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
- 判断：V3失败不是特征假设反证，而是重定向生命周期过短；先做profile-only预检有继续价值，直接再开完整回放没有。
