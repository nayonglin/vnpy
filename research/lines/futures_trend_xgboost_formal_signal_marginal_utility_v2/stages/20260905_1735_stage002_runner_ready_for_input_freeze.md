# Stage002 runner完成并进入输入冻结

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 记录时间：2026-09-05 17:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：正式A路径根事件与12项决策时点特征的一次性无标签资格runner实现
- 是否重要突破：否；尚未执行正式回放，没有事件资格或模型收益证据
- 是否触发A/B：否；不运行XGBoost候选或A/C绩效对照
- 是否触发reviewer：否；只有真实回测同时改善收益与最大回撤并通过基础稳健性门后才启动

## 本次改动

- 新增Stage002全量输入manifest，绑定1416个生产、正式材料、行情、映射、依赖、V2工具、测试、预注册和Stage001证据文件。
- 新增固定输入冻结凭证校验；精确文件数、逻辑key SHA、file contract SHA和runtime SHA不匹配时，在claim和正式回放前失败。
- 新增`O_CREAT|O_EXCL`一次性claim；claim存在即执行机会已消费。
- 新增A1/A2隔离冷worker：独立108MB数据库副本、空setting、portable Matplotlib缓存、release attestation、macOS sandbox、`python -I -S -B`。
- 安全守卫仅允许每个worker调用`_run_live_c9`一次；网络、外部进程、生产写、标签、holdout、模型导入、fit、predict、候选策略、CTP、账户和订单继续禁止。
- worker只输出正式根事件特征CSV和安全回执；组合曲线、交易、持仓和live spec在提取候选后立即释放。
- 父进程固定使用`1e-12`比较A1/A2，并应用预注册覆盖门；失败发布失败证据、删除数据库副本并闭线，成功只发布无标签事件资格产物。

## 固定参数

- 回放区间：`2020-01-02`至`2026-08-28`
- 事件总数：不少于150
- 完整年份：2023、2024、2025，各不少于24
- long/short：各不少于40
- 品种数：不少于15
- 12项特征：各不少于2个唯一值，其中至少8项不少于10个唯一值
- A1/A2数值绝对误差：`1e-12`
- 固定`fu.SHFE`：保留在正式A路径，事件样本必须为0

## 验证结果

- Stage002单测：`17 passed in 6.23s`
- V2全量测试：`29 passed in 25.95s`
- `stage001_import_preflight.py`、`stage002_event_feature_qualification.py`、`formal_signal_event_features.py`：`py_compile`通过
- 源码安全扫描：Stage002只有一个`_run_live_c9`调用点；没有XGBoost/sklearn、fit、predict、标签、CTP、账户或订单调用点
- 生产数据库：单一`database.db`，没有WAL/SHM旁挂文件；生产仓保持detached HEAD且clean

## 回测结果字段

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；未回测
- 胜率：不适用；未回测

## 过拟合与继续价值

- 当前是否过拟合：否。事件内容、未来价格和绩效尚不可见，经济对象、特征、阈值、区间和容差均已预先固定。
- 当前是否值得继续：是。下一步只需冻结当前精确输入合同并执行唯一资格运行，即可判断正式根事件是否具备进入标签合同阶段的最低信息量。
- 停止条件：输入冻结不一致、任一worker失败、A1/A2不一致或任一资格门失败，均立即闭线，不修改阈值、不缩短区间、不重跑。

## TODO

1. 计算最终1416项输入manifest，写入Stage002A冻结凭证和中文冻结记录。
2. 再跑全量测试并验证生产仓clean、claim/成功/失败目录均不存在。
3. 执行唯一Stage002；仅在通过时进入Stage003标签合同预注册，不直接训练或回测。
