# Stage322：原131连续paper状态的最薄桥接

- 时间：2026-10-20 02:58（Asia/Shanghai）；line_id=`futures_full_market_long_signal_ai`；非重要收益突破。按319/318完成代码接线，不是新alpha实验。
- 本阶段只写322 tool/test、implementation小证据和本文，不改原070/131、LINE或registry。0实际行情/大表、0fit、0研究cash、0SQL、0旧控制重放/旧suite；未初始化真实state、未设T0、未安装receiver或调度，也无真实资本。
- 调研沿318已经核读的[scikit-learn官方预处理/泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html)和[Freqtrade维护者因果诊断文档](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)：先封当时输入与决策、再消费后续行情。没有新增金融文献/库/下载；它们不构成策略有效性证据。

## 完成内容与接口

[工具](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage322_continuous_paper_state.py)：17091B，SHA256 `8d015968b9c91938e3ac1b38d09b3082fe89bc8ea3e9ea7f12bef47dad989a1e`。
[唯一tiny组](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage322_continuous_paper_state.py)：7993B，SHA256 `31c01d61eb86882b28ecae4d9566a25b3def1f6f58a044313273430a46064d85`。

函数式API均返回副本，不更改传入state：

```python
new_state(*, scenario, account_id, start_u, base_kernel, initial=1000000.)
seal_u(state, *, u_index, prepared, market, dates, economics, base_kernel)
advance_D(state, *, D_index, references, market, dates, economics, base_kernel)
export_state(state)  # canonical JSON envelope，含state内容SHA
restore_state(payload)
```

prepared直接接320的`({u:signals},{u:full_product_anchor_references})`，索引为整数。advance只接已封u的候选及当前D的anchor refs（`{product:anchor}`或`{D:refs}`）；不能用新D潜在信号重新挑入场。321负责真实completion/received/sealed/Dopen/T0分型，322只管逻辑相邻日期、场景/account、phase与状态经济一致性，不自行给forward资格。

新state固定NARROW、一次100万、原风险成本及注入的原核身份。state包含last_u/last_D、连续daily、原ledger/capacity快照、budgets、pending、position_days、entry unknown及封存source/econ/预算/ledger hash。只有调用者在未来另获授权后才会真正创建观察state；本轮new_state全部在synthetic内存中。

## 原核复用与连续边界

seal从原131 run的`co_consts`取唯一prepare CodeType，用明确closure cell绑定ledger、budgets、potential、dates、economics、scenario等，原函数/模块不改。market wrapper拒绝读取u以后的bar/indicator。它从本场景自己的E/F0/margin生成原实数预算、capacity cap及pending，保存来源与经济字段摘要。

advance用私有globals和恢复的CapacityLedger工厂执行原run（start=end=D）；原prepare在D价读取前重算u预算，与已封经济字段hash比较才继续。保留原D强制/减仓/stop、pending仅用自身预算、取消不回收、收盘mark/boundary/anchor顺序。single-D的end哨兵不prepare当前D，因此下一seal_D显式补该日new_order_reserve及对应risk/margin/fee字段，防止切段丢pending。

恢复包括CashLedger initial/realized/fees/slippage/positions/closed/fills、容量audit、tuple-key gross与unknown set；JSON存显式tuple记录并恢复budget_id关联，pending和reduction_record不因序列化丢失对应预算。ever_insolvent以原guard OR前态保留。拒重复u/D、错误phase、账户/场景串态、calendar改写、封存后经济/候选/ledger/pending改变。输入非有限辅助值以null保留未知，不填0。

**有限样本→连续运行有一项明确的表示适配，不能只因run bytecode相同就声称全等。** 旧calendar外expiry可能是len(calendar)哨兵。320给出固定source_lifecycle_target_date/K_target_date，322按min目标保存有效target，私有LocalLedger.enter按event把lineage带到position；原131 root原本不会复制这些字段。target尚未映射时用len(calendar)+1临时哨兵并明确expiry_state=pending_calendar，不称真实K/到期；calendar只追加，映射后沿首源日>=target确定索引。既有持仓也重绑，在seal_u的原收盘同位用原anchor_request刷新next force，不改已封target；D日期达到target时必须映射/执行原规则，避免一天假平仓或漏真实到期。

state的source/K字段保留当时lineage，expiry_state表明当前calendar映射；不把后获日历知识倒填成旧decision当时known。若nextD仍未确认，321/未来runner保留时钟unknown，322不声明已及时产生真实退出决定。

## 唯一状态tiny：RED→GREEN

没有运行旧131测试，只读其fake market/econ示例。新一组实测先因322缺失预期RED1fail，随后实现；中间两次ERROR定位到marshal对nested CodeType引用状态的序列化差异，非预算/数据错误。已改为稳定code字段fingerprint，不改策略。最终同一组GREEN：1test、exit0、0.249s；py_compile exit0。过程及真实终态见下列fixture receipt，不把中间错误隐藏成一次即过。

一组内以真131纯synthetic验证两相邻session、checkpoint/direct continuation一致、base/stress独立、entry缺价与持仓stale/deferred、pending、ever_insolvent、重复D拒绝、D不回收、calendar pending→确认目标及原模块不变。两个成本情景各含分日、恢复和一个原核小窗口对照，共8次synthetic kernel调用；没有任何真实账户/旧历史回放，研究cash计数为0。

手算预期：base第三family D1=378手、权益1002653→997739；stress=136手、权益1000137→997553。首family capacity仅1、另一family D缺价不腾额度给第三family；次日一仓缺价保留unknown，一仓按原lifecycle退出。成交/费用/权益/容量audit与同一小窗口原131一致。上述价格和权益是测试常量，**不是回测成绩或前瞻收益**。

## 源束、边界与反思

- [source_bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage322_continuous_paper_state/implementation/source_bundle.json)：3619B，SHA `b5538081ab1853613e6233e54513868219fc52543a48def6c2ff60a6e3cfc382`，绑定最终tool/test与原131/070/042纯依赖和API。
- [fixture_terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage322_continuous_paper_state/implementation/fixture_terminal.json)：2656B，SHA `2a9ec741cd8f8b87a28505c47977ea1f7d5cdd3b6fbd565ba02f32211acee721`。
- final源码已一次发323独立静审，未请求复跑tiny；当前本文不提前写323验收结果。root321可依确认接口对接。

原single-D summary不作为连续DD/Sharpe输出；state保留daily/ledger连续链，未来报告仍须对应成熟度。真实输入接收、firstseen、clock/deadline、全98新日生成与catalog缺口、真实观察初始化/T0以及生产资格均不由这一个桥证明。

新增的是状态接口与明确pending expiry表示；金融/模型参数修改、删除均0；未重训、未启用312或新策略臂。期末权益、收益、DD、Sharpe、总滑点、交易次数、胜率等真实研究结果均N/A。累计完整453fit/246cash不变，315的1个未完成尝试另记。

开始与结束反思：新增寻优过拟合操作为否，原政策历史选择风险仍在；继续最小接线有价值，因为它使冻结后的输入与连续状态可被核验。测试通过不证明alpha、跨周期、高质量或实盘ready，不授权加注或救参数。用户完整目标仍未实现；本322在源/fixture交付后停止，不碰真实数据或预设T0。
