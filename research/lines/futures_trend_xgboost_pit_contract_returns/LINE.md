# AI选品XGBoost PIT逐合约收益线

## 研究线身份

- `line_id`: `futures_trend_xgboost_pit_contract_returns`
- 创建时间：2026-09-02 11:46 CST
- 状态：Stage001标签前覆盖审计失败并闭线；原459行面板无法用真实PIT逐合约收益完整覆盖
- 正式基准：`ai_top10_plus_fu_official_live_v1`
- 冻结release：`m0005_20260901T165450+0800_1961d98ccb2b`
- 研究边界：只读正式完整排序、Stage014标签前基础特征和本地SQLite逐合约日线；只在本研究线写入测试、工具、记录和产物；不读取sealed holdout标签，不训练模型，不运行策略回测，不修改生产目录，不连接CTP，不调用订单API。

## 为什么另立本线

- `futures_trend_ai_xgboost_ensemble` Stage017已关闭原九特征/账户边际标签族，禁止继续调模型、参数、阈值、rank、年份或品种。
- `futures_trend_xgboost_account_context` Stage001证明正式账户`position_changes`不能覆盖未持仓候选，459行中27行零活动，不能据此构造完整候选组合上下文。
- 本线只验证一个不同的数据机制：从逐合约日线按当时可见的前一交易日持仓量选约，构造不跨合约比价的日收益。它不是对Stage017的参数救援。

## 外部调研与本地判断

- QuantConnect官方文档把连续期货拆成两个独立选择：何时/按何种规则映射合约，以及如何归一化拼接价格；`OpenInterest`是正式支持的映射方式：<https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures>。
- CME官方连续价格说明也把Active Contract定义为按历史流动性画像切换，并强调用成交量和持仓量检查真实容量：<https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html>。
- Moskowitz、Ooi、Pedersen的时间序列动量实现使用逐合约持仓量决定最活跃合约，并在换月时处理价差：<https://acfr.aut.ac.nz/__data/assets/pdf_file/0007/29806/PErdos-GElaut_Time-series-momentum.pdf>。
- 本地Stage020依赖事后导出的主力映射，并在换约日把收益强制置0；Stage122直接对拼接主力价格做`pct_change`。两者都不能作为本线的严格PIT候选收益真值。
- 我的判断：使用`T-1`持仓量选约并计算同一张合约的`close_d / close_{d-1} - 1`，能同时避免当天信息选约和跨合约价差跳点；但其是否可用必须先由上市前缺失、次日断档和120日窗口覆盖审计决定。

## Stage001冻结数据契约

### 输入

- 正式完整排序：Stage009 `formal_full_ranking.csv`。
- 标签前基础特征：Stage014 `prelabel_feature_panel.csv`，只读取51个月、rank10..18的键和split，不读取任何账户边际标签。
- 行情：`.vntrader/database.db`的`dbbardata`日线，只读打开，并记录运行前后文件SHA256。
- 正式候选全集：上述51个月正式排序中出现的18个非`fu`产品；禁止按Stage001结果删产品、删月份或删rank。

### 合约识别

- 合约必须与产品代码及交易所精确匹配，且symbol为`产品字母 + 3或4位交割月份数字`。
- 明确排除`88/8888/99/9999`等连续或指数伪代码，以及包含`C/P`等期权标记的symbol。
- 不使用当前主力映射决定历史选约；主力映射只作为本地反证材料，不进入Stage001计算输入。

### 选约与收益

- 对产品的每个交易日`d`，只使用该产品前一可用交易日`d-1`的逐合约日线。
- 候选合约要求`d-1`的close为正、open_interest为正；按`open_interest`降序、`volume`降序、`contract_vt_symbol`升序唯一选定。
- `d`日收益固定为选中合约自身的`close_d / close_{d-1} - 1`。
- 若选中合约在`d`没有有效close，记为missing；禁止查看`d`日后改选备用合约，禁止补0，禁止跨合约直接计算收益。
- 每行保留`selection_date/return_date/selected_contract/T-1 OI/T-1 volume/两日close/return/status`，以便逐行复核PIT。

### 标签前覆盖门

- 先发布全部缺失和异常明细，再决定通过或失败；不得只发布成功子集。
- 对Stage014的51个`eval_date`，使用不晚于该日的最近120个全局交易日；逐月逐品种统计有效收益数。
- 所有459个rank10..18样本必须各有120个有限收益，且对应Top9九品种也必须各有120个有限收益，才允许进入Stage002特征设计。
- `selection_date < return_date <= eval_date`违规数必须为0；跨合约比价数必须为0；事后fallback数必须为0；非有限收益数必须为0。
- `SH.CZCE/lc.GFEX/si.GFEX`等上市前无真实合约的月份必须按缺失失败，不得用当前已上市事实回填历史。
- 任一门失败，决策固定为`stage001_pit_contract_return_coverage_fail_stop_no_features`；只允许记录失败结构，不允许降120日、补值、删行、改产品/月份/rank或读取标签救援。
- 全部门通过，决策固定为`stage001_pit_contract_return_coverage_pass_ready_for_feature_design`；通过只授权另写Stage002特征设计，不授权训练、标签、回测或生产接入。

## 后续边界

- Stage001前不定义波动率归一化、Top9聚合或XGBoost输入，避免先看到覆盖结果再选择特征公式。
- Stage001通过后，Stage002仍需单独预注册风险标准化和账户上下文公式；不得直接复用账户PnL特征公式冒充市场收益组合。
- 只有产生策略回测数据才拉独立回测reviewer；Stage001只是数据覆盖审计，不触发回测reviewer。

## Stage001结果

- 读取SQLite日线`250,378`行，构造产品收益`39,646`行，其中有效`39,422`行；输入身份运行前后稳定。
- 收益构造技术门通过：PIT违规`0`、事后fallback`0`、跨合约比价`0`、`status=ok`非有限收益`0`。
- 覆盖硬门失败：候选完整窗口`445/459`，Top9完整窗口`415/459`，必需缺失单元`5,959`。
- 全部覆盖缺口只来自`SH.CZCE/lc.GFEX/si.GFEX`的上市前区间和上市首日；受影响月份为`2022-04-29`至`2024-02-29`，2024-03起才具备完整120日历史。
- 决策：`stage001_pit_contract_return_coverage_fail_stop_no_features`。不进入本线Stage002，不训练、不回测、不读holdout、不改生产。
- 禁止补0、降窗口、删月份/品种/rank、只保留完整月份或用XGBoost missing分支掩盖上市前事实。
- 若继续，只能另立“PIT上市/可交易资格先于排序”的新标签与排序机制；该机制不得视为本线参数修补。

## 过拟合与继续价值

- 运行前过拟合判断：是，研究序列风险高。已多次观察相同development月份，任何基于收益结果修改模型都属于事后救援。
- 本阶段控制：只检验数据可得性和PIT，不读取标签或收益效果，不比较模型，也不调任何效果参数。
- 继续价值：本线无。更上游的PIT上市资格重建仍有一次结构性研究价值，因为正式历史排序确实把尚未上市品种排入Top10/Top9。
