# Stage000 方向一致延续效用无标签预注册

- line_id：`futures_trend_xgboost_pit_directional_continuation_utility`
- 记录时间：2026-09-05 05:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：首次读取本线方向代理分布前的唯一合同冻结；不是标签实验、模型实验、回测或上线。
- 是否重要突破：否，当前只是可证伪的数据与语义资格合同。
- 是否触发A/B：否；逻辑回归主体、正式AI池、C9/15w、CTP和生产均不修改。

## 外部调研与判断

- XGBoost官方LTR文档（https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html）：排序学习需要明确qid和事前定义的相关性标签；模型不会替代经济标签设计。
- Moskowitz、Ooi、Pedersen的`Time Series Momentum`（https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463）：期货趋势收益具有时间序列方向性，标签不能只奖励未来上涨。
- Barndorff-Nielsen等的realized semivariance研究（https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3584014）：上行和下行变动的信息含义不同，支持把方向一致收益与不利路径风险分开度量。
- Goyal与Jegadeesh的`Return Signal Momentum`（https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2971444）：时间序列和横截面动量并非同一收益来源，不能用横截面排名替代事前方向。
- 我的判断：上一条标签线失败的根因是用未来路径自身符号定义“正确方向”。本线只允许用query date已经可见的正式策略延续条件确定方向，再让未来路径回答该方向是否有净效用。当前先审计方向代理与成本元数据，不允许借机调XGBoost。

## 正式策略身份冻结

- 当前线上版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 最终策略类MRO：`Stage847C9StopRetry -> Stage830C2Broker10MarginCap -> Stage827C2 -> Stage804LongTighterInitialStop -> Stage772ExactAm -> QmtRollPortfolioStrategy`。
- 最终引擎`new_bars`实际所有者为`ConfirmedDailyNextRealOpenEngine`；其传给策略的`bars`只含当日真实bar，缺失日只更新引擎估值bar而不更新策略AM。因此精确AM41定义为最近41根真实观测日线，不做平填。
- 最终合并方向相关设置冻结为：MA `5/10/20/40`、`long_entry_enabled=true`、`short_entry_enabled=true`、`rollover_reopen_enabled=true`、`reverse_on_opposite_signal=false`、精确AM `41`、MA5 extreme开启且比较`3`日、角度反转过滤关闭、short MA5 slope过滤开启、wick过滤开启且`10`日最多`5`日、RSI入场过滤关闭、Donchian周期`20`。
- 代码SHA256：
  - `qmt_roll_portfolio_strategy.py`：`98008f3c5e821cc9d9a522cd20864ad004a1dbd910fb4989509ac3e22adbcaec`
  - `analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py`：`b2fab80fcbb15766350408a2cfe1cb1b810b6f2ae2f28d4ce6e839dda4df6bfd`
  - `analyze_qmt_roll_stage772_am40_80_120_oi_monthly.py`：`5fbfe1cd84909b0c71df7a5b8f2042b9870e188709f43781bdb3a72fd806c6f5`
  - `analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly.py`：`ae33da36e944a50c9d8fdd48f7149555b30f1168c2d3b557cfd268b4f9535e57`
  - `analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py`：`9a63510355854349385c2309654101eb99432ddddf81c13636bc3dbbbde136f0`
  - `analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py`：`0adf455e167b8dbfde51a4687098dba91a6788b13b7a1a81020c260d0af32647`
  - `analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine.py`：`c9d37be2560278b20eb358a4767f05a25d579f856b9940eac1feee6a0b5a4d7d`
  - `analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py`：`47b460d6744edc43da53e867acc791a19d81f173e04c830b221f5f68bd18765c`
  - `analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`：`9947d72f921cd6063a5acd524106d8e2eb06adb991435ef20b1728ed47dc09d0`
  - `run_qmt_roll_backtest.py`：`38a016d6da5fe3b9d93868745b5e4f64ea12f499033bd301aba60cc09c6ee5fd`
- 配置SHA256：Stage777 `b7934ab7a54b033bb1b9a979f55c056571dad4c96aa95f229e51e6f6c93ae7e7`、Stage813 `25c1e9cdf3ee79c49c7772ffdac58317e83afabced36c145780d7cf0bdb5854d`、Stage819 `ef3e10f57eca5fd8e7f1d5dc9e01d8b392d2799c16c4f4d17f1b530e90ab36bd`、Stage847候选 `588e97e899f2291617fd935e474133a974da4088972e50a634ad0281e6edf83c`、live `0f4d0b524629f828915d2ee237faa9eacb176e29efc0b926efecd207199a14fc`。

## 冻结输入与样本身份

- 全市场特征面板：`model_feature_panel.csv.gz`，SHA256 `1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac`。
- 正式月度动作计划：`formal_scoring_plan.csv`，SHA256 `ed83264188655939cb1289d75f480174be3bdcc50e7ed2a9daf0731a48a73ed2`。
- 特征产物manifest：SHA256 `0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a`。
- 全市场原始源manifest/summary：SHA256 `e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a` / `67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939`；manifest唯一绑定`4,477`个实际合约原始文件。
- 不变量产品元数据：`invariant_product_metadata.csv`，SHA256 `23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174`。
- 仅用于冻结未来标签可用日期身份的expiry-safe paths/legs：SHA256 `a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e` / `db2fcffc24053cbb5c540a699bc47f19149d54eeb66aa2b57057707f346a92da`；Stage001不得读取legs的价格端点或未来bar。
- 基础面板必须精确为`57,528`行、`1,067`个qid、`64`个产品。唯一规则排除固定卫星`fu.SHFE`的`1,067`行后，模型排名层固定为`56,461`行、`1,067`个qid、`63`个产品，qid宽度最小/中位/最大`48/52/60`。
- development日期固定为expiry-safe paths已有的`1,046`个qid；排除`fu.SHFE`后必须与面板一对一形成`55,226`行、`62`个产品。剩余`21`个qid、`1,235`行只做inference-only方向覆盖；`ad.SHFE`仅存在于该区间，不得回填历史。
- 正式动作日期精确为`48`个，其中`47`个属于development，`2026-06-30`这`1`个属于inference-only；不得把48个动作日期写成48个可生成开发标签的月份。

## 方向代理冻结

- 名称固定为`counterfactual_rollover_continuation_direction_proxy`。它只回答“若query date已有该方向持仓，正式市场条件是否允许换月延续”，不是实际持仓、实际开仓信号、实际换月动作或成交。
- `proxy_observable=true`必须同时满足：query主力合约唯一命中manifest源文件；query date有真实bar；截至query date最后41根真实观测日线完整；这41根OHLC均正、有限且满足`high>=max(open,close)>=min(open,close)>=low`。
- 原始文件必须按合约、按query date递增流式推进：先只切分首列`trade_date`，只有该行日期不晚于当前尚未评估的query date时才允许访问其余OHLC字段并转成数值；每个query必须在任何更晚日期OHLC字段暴露前完成评估。完整文件SHA可按字节读取，但哈希过程不得解析字段值。`future_ohlc_field_access_count`、`future_ohlc_numeric_parse_count`与`post_query_bar_usage_count`必须同时为`0`。
- 不足41根或query date无真实bar属于事前可见的`proxy_unobservable`，必须保留原因和空方向，不得写成中性`0`。
- 在精确41根history上复刻正式`_rollover_reopen_allowed`：
  - `long_allowed = long_enabled AND MA5>MA10>MA20>MA40 AND MACD_hist>0 AND long_entry_filters_pass`
  - `short_allowed = short_enabled AND MA5<MA10<MA20<MA40 AND MACD_hist<0 AND short_entry_filters_pass`
  - 入场过滤逐项复刻正式MA5 extreme、short MA5 slope和wick规则；角度过滤与RSI入场过滤按最终设置关闭。
  - 仅long为真记`+1`，仅short为真记`-1`，两者都假记`0`；两者同时为真是技术失败。
- oracle固定为通过`object.__new__`构造的最终`QmtRollPortfolioStrategyStage847C9StopRetry`实例，并注入已核验的最终方向相关设置；使用同一41根真实bar独立构造正式`ArrayManager(41)`，先调用其继承的`_generate_signal`取得正式MA对齐状态，再调用`_rollover_reopen_allowed`。oracle不得读取或复用手工公式的MA对齐布尔值；独立手工公式与该最终C9实例oracle逐行比对，`formula_mismatch_count`必须为`0`。

## 成本元数据冻结

- Stage001只建立未来标签可用的成本元数据，不计算未来收益或费用。
- `qmt_universe.py` SHA256 `8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f`；`main_contract_mapping.py` SHA256 `86f4baa027e1a236616d749895e349840a3db305b7ca87a7401ff4afc47bc503`。
- 模型排名层63个产品中，`17`个必须标记为`formal_explicit_legacy_universe`并使用当前代码显式`rate/slippage/size/pricetick`；其余`46`个必须标记为`research_metadata_fallback`，按`_product_defaults`使用元数据size/tick、零rate、一个price tick的slippage fallback。
- 所有产品size、pricetick、slippage必须正且有限，rate必须有限；来源类型不得为空。该口径只能称`research_code_defined_cost_proxy`，不能称真实历史手续费、真实成交成本或生产成本。

## Stage001硬门

1. 全部冻结输入、完整策略/引擎继承链代码、配置、预注册、计划、核心、runner和测试都必须记录运行前后`path/SHA256/size/mtime_ns`且完全稳定；所有实际使用的原始合约文件必须与source manifest的size/SHA一致，最终bundle可离线复验。
2. 样本身份、固定fu排除、development/inference-only切分与上述精确计数完全一致；重复键、额外删除或回填ad历史均为0。
3. 正式设置快照和MRO/new_bars所有者逐值一致；AM只取真实观测bar，平填bar使用数为0。
4. 所有query主力合约都能唯一解析到source manifest；used OHLC非法、重复日期、源SHA不符、future OHLC字段访问/数值解析、post-query使用、方向双真与公式不一致均为0。
5. 每个development qid至少有`10`个`proxy_observable`产品，不得删除不达标qid；正式动作日期身份必须精确为`47 development + 1 inference-only`，全部`48`日各至少有`10`个可观测产品和`1`个非零方向产品。
6. 至少`252`个development qid存在一个非零方向产品；2022、2023、2024、2025、2026每年long和short非零计数都必须大于0。该门只防代理退化，不要求每个qid凑足10个方向产品。
7. 成本来源计数精确为`17/46`，63个产品均完整；正式显式和研究fallback必须分栏披露，禁止用“真实成本”措辞。
8. 未来close/return/label读取、标签生成、逻辑回归或XGBoost fit/predict、策略回测、true engine、sealed holdout、CTP、订单API和生产写入计数均为`0`。

## 唯一执行与防重放

- authorization JSON必须绑定预注册、计划、核心、runner和两份测试的SHA，包含唯一nonce且`allowed_run_count=1`。
- 对外正式`run_qualification`只接受已消费的执行租约与授权回执，不接受调用方覆盖输入、配置或输出路径；合成测试只能调用受`fixture_root`路径约束且关闭正式runtime身份检查的独立fixture入口。
- runner校验授权绑定后、读取面板或任何方向代理分布前，必须以`O_CREAT|O_EXCL`原子独占创建固定路径`artifacts/stage001_execution_event.json`，文件权限为`0600`，写入后同步文件和父目录；事件绑定nonce、授权摘要和唯一lease id并记录`status=started`。正式计算入口还必须以同样的排他耐久写入创建固定`stage001_execution_claim.json`，保证相同lease顺序或并发调用都只有一次能进入核心。
- 授权回执中的六项绑定SHA必须以`authorization_*`键并入`input_identity_contract`的expected SHA，防止授权校验后、首次before快照前发生漂移而误通过。
- 固定execution event、execution claim或最终输出目录任一已存在时，后续`--run`必须立即拒绝；异常也保留并更新event，不允许换nonce覆盖或删除后重跑。
- 最终bundle保存authorization receipt；完成后只允许`--verify-only`，不得再次计算代理分布。

## 决策

- 全门通过：`stage001_direction_proxy_qualification_pass_allow_label_preregistration_only`。
- 任一门失败：`stage001_direction_proxy_qualification_fail_close_no_future_labels`。
- 失败后禁止改AM41、方向公式、固定fu排除、10产品/252qid/双向年度门、删日期/品种、把不可观测补0或读取未来收益救援；新机制必须另立研究线。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：不适用；Stage001不运行回测。

## 过拟合反思

- 运行前判断：否，但后续风险高。
- 原因：方向完全来自已冻结线上策略与query-date数据，门禁在首次统计方向分布前固定，没有按未来收益选择方向或阈值；但该假设来自多条失败路线之后，后续标签和模型仍必须单次OOS并接受证伪。

## 继续价值反思

- 运行前判断：是。
- 原因：它直接修复“未来方向定义未来标签”的内生错误，同时保留逻辑回归主体；若无标签门都过不了，会以低成本终止而不是消耗一次模型实验。
