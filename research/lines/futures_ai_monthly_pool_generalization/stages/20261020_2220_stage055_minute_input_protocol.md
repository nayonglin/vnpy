# Stage055 统一本地分钟输入资格合同

- 时间：2026-10-20 22:20；重要突破：否，不改变alpha/正式策略/模型。
- 调研：[Backtrader订单执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)与[vn.py维护者回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)均把bar级成交建立在明确的执行规则上，并不是历史tick事实。本合同不复制其成交策略，只采用“输入身份与执行假设必须明确”的原则。实际C2仍绑定仓库当前参考kernel，不因补数据改政策。
- 判断：继续增加模型复杂度价值当前否；统一核对现有分钟输入的价值是。Stage054已定位132个在既有2020+产品参考范围内的首阻塞需求，小缓存428文件约332MB及SQLite候选可作列投影，不能只挑旧accepted的31个，更不能按结果选来源。

## 冻结合同

1. Stage052全部910精确epoch/交易日需求保留；只有source_trade_date>=2020且产品在既有reference helper literal名单内才生成参考grid，132个统一审计，其余778标unsupported不硬套历史会话。不扩helper时段/产品、不假定新产品符合旧规则。
2. grid继承已有源日历、left-labelled分钟、前一交易日夜盘与节假日/COVID约定。这只是冻结研究参考grid，不认证真实历史session或broker身份。reference token只用于选择产品时间表，不给交易API使用。
3. caller必须显式绑定exact epoch、source_trade_date、source_id和identity_basis。不能把当日代表或native短码当完整epoch，尤其CZCE重复年代代码须有明确约期/日期依据。
4. 单文件、单provider component分别审计；不拼provider/缺分钟、不补时间、不改OHLC。要求每个reference分钟恰一条、价格有限/正且geometry正确，aggregate OHLC逐项匹配当前clean精确epoch日线，first open等于source entry_price。
5. 资格模块只审输入，不计算/筛选C2结果或收益。同样完整但不同路径的合法来源全部保留finite paths；完全相同输入可按内容SHA去重，保留全部来源身份，不以结果挑provider。其他冲突、残缺、无身份与unsupported全留拒绝原因。
6. 通过的产物仅`conditional_reference_input_qualified`，physical_session_verified=False、broker_symbol_qualified=False、usable_for_trading=False，不能升级历史PIT、实际会话、tick先后或完整60日标签。首C2阻塞补上后仍可能有后续阻塞。
7. 小pilot按固定最早/最晚、既有AU/JM、缺格反例输入选择，无代码bug再自动全batch；全部范围同一规则，不按是否能补足第三年度块择数据。

## 实现与验证

- 新增`stage055_minute_input_qualification.py`及5项TDD，覆盖完整grid、缺/重/多分钟、epoch不符、日线冲突、非法geometry、混provider、Friday夜盘归Monday、pre2020/新产品unsupported。先缺模块见红，实施时一个dict语法错误已修，最终5项绿。
- batch启动前Stage057独审与root自查补3项TDD至8项：声明provider与实际component不符、frame显式epoch/day与请求矛盾、双方互缺/空identity不得以None==None通过，另收紧源价格bool/NaN及ISO日/epoch年月。均先红后绿，未生成真实payload产物前修复；实际合法052请求不受金额影响。最终资格模块SHA为`9736b1b0a362e4a12b2c7839db067c59e0a3b430be0c65c384f2a4433ba9d8c2`，batch另绑定该版本。
- 后续Stage056运行统一实际payload审核，Stage057独立复核；不先注入源、不重训。无新增/修改金融参数或删除旧结果。
- 账户期末权益、收益、回撤、Sharpe、滑点、交易数、胜率均不适用，本阶段不是账户回测。
- 开始新增按收益选参过拟合：否；仅按固定数据身份与参考会话审输入，已有会话/资料选择风险保留。继续价值：是，能确认“已经下载”的资料究竟有多少可在同一声明研究合同下使用。
