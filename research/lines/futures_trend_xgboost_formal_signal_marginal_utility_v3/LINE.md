# 正式信号账户边际效用XGBoost V3线

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v3`
- 创建时间：2026-09-05 17:43 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 资产/策略：商品期货趋势 / 当前正式逻辑回归选品 + C9/15万根入场事件的XGBoost二级过滤
- 当前状态：V3闭线。Stage001 metadata-only双冷worker预检通过；Stage002唯一执行在A1进入`_run_live_c9`后的profile构造阶段被外部写守卫阻断，A2未启动、无事件输出。新反证是回放profile会再次调用`build_static18_plus_fu_universe()`；仅在显式`_metadata()`期间重定向不足。claim已消费且禁止V3重跑，生产/workspace正式文件均未变化。
- 上游证据：V2 Stage002唯一执行在A1的`_metadata()`阶段被workspace写保护阻断；`_run_live_c9`尚未调用，V2 claim已消费并闭线。
- 线上材料身份：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`
- 线上执行身份：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / 15万元

## V3目标

- 静态枚举`_metadata()`完整调用链中的全部文件写入口，不能靠多次真实失败逐个发现。
- 在A1/A2隔离冷worker中只调用`_metadata()`，正式回放调用数固定为0。
- 仅把确定性派生品种池输出重定向到worker私有目录；不把workspace或生产目录加入写白名单。
- 派生文件必须与冻结正式输入逐bytes一致，A1/A2 metadata规范化结果必须一致；任何不一致即闭线。

## 固定设计原则

- 使用窄范围上下文管理器替换拥有该全局变量的生产模块`UNIVERSE_PATH`，在成功或异常后都恢复原对象。
- 不全局替换`DataFrame.to_csv`，不跳过`build_static18_plus_fu_universe()`，不直接复用已有文件来掩盖生成语义。
- worker私有目录、文件名、源输入SHA和期望输出SHA都必须显式绑定。
- metadata-only预检通过前，不创建新的事件资格claim，不调用`_run_live_c9`。

## 在线调研与判断

- Python `tempfile`官方文档说明高层临时目录支持上下文管理和自动清理，并建议显式传入目录位置。
- Python `contextlib`官方文档说明可用`try/finally`型上下文管理器保证异常路径也恢复资源。
- pandas官方文档确认`DataFrame.to_csv`的目标可为路径或文件对象；本线因生产函数使用模块全局路径，采用模块变量窄替换而不是全局I/O猴子补丁。
- 判断：V2失败是可隔离的确定性派生文件副作用，但只有完整静态枚举和双worker metadata-only证据通过后，才可认为有继续价值。

## Reviewer策略

- metadata分析、代码修改、单元测试、预检和失败诊断均不启动reviewer。
- 只有未来真实回测同时改善收益和最大回撤，并通过预注册基础稳健性门形成有价值候选后，才启动独立reviewer。

## 过拟合与继续价值

- 当前是否过拟合：否。没有事件、标签或绩效可见，研究对象是I/O副作用和可复现性。
- 当前是否值得继续：有条件值得。若metadata的全部写副作用都能在不改变返回语义的前提下隔离并精确复现，则继续；否则停止生产模块直载路径。

## TODO

1. 不修改V3 runner、claim、冻结文件或失败产物，不重跑V3 Stage002。
2. 新建独立V4 replay-profile副作用预检线，先静态枚举`stage827._profile`全部写入口。
3. 用零策略回放的profile-only双worker预检证明重定向生命周期和返回语义，再决定是否值得新建事件资格合同。
4. reviewer继续保持关闭；只有未来真实候选同时改善收益和最大回撤并通过稳健性门才启动。
