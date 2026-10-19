# Stage050：因果品种主力已完成周收盘合同

- 时间：2026-10-19 19:12 CST；宽日历资源边界更新于19:13 CST。
- line_id：`futures_trend_full_market_noai_one_lot`。
- 性质：实现与合成合同验证；不是重要突破版本，没有运行新金融回测。
- 工作树：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian`；分支：`codex/full-market-noai-one-lot`。
- 本阶段仅新增 `tools/stage050_weekly_main.py`、`tools/test_stage050_weekly_main.py` 和本唯一 stage；未改 LINE、registry、旧 tools、原金融源及旧输出、正式版本快照。

## 固定合同与实现

用户已固定多头额外要求 `周MA5 > MA10 > MA20 > MA40`，空头不加本条件；序列为品种因果主力、不复权、只用已完成周K。本模块只提供周线证据与查询接口，策略接入由 Stage051/052 完成，不在此模块新增空头逻辑。

`WeeklyMainTrend(market,mapping,calendar)` 使用独立完整交易日历确定每个自然周的最后真实会话，不由 source 的最后一条行情决定周末。周五假期时周四收盘即可完成；整周无会话不生成周bar。先从完整独立calendar求各周EOW，再仅为market/mapping联合输入日期跨度触及的自然周构造产品周网格；这既避免1900—2050等宽vendor日历制造数千无价周，也保留source周三截断所在周的真实未来周五invalid行，不先截断calendar。只有周末日映射所指定真实合约的 accepted-clean 正 close、正 volume 才有效，`observation_date` 必须严格早于该会话。未知映射、初期空主力/空 observation、缺所选合约价、非正价格/成交量、显式 execution-only 或 execution_only 列未知状态均保留 invalid 周。execution_only 列缺失仅用于调用者已经传入纯 clean 原始源的合同；有列时只接受布尔 False。quote_class 明示 execution-only 时亦拒绝。没有根据当日 OI 重选或替换成另一合约，未要求该周所有日 OHLC 齐备。

无效周 close 保留 NaN、不删除、不填充，均线在真实会话周序列上滚动；40周不足或40周窗口内存在坏周拒绝，任意相邻均线等号拒绝。坏周只有自然滚出40周窗口才解除污染。周表可单独冻结 CSV，包含产品、周末会话、所选合约、观察日、close/volume/valid、四条均线、窗口统计、allowed/reason/evidence_id。

`lookup(product,asof,phase='signal_close'|'open')` 返回可由 `json.dumps(...,allow_nan=False)` 序列化的 plain dict：收盘查询只允许 `week_last_session <= asof_date`，开盘查询严格要求 `< asof_date`。因此周五开盘不能读当天周收盘，周五收盘可以。空/未知产品、首周之前均 fail-closed。证据 ID 绑定产品和截至所选周末的最近最多40个周证据，未绑定未来文件hash，保证历史查询与未来增量隔离。

## 调研与判断

先查阅 [pandas 官方 resample 文档](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html) 与 [backtesting.py 官方仓库 resample_apply 源码](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)、[官方多周期示例](https://github.com/kernc/backtesting.py/blob/master/doc/examples/Multiple%20Time%20Frames.py)。判断：高周期指标可见时点应绑定周期结束，右侧标签本身不能证明期货交易日历完整，不能对截断日线直接 last/resample 后认定该周已完成。采用独立日历+phase查询，不复制这些项目实现、不增加依赖包。原始换月跳空会真实进入该已选定未复权序列；本阶段只验证合同实现，不评价其alpha。

## TDD 与验证证据

按 test-driven-development 和 writing-good-tests 先写合成测试。初次运行13个测试、含subtest合计18项失败，均明确为 `weekly causal gate implementation is missing`；再实现最小周线模块，13项通过。之后增强同合同的独立边界覆盖，先达到15项通过。根任务审阅要求增加宽calendar资源边界后，先新增2项回归并观察RED（7879周而非40周），修复后最终17项通过，约0.840秒：

```text
.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p test_stage050_weekly_main.py -v
Ran 17 tests in 0.840s
OK
```

覆盖39/40周及手算均线38/35.5/30.5/20.5；周一未来周五、周五开盘/收盘、周四假日末会话、全周停市、source周三截断；等号/下行、坏周不压缩与恢复时点、quote-only/未知执行资格/0量/非正close、所选合约缺价不替代、初期空映射和非因果 observation、未复权roll gap与当日OI干扰、多产品隔离、JSON安全、未知/空产品、重复map/dayprice、非法phase。未来价格和未来映射同时改动，以及只提供历史prefix源，均证明过去收盘/开盘查询及 evidence_id 完全一致。

本线扩展 unittest 同时抓到并行 root 正在先RED的 Stage051：当时共162 tests，8失败全部属于 Stage051 未实现特征，其余154通过。失败方法：

- `test_bullish_long_still_gets_original_budget_and_week_receipt`
- `test_missing_weekly_provider_fails_closed_only_for_longs`
- `test_native_flat_reverse_and_rollover_long_all_require_weekly_bull`
- `test_open_position_does_not_accept_forged_native_size_when_week_bearish`
- `test_missing_signal_weekly_receipt_never_bypasses_fill_gate`
- `test_old_signal_not_replaced_by_reissue_and_new_bear_week_blocks`
- `test_real_long_fill_has_original_risk_budget_plus_weekly_receipt`
- `test_real_long_fill_requires_weekly_rule_and_cleans_rejected_intent`

这些初始失败已明确通知 root，不能把该次运行描述为全绿。Stage051实现及宽calendar修复后，已再次运行本线完整 `test_stage*.py` unittest：**166 tests，25.874秒，OK**；原8项Stage051 RED均已消失。最终验收仍由合入者在全部实现稳定后复核。旧测试导入产生 matplotlib 不可写默认缓存目录提示及 TqSdk 免责声明，没有安装依赖。环境没有 pytest，因此使用原解释器的 unittest，不为本阶段安装包。

代码SHA256：`b0275cf2feb959161cb8dd1d71822829135b9f07d7fcb0a4228dc736daef7060`。
测试SHA256：`f861bc33843e1fa382cb2d79493062f169fc915934f9dbe8a050a52c7c21b020`。

## 参数、金融结果与后续

- 新增参数：固定周MA窗口5/10/20/40、严格多头排列、signal_close/open相位，不做网格或收益选参。
- 修改参数：无；删除参数：无。
- 新增/修改/删除金融回测结果：均无。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：均不适用，本阶段不产生这些指标。
- 未下载数据、未调用生产/账户/CTP/订单接口、未修改原来源映射逻辑或旧金融产物。
- TODO：根任务接入 Stage051/052、冻结新周CSV/源码hash，先独立审查及联合合成验证，只有明确授权后才新金融运行；完整独立日历必须由调用者验证，不能把截断日历当成节假日事实。
- 开始与结束过拟合判断：**否**。固定用户预先指定、对所有品种一致的通用结构假设，没有按品种、年份或收益选阈值；历史选择偏差和后验提出该过滤器仍不等同样本外证据。
- 开始与结束继续价值判断：**是**。建立可证伪的因果周线合同并阻断未来数据有研究价值；此结论不代表收益改善、不支持直接晋级。
