# Stage685 单族计划风险0.5%机械复用实现（source ready，未运行actual）

- line_id：`futures_full_market_long_signal_ai`
- 记录时间：2026-10-21 17:44
- 模式/阶段：冻结684后的隔离实现；root独占唯一actual_run1启动权。
- 是否重要突破：否；无新增实际财务结果。
- 是否触发A/B：研究基线A(.25%)与候选C(.5%)同历史单点资金风险敏感性，不接入正式策略。

## 外部调研与判断

- 沿用684冻结研究来源：[CME按风险与止损定仓](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[backtesting.py原资金/保证金约束](https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py)。未下载或导入第三方实现。
- 判断：本次0.5%来自用户在看过1%后追加的历史单点，属于适应性历史跟进；不得称为独立预注册OOS或最优仓位。单族预算相对.25%虽翻倍，共同2%风险、25%保证金、整数手、容量及D开盘约束仍使实际路径非线性。

## 变更与固定合同

- 新增`tools/stage685_single_risk_halfpct.py`和最少必要`tools/test_stage685_single_risk_halfpct.py`；仅本线新文件。
- 来源：逐字机械复制最终680 runner（SHA514ec1988c7e11bc51180afc9ec70a05b5cd2200353be0c4010182054f3b50a4），仅替换阶段679→684/680→685、协议hash、onepct→halfpct、risk100→risk050、新风险.01→.005及文字标签；逐字替换等价校验通过。
- 策略修改参数：仅SINGLE_RISK：原研究基线.0025→新候选.005；其余参数无新增、修改或删除。未修改680或任何旧脚本/证据/global。
- 三层私有FunctionType结构不变：070 reserve_batch的真实globals路径使用.005，131容量函数接私有预算函数，131 cash函数接私有容量函数；原code/defaults与所有其他全局依赖复用。
- 固定TOTAL_RISK=.02、MARGIN_CAP=.25、MARGIN_BUFFER=1.1、初始止损=.25N、原COMMON52+K、信号、成本base/stress、容量1%、共同scale先capacity、D仅减量、存量仓入场风险冻结及次日减仓。
- 684输入16roles与679完全相同：原675信号5246条、完整129母事件399252/98产品/95族、132已归档native缓存；不读actions/COMMON/scores/模型，不读/重放1%账户。0fit/2newcash/0旧cash/0SQL/0下载/0新labels/scores/0bootstrap。
- 窗口：2015-01-01—2026-10-16，实际首日2015-01-05，2862源日；初始权益1,000,000，连续不重置。新账户`all_2015_halfpct_base/stress`。
- 输出保持680形状：新两账ledger/summary/daily/diagnostics、四账年度48行、新两账95族零格2280行、.25/.5四曲线宽CSV及预算约束/参数实效/源IO收据；687单独汇入680小数据绘制六账图。

## 验证和结果

- TDD：先观察685实现缺失使4项合成测试失败，再机械生成runner；4项全部通过，无真实数据载入或actual回测。
- 已验证：孤立raw预算为.25%基线2倍且allocated risk=5000/百万；5族共同2% cap与.8 scale保持；capacity后置不重分配；真实合成cash入场调用抵达.005预算；风险单价和.25N不变；原global前后identity不变；新actual输出身份提前拒绝其他目录。
- 未重复42项旧测试，沿用最终680已验约束；本次只做必要风险生效fixture和机械源码等价核查。
- 实际期末权益、总收益、最大回撤、Sharpe、总滑点、交易数、胜率：尚未运行，无新增结果。
- source_ready：`outputs/stage685_single_risk_halfpct/source_ready.json`；实际输出`outputs/stage685_single_risk_halfpct/actual_run1`尚未创建。

## 反思与后续

- 运行前过拟合判断：本次追加单点具有高历史适应/选择风险；实现本身没有新增alpha或扫参，不因结果继续改总风险、保证金、止损或模型。
- 运行后过拟合判断：目前只有fixture，不产生新收益结论，不能解释为最优仓位、正式晋升或加注资格。
- 运行前继续价值：有，回答用户指定0.5%在固定组合上限下的风险收益路径。
- 运行后继续价值：有，待686最终source_GO后由root授权一次两cash，保留全部正负结果再独审；禁止自动重试或救参。
- TODO：最终ready后冻结runner/test；686仅审最终hash；root跑两账；686一次终态独审；687六账图与浏览器验证。
- 不修改LINE.md/registry.md/根memory.md/back_log.md，合入由root统一处理。
