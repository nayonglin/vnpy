# 正式信号账户边际效用XGBoost V2线

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 创建时间：2026-09-05 16:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 资产/策略：商品期货趋势 / 当前正式逻辑回归选品 + C9/15万根入场事件的XGBoost二级过滤
- 当前状态：已闭线。Stage002唯一执行在A1调用`_metadata()`时失败；正式配置链调用`build_static18_plus_fu_universe()`并尝试把品种池写入workspace `backtest_outputs`，被只读守卫阻断。失败发生在`_run_live_c9`之前，没有事件、标签、模型、预测或回测结果；claim已消费，V2禁止修复后重跑。失败前冻结1416项输入，失败后、记录更新前全量manifest逐项一致，目标文件未变化，生产仓clean，临时数据库副本已删除，未启动reviewer。
- 上游失败证据：V1 Stage001唯一执行在A1导入阶段被`matplotlib.font_manager`的`fc-list --help`触发阻断；预置字体缓存后的只读诊断又发现正式材料resolver调用`git cat-file -e`。V1已闭线且禁止重跑。
- 线上材料身份：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`
- 线上执行身份：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / 15万元

## V2目标

- 保留V1的经济对象：逻辑回归继续决定月度品种池，C9方向和执行逻辑保持主体，XGBoost未来只可能作为根入场事件的二级skip过滤器。
- 已证明生产策略模块图可以在隔离冷进程中完成纯导入，同时外部进程、网络、生产写入、CTP、账户、订单、标签、fit与predict计数全部为0。
- 当前只允许冻结Stage002精确输入合同并执行一次无标签正式基准事件资格；不得读取未来收益、生成标签、训练XGBoost或运行候选策略。

## 固定修复原则

- 不放宽子进程禁令，不把`fc-list`、`system_profiler`或`git`加入白名单。
- Matplotlib缓存必须作为版本、平台和SHA绑定的只读输入进入隔离runtime；缓存不匹配或导入仍尝试外部进程即失败。
- 正式材料resolver的commit成员关系校验只能替换为显式、窄范围、fail-close且有等价测试的无进程身份适配；不得跳过release、manifest、CURRENT或全部payload身份校验。
- 生产代码目录保持只读，不修改`/Users/bytedance/Desktop/person/vnpy_production_live`。
- 先枚举完整导入期外部进程依赖，再冻结实现合同；不采用遇到一个放行一个的补丁路线。

## 阶段边界

- Stage000：只读枚举导入链和全部外部进程依赖，预注册V2纯导入合同。
- Stage001：实现并测试独立的纯导入预检；只输出模块身份、敏感计数和可复现性，不运行`_run_live_c9`。
- Stage002：仅在Stage001通过后，重新冻结正式基准事件与12项特征资格的唯一执行合同。
- Stage003及以后：只有前序资格全部通过后才允许讨论标签、固定浅树、purged expanding walk-forward和未来shadow。

## 闭线结论

- V2验证了导入期外部进程可在不放宽边界的情况下消除，但反证了“正式metadata构造是纯读操作”的假设。
- 不允许在V2把workspace输出目录加入写白名单，也不允许删除claim或复制V2参数重跑。
- 后续如继续，应新建V3并先做零正式回放的metadata预检：静态枚举全部写路径，把确定性派生文件重定向到worker目录，并逐bytes核对其与冻结正式输入相等；该预检通过前不得再申请事件资格唯一运行。

## Reviewer策略

- 常规代码修改、单元测试、导入预检和失败诊断不启动reviewer。
- 只有真实回测结果同时改善收益与最大回撤、并通过预注册的基础稳健性门，形成有价值候选版本后才启动独立reviewer。

## 过拟合与继续价值

- 当前是否过拟合：否。失败发生在事件生成前，没有看到样本覆盖、标签或绩效，未据结果调整任何研究阈值。
- 未来风险：高。历史样本小且被多次观察；任何模型阶段仍需固定特征、阈值和walk-forward边界，并以后续真实前向样本为最终依据。
- 是否值得继续：V2本线否，新的metadata纯读预检线有条件值得。只有能在零正式回放下证明全部确定性写副作用被隔离且语义不变，才值得重新预注册事件资格。
