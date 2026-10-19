# Stage060 当前交易合约周线修正预登记

- line_id：futures_trend_full_market_noai_one_lot；时间：2026-10-19 20:11 CST；同工作树codex/full-market-noai-one-lot，旧研究源和原工作区不改。
- 用户明确修改：周K改用当前交易合约自身，不用主力连续；承接先前已批准的100万、全市场、无AI、多空全部case、原预算最多1手、无4品种上限、不加仓、日线近似和缺冻结供需过滤停用。空头/全部平仓/env_probe不增加周门。
- 本轮为价格序列语义修正，不优化收益。不创造正式晋级A/B/C，不读取或替换原生产身份。原始无周门预算A：87487e32d/a8696e2b73b25399251d1efc46e47dfd49f89d23bfc80f6bc1f33bfdbe5237c3；前版主力周C：12f9d3500/7e6f2647de1d99253ba2cbade3e0852158d50d3cbfde19e8da4afdba6f16fed4；当前新合约周版在前版策略合同上只替换周线提供器和双身份绑定，其余native参数与A逐键一致。

## 调研与固定设计

已查[pandas官方resample](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html)与[backtesting.py官方实现](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)。判断：高周期可用时点仍需独立日历，单一合约历史不足时必须如实拒绝而非拼主力。该口径更准确对应具体交易对象，但较短上市历史可能机械压缩机会，不能默认收益或质量改善。

- 新058：按exact vt_symbol隔离，自身accepted-clean末会话close，原始不复权；完整calendar先判周末，再限制合约listed_date到本地末行情周。仅查询所需合约并cache，导出weekly_contract_features为已查询合约完整本地周表subset，scope/名单/行数显式写manifest，不冒充4328全合约预计算。
- 周MA5>MA10>MA20>MA40严格>；最近40个有会话自然周均有效，不压缩缺周、不用其他合约填充。新合约不足40有效周不开多。最新应完成周缺失也不得复用更早allowed快照。
- 新059：普通/反手/移仓重开/旧单都按实际目标合约自身周线；同时核contract与product，原信号冻结授权不能借同品种另一合约。signal_close只准week<=信号日，open只准week<成交日，不能读周五全天close；均线通过不能复活native预算0。全部short/CLOSE/env_probe直接super。
- 新060：基于052隔离入口仅替换provider/candidate、证据名和身份/日历导出；source市场/mapping/metadata/成本/期间/native参数不变。交易合约选择仍依原因果主力映射，但周门历史不依主力映射。新增trading_calendar.csv冻结完整原日历；source已有contract_metadata.csv复用。
- 新062/063：资金总览保留042绘图、显式比较无周门A/前主力周/新合约周。逐笔周K同样只用实际合约OHLC及MA；仅替换原weekly payload，原坐标、显示窗、其他周期、排序、entry/exit与R保持。有效EOW但周内缺日时只聚合真实日并披露缺口，不用主力。无有效EOW时留空；不存在完整40周均线则显示缺失。

## 参数、试验与验收

- 新增政策：exact_traded_contract_unadjusted_accepted_clean，product+contract授权绑定；周参数5/10/20/40及40周、严格>、双相位均未修改。原金融参数新增/修改/删除：0。旧050/051/052/055及旧产物不变。
- 唯一拟金融输出：outputs/run_20261019_contract_weekly_long_v1；2014热身、分析2015-01-01至2026-10-16，实际首会话2015-01-05；100万。不得覆盖任何旧run；失败保留并先独审，不按收益救参。
- 测试先行：059先13 tests中9个真实行为RED、无import ERROR，再实现13全部GREEN；060真实MRO/预算及A参数一致3项GREEN；058合成16项RED→GREEN。联合金融相关206 tests通过；062/063显示测试独立后续验收。
- 预运行独立Stage061后冻结代码提交，再跑一次完整回放；结束必须Stage064独立复核raw exact合约40周/信号开盘两相位、原预算/1手/会计/生命周期/残仓、参数数据代码hash及置信度。全部真实开多合约身份证据/预算违规必须0。
- 报告期末权益、总收益、最大回撤、Sharpe、滑点、手续费、成交次数、完整笔数、净胜率、净盈亏比及年度长短贡献；三版本同区间描述对比不当样本外或正式资格。全量复盘与曲线验收后仅更新本线并保存版本。

## 运行前反思与待填结果

过拟合操作判断：**否**，修正用户指定序列语义，未按收益选窗口/品种/年份；仍属看过同一历史后的研究，有后验偏差。继续价值判断：**是**，须验证正确口径实际结果、机会损失和实现正确性；不因改后结果更好就宣称正式晋级。

本记录写入时无新金融回放结果；期末权益、总收益、最大回撤、Sharpe、总滑点、成交、胜率均待完整实际运行。新增/修改/删除旧结果均无。是否重要突破：否。TODO：完成预审、唯一回放、独审、全量规范HTML和真实交互验收；若无稳健改善，不追加调参。
