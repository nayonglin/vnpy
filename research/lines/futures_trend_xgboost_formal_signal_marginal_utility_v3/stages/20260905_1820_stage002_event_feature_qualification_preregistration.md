# Stage002 正式根事件与特征资格预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v3`
- 当前模式：正式LR选品 + C9根入场事件XGBoost二级过滤的无标签资格研究
- 记录时间：2026-09-05 18:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：一次性正式基准根事件与12项决策时点特征资格
- 是否重要突破：否；执行前无模型和收益证据
- 是否触发A/B：否；只运行正式A路径基准以提取事件，不运行B或C候选
- 是否触发reviewer：否；无标签资格不是有价值策略版本

## 上游资格与独立性

- V3 Stage001 metadata-only双冷worker预检已通过：801个合约、19个品种，两个派生CSV逐bytes一致，正式回放、网络和全部敏感计数为0。
- V2 Stage002的claim已消费且永久禁止重跑；其失败发生在`_metadata()`，未调用`_run_live_c9`，未看到事件或绩效。
- 本阶段是新的V3合同和新的唯一执行机会，不复用或修改V2 claim、冻结文件、失败证据和产物。
- 正式身份固定为`m0005_20260901T165450+0800_1961d98ccb2b`、`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`和15万元。

## 候选假设与A/B边界

- 一句话假设：正式LR月度排名与C9根入场产生的决策时点上下文，可能包含树模型可利用但线性边际分数无法表达的非线性交互，从而在未来作为二级过滤改善收益与回撤。
- A：当前正式LR选品 + C9基准，仅用于生成根事件。
- B：本阶段不存在；不训练XGBoost独立策略。
- C：本阶段不存在；不改变正式基准动作。
- 本阶段只判断样本与特征是否具备进入标签设计的资格，不作推广结论。

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

- 特征工具继续逐bytes复用V2从未成功产出事件的冻结实现，SHA256为`e131e0a4e689fdb47769cf0d4aae01a82d793f3033b9b14c839cdbc688163d5a`。
- 禁止根据Stage002结果增删、变换特征或修改阈值。

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

- 父进程先生成全量输入manifest；实现和测试稳定后另写精确Stage002A输入冻结文件，没有精确冻结值不得执行。
- claim文件以`O_CREAT|O_EXCL`创建；claim一旦存在即视为执行机会已消费，无论成功、失败或中断都禁止同线重跑。
- A1/A2均由`.py311/bin/python -I -S -B`和macOS sandbox冷启动，使用独立runtime、数据库副本、HOME、TMP、MPLCONFIGDIR与空setting。
- 每个worker先复用V3 Stage001已通过的两个metadata路径重定向并逐bytes核验，再允许`_run_live_c9`恰好1次；第二次立即阻断。
- 子进程、网络、生产/workspace写、标签、holdout、XGBoost/sklearn、fit、predict、候选策略、CTP、账户和订单全部禁止。
- worker只暂存`entry_candidates`，立即释放组合曲线、交易、持仓与live spec对象；仅发布无标签事件特征CSV和安全receipt。
- 父进程只在输入前后身份一致、A1/A2一致且全部资格门通过时发布成功目录；否则发布失败记录并闭线。

## 在线调研与判断

- XGBoost官方Python API说明`DMatrix`承载特征数据、可显式绑定feature names与missing语义；本阶段先确保特征矩阵完整且非退化，不创建DMatrix、不导入XGBoost：https://xgboost.readthedocs.io/en/stable/python/python_api.html
- XGBoost官方模型说明其属于监督学习，训练数据需要特征与目标；因此标签必须在后续独立预注册，不能在本阶段偷看：https://github.com/dmlc/xgboost/blob/master/doc/tutorials/model.rst
- scikit-learn官方`TimeSeriesSplit`说明普通交叉验证会造成“未来训练、过去评估”的不合适顺序；后续若进入训练，必须使用按时间向前且带gap的验证：https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- 判断：当前值得继续，因为Stage001已消除V2唯一阻塞且没有观察事件；过拟合风险仍低，但Stage002门槛禁止结果后调参。

## 回测结果字段

- 期末权益：不发布；本阶段不评价绩效
- 总收益：不发布；本阶段不评价绩效
- 最大回撤：不发布；本阶段不评价绩效
- Sharpe：不发布；本阶段不评价绩效
- 总滑点：不发布；本阶段不评价绩效
- 总交易次数：不发布；只允许报告根事件样本数
- 胜率：不发布；本阶段没有结果标签

## 停止条件

- 资格通过：只允许进入Stage003单事件反事实标签合同的预注册，不直接训练或回测XGBoost。
- 任一门失败：V3事件研究闭线，不降门、不删年份/品种/方向、不补值、不缩短区间、不重跑。
- reviewer继续保持关闭；只有未来真实候选同时改善收益和最大回撤并通过预注册稳健性门后才启动。
