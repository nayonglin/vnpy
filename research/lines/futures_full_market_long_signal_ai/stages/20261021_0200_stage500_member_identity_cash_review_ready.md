# Stage500：具名会员B/C现金账独立审查准备

- line_id：futures_full_market_long_signal_ai。当前day；记录时间：2026-10-21 02:00 CST；非重要突破。只准备独立Stage497现金审查，不改正式C9、不改LINE/registry、不切分支/工作树、不提交。
- 已读registry、Stage495固定协议（SHA d3e3a5430b18ef71293cb950c06c5ef4e68f56d452edad3a8bf2bd343a653918）、497作者代码及已接受491/490/132/102独立会计。调研继承495引用的[交易所披露说明](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)及[维护者字段实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cot.py)；这些只能支持披露会员身份字段，不能证明最终投资者身份、历史首次可见或收益。

## 变更与独立性

新增tools/stage500_member_identity_cash_review.py、test_stage500_member_identity_cash_review.py；旧代码修改/删除0，原参数修改/删除0。脚本不调用拟合器、策略或现金内核，只对已完成保存账做独立成交会计、原生价格/容量锚、预算/持仓、所有导出与raw checkpoint对照，以及原配对indices计算。A只能为157自身四账，不能误用其131B baseline_refs。source/model/held标签与argmax另由498审查；500不冒充全链路重复认证。

静态验证：4个合成测试通过，覆盖primary stress DD须严格更浅、差异未知/stale/执行未知不能过门、破产路径不得修补log、原indices配对和滑点在fill价内不得双扣、raw账费用或身份篡改可检出；py_compile通过。新actual数据/旧账/实际cache读取0，fit/cash/SQL/API/下载0。准备阶段不读取或推断任何新497收益。

## 待授权一次实际审查预算

一次110MB原生cache；8本新raw账与每本9份ledger各唯一文件一次（纯helper复用内存副本）；4本157 own日线和摘要、157 own family表和diagnostics各一次；原252日/2000次两个indices数组各一次；12组配对CI、全95 family零行/年度/截至2025同账截面核对。原129 Y、COMMON、130scores、156大流、原CSV/H5、SQL、金融回放和新增模型均0。每本及汇总phase留checkpoint；失败保留，无自动重试。小JSON摘要会被已接受纯会计helper及绑定收尾分别读取，read计数不声称涵盖helper的直接小JSON读取；大账CSV和cache均走一次hash校验内存读取。

500自身金额比较atol=1e-8、rtol=1e-11；接受旧helper已有金额累计容差（102默认5e-6/2e-11，132默认2e-7/2e-10，diagnostics默认1e-6/1e-10），每个namespace单独披露，不把全等浮点末位误差当策略错误。身份、整数数目和未知语义严格。

权益/总收益/DD/Sharpe/总滑点/交易次数/胜率：N/A，实际回测尚未审查。新增/修改/删除实际金融结果0，当前实际结果不能声称通过。

## 结论与反思

运行前后判断：长期同史择题过拟合风险高，是；本审查不择参、不重跑金融，不能将12组CI解释为blind或因果证明。继续价值是：一次独立有限财务核查能暴露费用双扣、遗漏意图、错误A基准或未知置零等实质错误；重复旧大流和同一核查无价值。SHFE/INE来源不能证实全市场机制，98品种/95族政策仍保留。完整更高收益低回撤/高质量long/极窄损加注目标未完成。下一步仅在root给出完成497精确manifest和once-only授权后审查。

## 输出

- outputs/stage500_member_identity_cash_review/static_ready.json：精确source_bundle、授权JSON合同及读取预算。
- CLI：`.py311/bin/python tools/stage500_member_identity_cash_review.py --protocol PATH --protocol-sha256 SHA --handoff PATH --handoff-sha256 SHA --cash-manifest PATH --cash-manifest-sha256 SHA --authorization PATH --authorization-sha256 SHA --output ABSOLUTE_FRESH_OUTPUT`，tools路径相对此研究线。
- 不更新LINE/registry及根memory/back_log。
