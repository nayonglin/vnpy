# Stage044 固定12项asof特征与首次过去panel

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:59 CST；非收益突破，只新增本线工具/输出/stage，不改LINE/registry。
- 按Stage041，未来target与过去AM41特征分开。本轮不读未来标签、不fit，正式A/C因身份缺项仍禁跑。
- 实施前冻结合同outputs/stage044_asof_features/contract.md：20/40 logreturn绝对能量与效率、ddof0波动20和5比、两MA差/ATR14、ATR14/close、abs(RSI6−50)/50、volume5/20、OI lag20对称变化。Wilder ATR14/RSI6从41窗口默认TA-Lib初始化，合法零分母0，missing不填0。平价TA-Lib RSI0导致第10项1事前明示，未依后续表现改动。
- 只读冻结m0008 qmt_universe.py的PRODUCT_SPECS AST与manifest，原18清单与SHA在old18_binding.json，固定fu不在18。未import配置或运行写文件generator。

## 实际输出与发现的错误

21:58:49–57首次构建19,698=98×201月格，8,998已知12特征、10,700未知行全保留，368,918精确同epoch pastbar。69固定分层样例/1,059source与独立Wilder算术检查通过；DB与040panel stats未变。8项模块TDD先失败后通过，全线当时140通过。future labels/fit/金融回放/订单/下载0。

首次domain_role存在case身份错误，未接纳为分组比较输入。冻结原名单混用大小写而clean panel统一大写，直接isin只有8个CZCE品种匹配；fu.SHFE直比FU.SHFE也漏fixed。18名单与12值/source keys/缺失状态正确，只有分组标签错误。root同时发现且没有fit；原044输出/receipt冻结，源码快照与role-only修复验证另见Stage048。旧原18已知1010/原18外7965表述不得沿用。

## 调研、判断与反思

已查[sklearn官方泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)、[TA-Lib官方仓库](https://github.com/TA-Lib/ta-lib-python)、[ATR维护者源码](https://raw.githubusercontent.com/TA-Lib/ta-lib/main/src/ta_func/ta_ATR.c)。判断：固定asof无监督变换可预算，scaler/填补/特征选择必须train-fold fit，产品身份先标准化再比较。12项未因未来表现调整。

开始/结束新增收益择参过拟合否，无未来target或真实收益试算；继续价值是，但须先修分组bug。新增12研究特征/合同，正式/模型alpha参数新增修改删除0；权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A。当前044保留首跑证据，后续使用048修复版。
