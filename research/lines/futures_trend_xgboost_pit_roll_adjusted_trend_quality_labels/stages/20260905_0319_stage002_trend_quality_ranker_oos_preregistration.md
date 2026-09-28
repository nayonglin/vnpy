# Stage002 趋势质量 XGBRanker 样本外预注册

- line_id：`futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels`
- stage：`stage002_trend_quality_ranker_oos`
- 预注册时间：`2026-09-05 03:19 CST`
- 工作类型：日级模型研究，A/C 单槽替换；不是策略撮合回测。
- 目标：判断固定 XGBoost 排序器能否在不改变正式逻辑回归 Top9 和固定 `fu` 的前提下，为正式第 10 名提供稳定、可审计的替换信号。

## 开始前反思

- 是否正在过拟合：**风险存在但当前受控**。Stage001 标签总体分布已经可见，因此本阶段不得再根据结果改变标签、特征、模型参数、选择规则或效果门槛；只允许修复不改变研究语义的实现缺陷。
- 是否还有价值继续：**是**。当前只有无跨合约跳价的路径标签，还没有证明 XGBoost 有样本外排序能力；固定一次开发样本外实验是进入真实撮合回测前成本最低、信息增益最高的闸门。

## 外部调研与判断

- XGBoost 官方 Learning to Rank 文档确认 `rank:ndcg` 使用 LambdaMART，qid 必须按 query 分组且排序；本阶段因此把日级截面作为 qid，并强制连续排序：https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html
- CME 连续价格序列材料说明换月拼接会引入合约切换处理问题；本线继续使用同一实际合约 leg 收益，禁止旧合约与新合约价格直接相除：https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html
- AQR 的长期趋势跟随研究支持跨市场趋势机会具有长期研究价值，但不构成本模型有效证据；是否保留只看本阶段的严格样本外结果：https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf
- 判断：可借鉴 LTR 的 qid 与排序目标，但不能把文献结论当作本地收益证明，也不能通过调参救援首次失败。

## 冻结输入

1. Stage001 `path_labels.csv.gz`：方向中性的连续趋势质量、幅度、路径回撤代理及五级 relevance。
2. expiry-safe `expiry_safe_paths.csv.gz`：仅补充每个 qid 的 `label_end` 成熟时间。
3. V1 `model_feature_panel.csv.gz`：沿用 19 个已冻结 PIT 模型特征。
4. V1 `formal_scoring_plan.csv`：每月一个正式逻辑回归第 10 名及池外 challenger；不得读取正式分值。
5. V1 `fold_plan.csv`：37 个月度 walk-forward 测试点；36 个效果月，`2026-06-30` 仅推理。
6. Stage001、expiry-safe、V1/V2 合约的冻结 manifest/summary，以及本阶段代码、测试和本预注册文件的 SHA256。

运行前必须重新验证全部输入身份，运行后再次核对 size、mtime_ns 和 SHA256。输出只能写入本研究线。

Stage001 原始标签含固定 sleeve `fu.SHFE`。Stage002 在任何训练、预测或指标计算前确定性排除其 1,046 行，并仅根据剩余 AI universe 的连续 `future_trend_capture_quality` 重新计算五级 relevance；预期为 55,226 行、1,046 个 qid。该修正来自首次拟合前独立评审，不使用任何 Stage002 模型结果。

## 冻结特征与模型

- 特征严格等于既有 `MODEL_FEATURES`：17 个截面 rank 加 2 个缺失标记，共 19 个。
- 禁止特征：产品代码、合约代码、日期、月份、年份、正式排名/正式分值、未来方向、未来收益、未来回撤、标签或其变形。
- 工厂严格为 `xgboost.XGBRanker`。
- 参数严格沿用既有 V2 固定参数：`rank:ndcg`、`ndcg@10`、64 棵树、深度 2、学习率 0.03、`min_child_weight=5`、`reg_lambda=10`、`hist`、固定 seed 42、单线程及既有 LambdaMART 参数。
- 不做参数搜索、特征筛选、早停搜索、阈值搜索、模型融合权重搜索。
- 每个 fold 独立拟合两次；模型字节必须一致，预测最大绝对差必须不高于 `1e-12`，且至少一个 split、至少两个不同预测值。
- 授权除本线实现外，必须绑定实际解析到的 V1 特征合同、V2 固定模型实现、XGBoost sklearn 源码和原生库 SHA256。

## Walk-forward 与泄漏约束

- 按 `test_eval_date` 升序执行 37 个 fold，共 74 次 fit。
- 训练集只允许 `label_end < test_eval_date` 的完整 qid；不允许拆分 qid。
- 训练行按 `query_date, product_vt_symbol` 稳定排序，qid 必须连续非降序。
- 每个 fold 先完成训练、排除固定 `fu` 后的 AI 全截面预测、A/C 选择，并把模型、预测和选择 SHA256 以独占创建方式落盘 seal；之后才能逻辑开放该测试月标签。
- `2026-06-30` 没有成熟标签，只允许生成推理选择，禁止进入效果统计。
- 本阶段使用的是开发样本外，不是未见 sealed holdout；完整标签文件会在 runner 内存中加载，`seal 前 0 行`仅表示受审计 API 的逻辑开放为 0，不是物理不可访问。不得据此宣称正式收益、账户回撤或可上线。

## 冻结 A/C 结构

- A：当前正式逻辑回归 Top10，固定 `fu` 保持不变。
- C：正式 Top9 与固定 `fu` 保持不变，最多只处理第 10 个槽位。
- XGBoost 在排除固定 `fu.SHFE` 后的完整 AI 测试 qid 上排序。仅当正式第 10 名不在 XGBoost Top10，且至少一个池外 challenger 在 XGBoost Top10 时，才用 XGBoost 分数最高的该 challenger 替换正式第 10 名；并列按 `product_vt_symbol` 升序确定。
- 任何月份最多替换一个品种；不得改变正式 Top9、固定 `fu`、仓位、方向、止损或执行规则。
- B（纯 XGBoost 排名）只作诊断，不是候选执行版本。

## 冻结全截面预测门

只对 36 个效果月计算。独立评估 NDCG 使用与训练配置一致的线性 gain；对相同预测分数的 tie group 取组内随机排列的精确期望，不等同于 XGBoost 内置指标的 tie 处理：

1. 36 个月的 mean Rank IC `> 0`。
2. median Rank IC `> 0`。
3. Rank IC 为正的月份不少于 22 个。
4. 去掉 Rank IC 最佳月份后，其余月份 Rank IC 总和仍 `> 0`。
5. 4 个自然年中，月均 Rank IC 为正的年份不少于 3 个。
6. 每月 NDCG@10 与同一 relevance 分布下的精确随机排序期望比较：平均差值 `> 0`，且优于随机期望的月份不少于 22 个。

Rank IC 或 NDCG 门任一失败，立即停止，不允许进入真实撮合回测预注册。

## 冻结 A/C 路径代理效果门

只对 36 个效果月计算。未替换月的 C-A 必须严格为 0。所有门必须同时通过：

1. 替换月数在 `[8, 32]`。
2. 替换月中 `future_trend_capture_quality` 改善比例 `> 50%`，中位数差值 `> 0`。
3. 36 个月质量差值总和 `> 0`，去掉最佳月份后仍 `> 0`。
4. 4 个自然年中，质量差值总和为正的年份不少于 3 个。
5. `future_abs_log_return` 差值总和 `> 0`，去掉该分量最佳月份后仍 `> 0`。
6. `future_oriented_max_drawdown` 差值总和 `> 0`，去掉该分量最佳月份后仍 `> 0`；数值更大表示回撤更浅。

这些只是单品种未来路径代理，不是策略收益和账户最大回撤。即使全部通过，也只允许预注册 A/C 真实撮合回测。

## 技术门与副作用门

- 输入、实现、所有实际复用代码、运行时、固定参数与一次性 nonce 授权绑定；开始事件必须在任何 fit 前 durable 落盘，文件和父目录均 `fsync`，nonce 不得复用。
- 37 个 fold、74 次 fit、37 个 seal、36 个效果月和 1 个推理月必须精确成立。
- 测试月标签在对应 seal 前的逻辑开放行数必须为 0。
- 37 个 seal（含推理月）必须生成后立即复核，并在汇总前结合落盘模型、预测和选择逐月重放复核；任何不一致 fail-close。
- 策略回测次数、sealed holdout 读取、CTP 连接、订单 API、生产写入全部必须为 0。
- 运行失败也必须原子发布保留进度和错误的失败证据包，不得把部分结果解释为效果结论。

## 决策

- 技术门、预测门、A/C 路径代理门全部通过：`stage002_trend_quality_ranker_oos_pass_allow_true_engine_ac_preregistration_only`。
- 技术门失败：`stage002_trend_quality_ranker_contract_or_pit_invalid_stop_no_effect_claim`。
- 技术门通过但任一效果门失败：`stage002_trend_quality_ranker_oos_fail_stop_no_true_engine`。

本预注册之后，首次真实 fit 前不得修改上述研究语义。
