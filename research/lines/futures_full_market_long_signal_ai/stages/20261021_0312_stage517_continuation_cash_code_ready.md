# Stage517 固定续持退出现金实现（尚未实际回测）

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-21 03:12 CST；当前分支沿用研究分支；仅本线新增文件。
- 是否重要突破：否。是否触发A/B：承接514固定A/C实验，尚无金融结果。

## 调研与判断

沿用514收益前冻结的低容量续持模型设计；原始方法参考 [mlOSP作者仓库](https://github.com/mludkov/mlOSP/) 及 [Ridge官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)。方法提供继续/退出的建模框架，不证明期货策略alpha。最重要的实现判断是：账户主动退出改变资金、占用及后续重入，必须以候选真实账户持仓状态评分，不能把511单位路径的未来退出日复制为账户退出指令。

## 本次变更

新增 `stage517_continuation_cash.py`、`stage517_continuation_kernel.py`、`test_stage517_continuation_cash.py`。旧131、157核及正式版未修改。原131循环在本地新核中保留，增加显式close评分钩子；禁用钩子时在合成持仓/缺价案例上与旧核完整返回账本逐值相等。

新增参数：无可调参数。固定模型finite prediction<0才锁定下一原生日开盘退出请求；等于0或非finite继续持有。六X/六missing和train-only标准化由515实现。模型头按当前close日期切换，2020—2022使用2020头，2023起用2023头，不按入场日固定。年龄为`t_index-entry_index+1`；前close仅同epoch前一原生日有效bar。

修改/删除旧参数：无。入场N、0.25N初始SL0、own20low、u锚、source lifecycle∩K、100万资金、family0.25%/总2%风险、25%buffered margin、1.10缓冲、1%交易量容量、两套原费用均继承。

账户close原prepare安排实际减仓后，只有非stale、无原强退、无实际`reduce_to<qty`且未锁定请求的持仓才调用模型。零数量减仓记录不额外封模型。次日执行顺序：原force/deferred > 原scheduled reduction > voluntary > 原intraday stop。主动请求遇缺价不撤销，继承原deferred并在首有效open按原强退优先执行；不重置SL0/边界、不加注。

## 源与运行预算

四个新C现金候选：2020全期base/stress、2023冷启base/stress，截至2026-10-16。A只引用157 OWN VOLUNTARY_RESELECT四账，绝不误用157自身baseline_refs131B，也不重跑A。

拟单次只读511 action summary的17项事前字段、完整mother域、489原Achoices、accepted132 native数组、经济快照、原日历；源summary含未来列但pandas明确usecols白名单排除terminal/exit/outcome列。保留98历史产品/95family完整母域。原129、COMMON、单位未来退出观察、SQL、下载均0。一次四账先各自保存raw pickle checkpoint，再导出及比较；报告故障不得隐式重放金融。

## 验证与结果

8个新合成测试通过：disabled完整旧核parity、负值次open及零值hold、原forced与真实减仓优先、D缺价锁请求后deferred、零量减仓与invalid预测、跨2023按当前close换头、入场同bar止损不触发模型、事前字段白名单不物化未来终态。

真实fit/现金回测/SQL/大源/native读取：均0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A（尚未实际回测）。累计历史fit/现金数未因此增加。

## 结论与后续

代码准备完成，需515最终portable/handoff接口、516实际模型独审通过和root精确源授权后才能首次实际现金运行。代码阶段不是收益改善证据；随后只跑四个新C账户、完整独审及与四A比较。不扫阈值、模型、风险或成本救分。

## 反思

运行前/后过拟合风险：是，长期反复观察同一历史和择题风险仍在；本阶段未根据新收益调参，0新金融。继续价值：是，固定条件退出是真实新决策对象，且实际现金检验可以反证单位模型收益能否传导到账户；这不缩减全市场高质量入场与更高收益/更低回撤的完整目标，也无加注/上线资格。

不修改本线LINE/registry，由root闭环更新；不追加根memory/back_log。

## 03:15 必要独审观测补充

应519源审，before已有完整母表RAM新增最小canonical_references.csv.gz三列product_id/u_index/reference_epoch，全部399252母含空reference保留，manifest自动绑定。用于独立验证anchor强退因果，避免独审第二次读取旧511母表；额外大源读取0，策略核与参数不改，actual仍0。仅编译验证，不添加显示导出测试。
