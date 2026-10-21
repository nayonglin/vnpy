# Stage511：独立单位机会持仓状态构造器 CODE READY

时间：2026-10-21 02:51 CST；研究线 `futures_full_market_long_signal_ai`。先读registry及LINE507，采用508科学对象及root510冻结合同。不是重要突破；本stage仅代码和合成fixture，没有历史actual。是否继续actual由root在508唯一科学静审后决定。

开始反思：长期使用同史择题的过拟合风险**是且高**；本轮按收益调参**否**。继续有限构造性测量**有条件价值是**：129遇缺价结束与131/157现金deferred不同，必须先构造真正的单位机会持仓状态，不能把507已closed严格区间当训练风险集。

## 具体改动与边界

新增 `tools/stage511_continuation_unit_states.py` 及独立新fixture；不改旧内核、模型、账户、正式策略。按root510只允许466全动作metadata的14个身份/u资格字段，466完整母grid、132既有native数组、经济投影、日历各一次。代码显式恢复native，不调用旧132隐式数据库stat/protocol读取，不SQL/下载。原N/low20/run来自此前接受的132缓存，在u/t抽取因果字段；仅独立复核缓存legal-bar标志，不冒称重新认证完整indicator或PIT。

实现每条事前eligible机会独立单位价路径：D<K和source lifecycle/listing；D缺价保持entryunknown；原F/0.25N/SL0及同bar止损；正常持仓gap/low止损；缺价保留mark/B并锁deferred，首个合法bar优先open强退；close用own low20和固定u anchor，lifecycle优先于既有force，B可下降但不低于SL0。无账户预算、整数手数、占族、同日冲突或风险减仓，因此不是实际A157账户prefix。

状态只按当日alive/current valid/no force置riskset，不根据下一bar、最后closed/filled、未来持有期或事后价格筛选。缺当前N/low20/prevclose的风险集仍保存，另记state_values_complete；未来训练缺失纪律必须另冻。entry BUY/SELL两场景quote代表性可连接状态，未来SELL失败不反向删alive；价路径仍保留，执行支持未知单列。

未来观察物理分表：baseline terminal reference/date/phase/OHLCV及两场景SELL quote；每riskset t提出最早t+1 open，missing则现金deferred到firstlegalopen，存在bar但quote失败不向后挑价格。仅保存raw reference、fill、fee、slippage、mult/tick及日期/phase；**没有计算Δ、R、PnL或训练reward**。这仍明确包含未来价格原料，不能称无未来信息；它不进入因果状态。

全母域399252、186400无子、98产品/95族/六所与自然有子97/94分开守恒。five tables：action_path_summary、unit_states、baseline_terminal_observations、voluntary_exit_observations、mother_domain；输出压缩字节边写边hash，失败保留checkpoint，不自动restart。

## 验证与已保留纠偏

9项新合成fixture已通过：入场同bar stop、stale/deferred首价强退、固定anchor/force优先、B非ratchet、D=K/lifecycle、未来bar/terminal变化不改变先前riskset、未参与/entryunknown/open保留未知、Decimal SELL tick-floor和不可表示quote、tiny全源流及5表守恒/未来字段隔离。没有运行仓库旧全套tests或重复历史回测。初次新模块不存在、SELL函数不存在的RED保留；tiny日历初版错误等于sample_end，触发了合法source-lifecycle sentinel，fixture改为像真实5587calendar那样延伸到sample_end之后，政策未改。

静读489 producer时发现其所谓causal projection只含2020+966740，不是全1552456；已立即报告root并在任何actual之前改为466全metadata白名单+native因果参数，未读取错误大源或重跑历史。

CODE READY：`outputs/stage511_continuation_unit_states/code_ready.json`；包含exact source bindings与五表字段。代码SHA `c8056cb396efa1fb3f2543932162d8cfd1297803a6e8c71a739a12a3787931cb`，test SHA `b4df104d337fea5b3c0e1a8c99abe54507ed9ef0de974a16c27f0f48189aa848`。root510 protocol SHA `f19257726a1ff8d43b2609e65e4a2b1ae63ed650d4ca6112055caafb4c93f1b8`。

本stage历史metadata/native/价格/经济大源实际读取、SQL/API/下载、fit/cash/reward均0。仅小代码/manifest/一行schema前缀读取与synthetic I/O。新增/修改/删除策略参数0；新期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。累计505fit/274完成cash及1旧partial不变。不改LINE/registry/rootmemory/back_log/正式/生产/CTP/邮件/调度/Git。

结束反思：按收益救参过拟合**否**，同史长期择题风险**是且高**。继续一次root授权构造actual **有条件价值是**；现在拟合、跑账户或加注**否**。全市场高质量做多/更高收益更低回撤/窄损加注目标active未完成。
