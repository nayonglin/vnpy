# Stage002 正式根事件与特征资格预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 当前模式：正式LR选品 + C9根入场事件XGBoost二级过滤的无标签资格研究
- 记录时间：2026-09-05 17:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：一次性正式基准根事件与12项决策时点特征资格
- 是否重要突破：否；执行前无模型和收益证据
- 是否触发A/B：否；只运行正式A路径基准以提取事件，不运行候选策略或A/C对照
- 是否触发reviewer：否；无标签资格不是有价值策略版本

## 上游资格

- V2 Stage001纯导入预检已通过，两个冷worker在零子进程、零网络、零生产写与零正式回放下完成生产上下文导入。
- 正式身份固定为`m0005_20260901T165450+0800_1961d98ccb2b`、`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`和15万元。
- V1 Stage001唯一执行已失败闭线，不复用其authorization、claim、event、失败产物或执行机会。

## 固定经济对象

- 逻辑回归继续决定月度模型排名池，C9继续决定方向与根入场。
- 样本只接受模型排名层、`flat_entry`、`candidate_status=opened`且`is_opened=1`的正式根事件。
- 固定发布卫星`fu.SHFE`保持正式A路径，但不属于LR模型行，不进入事件样本或未来skip动作。
- 冷启动回放区间固定为`2020-01-02`至`2026-08-28`；样本只从冻结动态LR资格日进入。

## 固定12项特征

1. `formal_rank_percentile`
2. `formal_score_margin_to_cutoff`
3. `directional_rsi`
4. `directional_ma_gap`
5. `directional_ma_slope`
6. `open_interest_change_pct`
7. `stop_distance_pct`
8. `portfolio_drawdown_pct`
9. `margin_to_equity_before`
10. `active_positions_fraction`
11. `same_direction_correlation`
12. `loss_streak`

特征定义逐bytes复制V1已冻结工具，SHA256为`e131e0a4e689fdb47769cf0d4aae01a82d793f3033b9b14c839cdbc688163d5a`。禁止根据Stage002结果增删、变换特征或修改阈值。

## 固定资格门

- 事件总数不少于150。
- 2023、2024、2025每年不少于24个事件。
- long与short各不少于40个事件。
- 覆盖不少于15个品种。
- event identity唯一，全部为正式根开仓语义，`fu.SHFE`事件数为0。
- 12项特征全部有限且各至少2个唯一值，其中至少8项有不少于10个唯一值。
- A1/A2事件表字段、排序、离散值和数值在绝对误差`1e-12`内一致。
- 同向相关性独立重算trace必须与正式快照一致；unknown不得当成0。
- 输出列不得包含future、label、realized、gross_pnl、net_pnl、MFE、MAE或exit字段。

## 执行与安全合同

- 父进程先生成全量输入manifest，覆盖正式release、生产回放Python树、workspace vn.py核心、`vnpy_portfoliostrategy`、数据库、分钟源、映射、元数据、品种池、V2工具/测试/预注册及Stage001通过证据。
- 最终输入数量、逻辑key SHA、file contract SHA与runtime SHA在实现和测试稳定后，于唯一运行前另写Stage002A记录冻结；没有精确冻结值不得执行。
- 固定claim文件以`O_CREAT|O_EXCL`创建；claim一旦存在即视为执行机会已消费，无论成功、失败或中断都禁止同线重跑。
- A1/A2均由`.py311/bin/python -I -S -B`和macOS sandbox冷启动，使用独立runtime、数据库副本、HOME、TMP、MPLCONFIGDIR与空setting。
- 每个worker的安全守卫只允许`_run_live_c9`恰好1次；第二次立即阻断。子进程、网络、生产写、标签、holdout、XGBoost/sklearn、fit、predict、候选策略、CTP、账户和订单仍全部禁止。
- 生产导入继续使用V2 Stage001已通过的portable字体缓存和release attestation适配，不修改生产代码，不放行`fc-list`、`system_profiler`或`git`。
- worker只暂存`entry_candidates`，立即释放组合曲线、交易、持仓与live spec对象；仅构建事件特征CSV和receipt。
- 父进程只在输入前后身份一致、A1/A2一致且全部资格门通过时发布成功目录；否则发布失败记录并闭线。

## 结果发布边界

- 允许：事件ID、正式身份、决策时间、品种/合约、方向、正式分数/rank/top_n、相关性trace和12项特征，以及聚合覆盖统计。
- 禁止：任何未来价格、事件最终盈亏、组合收益曲线、最大回撤、MFE、MAE、退出原因、标签、模型、预测、候选策略结果。

## 回测结果字段

- 期末权益：不发布；本阶段不评价绩效。
- 总收益：不发布；本阶段不评价绩效。
- 最大回撤：不发布；本阶段不评价绩效。
- Sharpe：不发布；本阶段不评价绩效。
- 总滑点：不发布；本阶段不评价绩效。
- 总交易次数：不发布；只允许报告根事件样本数。
- 胜率：不发布；本阶段没有结果标签。

## 决策纪律

- 通过只允许进入Stage003“单事件反事实标签生成合同”的预注册与实现，不直接解锁标签读取、训练或回测。
- 失败即关闭本线，不降门、不删年份/品种/方向、不补值、不缩短区间、不重跑。
- 不对Stage002启动reviewer；只有未来真实回测同时改善收益和最大回撤、并通过基础稳健性门形成候选版本时才启动。

## 过拟合与继续价值

- 运行前是否过拟合：否；对象、特征与资格阈值均在事件结果不可见时冻结。
- 当前是否值得继续：是；这是判断正式根事件样本是否足以支持后续双目标树模型的必要门。
- 主要风险：历史正式根事件可能仍不足150，或账户/相关性特征不可复现；任何失败都属于机制资格反证，不允许参数救援。

## 合入建议

- 是否更新本线`LINE.md`：实现稳定并冻结精确输入合同后更新。
- 是否更新`research/registry.md`：否，由统一合入者维护。
- 是否追加根目录`memory.md/back_log.md`：否；尚无模型或回测突破。
