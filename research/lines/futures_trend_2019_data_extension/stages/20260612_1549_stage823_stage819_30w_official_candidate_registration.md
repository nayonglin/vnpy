# Stage823 Stage819 30w 晋升官方候选登记

## 基本信息

- 时间：2026-06-12 15:49 CST
- line_id：`futures_trend_2019_data_extension`
- 是否重要突破：是，属于官方候选登记事件；但不是实盘默认切换。
- 本次动作：按用户要求，将 Stage813 逻辑的 30 万资金口径 Stage819 登记为当前 primary official candidate。
- 新候选版本号：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 新候选配置：`examples/portfolio_backtesting/qmt_roll_official_candidate_stage819_30w_config.py`
- 修改注册表：`examples/portfolio_backtesting/qmt_roll_official_live_config.py`
- 当前实盘默认：仍为 `official_live_stage372_20w_recovery_sleeve`
- CTP/SimNow/下单：未连接 CTP，未调用下单。
- 本阶段是否新增回测：否；引用 Stage819/821/822 已完成回测结果作为登记依据和风险边界。

## 外部调研与判断

- vn.py/VeighNa 官方项目定位是用于多品种量化策略研发、回测和实盘的一体化框架，因此官方候选应以可复现配置和 manifest 固化，而不是只停留在报告结论。
- Walk-forward / rolling-window 验证的公开资料普遍强调：单一固定终点回测容易给出路径依赖的虚假稳定感，滚动窗口能更接近真实部署中不断前移的样本环境。
- 判断：本次登记不新增 alpha、不扫参数，符合低自由度候选固化；但由于 Stage822 月度 3 年滚动并不支持 30w 稳定压过 50w，30w 只能作为官方候选/观察臂，不能直接切 live default。

## 版本改动

- 新增参数/常量：
  - `OFFICIAL_CANDIDATE_STAGE819_30W_VERSION`
  - `OFFICIAL_CANDIDATE_STAGE819_30W_STATUS`
  - `OFFICIAL_CANDIDATE_STAGE819_30W_CONFIG_MODULE`
  - `OFFICIAL_CANDIDATE_PRIMARY_VERSION`
  - `OFFICIAL_CANDIDATE_PRIMARY_CONFIG_MODULE`
- 修改参数：
  - `OFFICIAL_CANDIDATE_VERSIONS` 新增 Stage819 30w 条目，并标记 `primary_official_candidate=True`。
  - `build_official_live_manifest()` 新增 `primary_official_candidate` 字段。
- 删除参数：无。
- 策略逻辑参数不变：
  - `AM41`
  - 基础风险 `0.40`
  - `OI上升 + 价格沿方向` 恢复到 `0.80`
  - 旧正式 AI 品种池
  - `maxpos4`
  - Stage804 多头更紧初始止损
  - `enable_rsi_partial_exit=True`
  - `rsi_partial_exit_threshold=95.0`
  - `rsi_partial_exit_ratio=0.5`
  - 关闭连败缩放和 recovery sleeve
- 资金口径变化：
  - `account_capital: 500000 -> 300000`
  - `c3_capital: 500000 -> 300000`

## 引用回测结果

### Stage819 年度起点 30w

- 全体年度起点 `9` 个：正收益 `8/9`。
- 相对 Stage813 50w：收益胜出 `8/9`，回撤胜出 `6/9`，Sharpe 胜出 `8/9`，收益+回撤双胜 `6/9`。
- 全体收益差中位 `+157.7107pp`，回撤差中位 `+0.3944pp`，Sharpe 差中位 `+0.1055`。
- DD40 失败 `4/9`，DD50 失败 `1/9`，broker100 失败 `0`，生存失败 `0`。
- 代表 `2018-01`：期末权益 `26,322,730`，总收益 `8674.2433%`，最大回撤 `-54.7546%`，Sharpe `1.4363`，总滑点 `2,149,150`，总交易次数 `666`，胜率 `53.1069%`。
- 代表 `2020-01`：期末权益 `18,787,535`，总收益 `6162.5117%`，最大回撤 `-44.6223%`，Sharpe `1.5941`，总滑点 `1,489,460`，总交易次数 `529`，胜率 `54.7544%`。
- 代表 `2022-01`：期末权益 `1,060,100`，总收益 `253.3667%`，最大回撤 `-37.8438%`，Sharpe `0.9661`，总滑点 `73,270`，总交易次数 `272`，胜率 `50.5282%`。
- 代表 `2026-01`：期末权益 `265,800`，总收益 `-11.4000%`，最大回撤 `-14.8955%`，Sharpe `-1.3022`，总滑点 `3,680`，总交易次数 `24`，胜率 `44.8276%`。

### Stage821 年度步进 3 年滚动

- 30w：正收益 `7/7`，中位收益 `352.8550%`，最小收益 `97.9583%`，最大收益 `1885.8950%`，中位回撤 `-32.8556%`，最差回撤 `-44.6223%`，DD30 失败 `5`，DD40 失败 `2`，DD50 失败 `0`，中位 Sharpe `1.6721`。
- 30w vs 50w：收益胜出 `4/7`，回撤胜出 `5/7`，Sharpe 胜出 `4/7`，收益+回撤双胜 `3/7`。

### Stage822 月度步进 3 年滚动

- 30w：正收益 `66/66`，中位收益 `643.7725%`，p10 收益 `75.4383%`，最小收益 `28.9200%`，最大收益 `3659.4817%`，中位回撤 `-37.6836%`，最差回撤 `-56.7501%`，DD30 失败 `52`，DD40 失败 `25`，DD50 失败 `2`，中位 Sharpe `1.6939`，p10 Sharpe `0.7328`，总滑点 `10,976,430`，总交易次数 `17,530`。
- 30w vs 50w：收益胜出 `30/66`，回撤胜出 `32/66`，Sharpe 胜出 `35/66`，收益+回撤双胜 `18/66`；中位收益差 `-6.8268pp`，中位回撤差 `-0.0398pp`，中位 Sharpe 差 `+0.0102`。
- 30w vs 20w：收益胜出 `41/66`，回撤胜出 `18/66`，Sharpe 胜出 `38/66`；中位收益差 `+30.8008pp`，中位回撤差 `-0.7646pp`，中位 Sharpe 差 `+0.0374`。

## 决策

- 决策：`stage823_stage819_30w_promoted_to_official_candidate_not_live_default`
- 当前 primary official candidate：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 当前实盘默认仍保持：`official_live_stage372_20w_recovery_sleeve`
- 原 Stage813 50w 候选仍保留在候选池作为对照：`official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- Stage777 50w 旧候选仍保留为历史对照：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`

## 反思

- 运行前过拟合反思：有一定风险。资金口径是外生部署约束，不是交易信号阈值，但把 30w 晋升候选是基于历史多窗口结果和用户偏好，容易误读为“30w 最优本金”。因此本次只登记候选，不扫 `25w/28w/32w/35w`，也不切实盘默认。
- 运行后过拟合反思：风险可控。实际改动只固化一个已测资金口径，并保留 Stage822 的负面边界；没有根据结果新增交易规则、品种过滤或阈值。
- 运行前继续价值反思：有价值。30w 解决了一部分 20w 小资金整数手颗粒度问题，又比 50w 在部分窗口有更低尾部压力，适合作为候选 shadow 观察臂。
- 运行后继续价值反思：仍有价值，但只限于候选 shadow、dry-run 和风险复核。若要改 live default，必须先做最新交易日影子盘、经纪商状态 dry-run、和当前 Stage372 20w 同窗口公平对照。

## 后续 TODO

- 跑 Stage819 30w 最新完成交易日候选 shadow，只读输出信号，不连接下单。
- 做 Stage819 30w 与当前实盘 Stage372 20w 的同窗口公平 rolling 3y/月度冷启动对照。
- 对 Stage822 中 30w 的 `2019/2020` 起点组 DD50 来源做只读归因。
- 不继续扫本金、RSI 阈值、OI 倍率、AM 根数、AI topN、训练窗或 horizon。
