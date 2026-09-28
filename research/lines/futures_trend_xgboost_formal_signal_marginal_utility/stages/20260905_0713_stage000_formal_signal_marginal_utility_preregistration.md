# Stage000 正式信号账户边际效用预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：`day`
- 记录时间：2026-09-05 07:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线启动、标签前经济对象与研究边界冻结
- 是否重要突破：否；当前只有新的可证伪假设，没有XGBoost收益证据
- 是否触发A/B：有潜在价值但尚不触发；Stage000/001只做正式A事件与特征资格，不运行候选B/C

## 外部调研与判断

- XGBoost官方文档确认，XGBoost是监督学习模型；排序任务必须有按`qid`分组的样本与相关性标签。模型本身不会自动创造经济目标，先定义正确标签比换树参数更重要。
- Joubert《Meta-Labeling: Theory and Framework》将meta-labeling定义为叠加在主策略之上的过滤/仓位层，可用于减少假阳性并改善Sharpe和最大回撤；它不取代主策略方向。
- mlfinlab公开实现和相关讨论强调，`side`应来自主模型；若事件筛选本身依赖未来结果，meta-label仍会泄漏。
- 我的判断：逻辑回归继续选品、C9继续产生方向，XGBoost只判断正式根入场是否应接受，结构上成立；但旧信号质量线已反证静态桶，因此必须改用连续决策时点特征和账户级单事件反事实标签。历史已被反复研究，任何历史效果只能算开发证据，真正晋级必须依赖2026-09-05之后的新增前向样本。

## 已否决方案

- 否决继续调月度XGBRanker、融合权重、树深、学习率、TopN或年份：旧主线已失败，属于结果后救参。
- 否决把最终交易盈利、固定20日MFE/MAE继续作为唯一标签：与Stage234-236重复，且不能表达资本占用和被挤出的机会。
- 否决让XGBoost独立猜多空：这会绕过正式C9方向，重复月度方向代理失败。

## 冻结经济对象

- 样本单位：单一起点正式基准中`entry_context=flat_entry`、`is_opened=1`且属于逻辑回归模型排名层的根入场事件。
- 固定`fu.SHFE`是发布卫星，不是逻辑回归模型行；其正式路径保持A，禁止进入样本、训练或未来skip动作。该排除在读取任何标签前按生产语义冻结。
- 事件身份：正式材料release、执行版本、回放起止日、`candidate_index`、决策日期、产品、实际合约、方向、signal共同构成；任一字段变化视为不同事件。
- A路径：当前正式逻辑回归AI池 + C9/15万完整路径。
- S路径：与A完全相同，只在目标根事件决策点把该事件置为skip；之后策略自由演化，包含释放仓位后出现的真实机会成本。
- 标签终点：A路径中该根事件及其0.5R重试家族最终回到该产品空仓的交易日；若无法唯一闭合则该事件标签资格失败，不得用固定收益补齐。
- 收益边际：`(A_end_equity - S_end_equity) / A_pre_event_equity`。
- 回撤边际：同一事件区间内`A_max_drawdown - S_max_drawdown`；值越大表示接受事件后的最大回撤更浅。
- 未来C臂：仅当两个固定回归头都预测边际严格小于0时跳过根事件，否则与A一致；阈值固定为0。

## 固定特征与变换

- `formal_rank_percentile = 1 - (rank - 1) / max(model_ranked_top_n - 1, 1)`；这里的`model_ranked_top_n`只统计逻辑回归排名行，固定`fu`不进入分母。
- `formal_score_margin_to_cutoff = event_score - 当月正式模型排名层最后一名score`；固定`fu`只作为发布卫星，不作为模型cutoff。
- `directional_rsi = sign * (rsi - 50) / 50`，long的`sign=+1`，short的`sign=-1`。
- `directional_ma_gap = sign * (ma_mid - ma_long) / planned_entry_price`。
- `directional_ma_slope = sign * (((ma_mid-ma_mid_prev) + (ma_long-ma_long_prev))/2) / planned_entry_price`。
- `open_interest_change_pct = entry_oi / prev_oi - 1`；要求两者严格正值。
- `stop_distance_pct = stop_distance / planned_entry_price`。
- `portfolio_drawdown_pct`沿正式快照原值，禁止用事后曲线重算替换。
- `margin_to_equity_before = total_margin_in_use_before / estimated_equity`。
- `active_positions_fraction = active_positions_before / max_concurrent_positions`。
- `same_direction_correlation`沿正式快照；无同向持仓时正式值应为0，不允许把未知缺失填0。
- `loss_streak`沿正式快照数值。

## Stage001预声明硬门

> 2026-09-05 07:51 CST执行前修订：正式材料无标签结构检查确认`2019-12-31`是全零分数静态18边界且无固定`fu`卫星，动态LR快照从`2022-01-28`才开始。依据同目录Stage000A记录，回放区间仍保持`2020-01-02 -> 2026-08-28`以形成真实账户状态；事件样本严格排除静态边界，覆盖门改为动态事件总数`>=150`、2022-2025各`>=24`，其余门不变。该修订发生在authorization、claim、标签、收益和正式回放之前。

1. 当前active material必须精确为`m0005_20260901T165450+0800_1961d98ccb2b`，策略为`ai_top10_plus_fu_official_live_v1`。
2. 执行版本必须精确为`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，资金必须为`150000`。
3. 回放区间固定`2020-01-02 -> 2026-08-28`，只允许一个冷启动起点。
4. A1/A2必须分别在冷进程、独立`.vntrader`、`HOME`、`TMPDIR`和`MPLCONFIGDIR`运行，使用独立空设置文件，禁止checkpoint复用；解释器、cwd、sys.path、模块路径、source contract及每个worker恰好一次正式基准回放必须硬校验。
5. A1/A2根事件身份表和12特征矩阵排序后逐值一致；数值最大绝对差必须`<=1e-12`。
6. 动态LR根事件总数必须`>=150`；2022-2025每个完整年份必须`>=24`；long和short各自必须`>=40`；产品数必须`>=15`。
7. 事件身份键不得重复，且全部为`flat_entry/opened/is_opened=1`的模型排名层事件；固定`fu.SHFE`样本数必须为0。
8. 12项特征必须全部存在、有限且无缺失；每项至少2个唯一值，至少8项必须有`>=20`个唯一值。
9. 正式AI月份、score、rank、top_n与active release逐月可追溯；必须恰有`2019-12-31`静态18边界和从`2022-01-28`至`2026-08-31`的冻结56个动态月份，每个动态月恰为10个模型行加rank11固定`fu`；固定`fu`不得误当逻辑回归模型排名层cutoff。
10. 输出列禁止包含未来收益、未来OHLC、结果标签、MFE、MAE、最终盈亏、退出原因或未来账户状态。
11. XGBoost/逻辑回归fit、predict、反事实标签、候选回测、holdout读取必须为0。
12. `sandbox-exec`必须以deny-default方式关闭当前进程、原生库和后代进程网络，并把写入限制在worker目录；CTP连接、账户读取、send/cancel/order API、子进程和越界写入必须为0。
13. 恰好1409项冻结逻辑输入必须逐项记录并核对规范化path/size/mtime/SHA；claim与event必须原子成组发布，任何中断只允许恢复为技术失败，异常路径也必须写nonce绑定的耐久事件账本。

任一硬门失败即关闭本Stage001形状；不得根据失败值删事件、降门、补值、换起止日、改特征或同线重跑。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：上述固定事件、特征、标签和门禁合同
- 修改参数：无正式策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage001计划固定`2020-01-02 -> 2026-08-28`
- 账户规模：15万元，仅正式基准事件资格
- 成本口径：Stage000/001不生成收益标签；未来S路径必须与A使用完全相同正式成本
- 样本过滤：正式基准模型排名层`flat_entry`根事件；仅按生产语义排除固定`fu`卫星，禁止按结果、其他产品、年份或方向过滤
- 策略/归因口径：active m0005逻辑回归选品 + 当前C9/15万

## 结果

- 期末权益：不适用，未运行回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：0个新回测交易
- 胜率：不适用
- 其他关键指标：标签读取0、模型训练0、预测0、CTP/订单0、生产写入0

## 输出文件

- report：本记录
- summary：无
- orders：无
- daily：无
- quality：无

## 结论

- 本阶段结论：`stage000_formal_signal_marginal_utility_preregistered_no_labels`。
- 是否进入下一步：是，只允许实现和独立预审Stage001无标签资格runner。
- 下一步：按TDD实现纯特征构造与fail-closed校验，再实现A1/A2冷进程事件重建；执行前做独立代码复核。

## 过拟合反思

- 运行前判断：是，风险高。
- 运行后判断：尚未运行；预注册本身没有新增结果拟合，但不能降低历史数据已被反复观察的事实。
- 原因：事件数预计只有约300，且既有研究已暴露多个历史阶段；因此历史开发不得作为最终晋级证据。

## 继续价值反思

- 运行前判断：有条件有价值。
- 运行后判断：仍有条件有价值。
- 原因：经济对象直接对应单事件对账户收益和回撤的边际作用，并保持LR与C9主策略不变；若事件覆盖或可复现性失败，价值立即归零。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是，注册新线
- 是否追加根目录 `memory.md/back_log.md`：否，尚无突破、候选或回测结果
