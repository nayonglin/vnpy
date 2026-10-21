# Stage328 历史输入连接独立审查（实际失败）

记录时间：2026-10-20 03:15 +0800。所属线：`futures_full_market_long_signal_ai`。非重要突破；本阶段没有金融回测。

本次仅审325调用器、326快照/预热和327一次胶水。沿324范围固定132缓存末日2026-10-16，复用130 main2023原52 portable/scaler。未增加策略、参数、模型或历史选题；网上/外部方法沿318及root已核材料，本阶段不重复搜索。

325/326冻结新源各一次静读，新tiny结果仅审收据，不执行：325集成组1方法最终GREEN 0.355秒；326预热组1方法/3子例GREEN 0.227秒；未跑320/321/322旧组。核了cached N不重种、尾窗前检查点、无当日报价不carry、当前OI、null/missing flags、同核心注入、观察模式资金隔离和真实UTC提案末闸。初始静态收据core0的全域段落遗漏了loader把产品目录强等于native产品集合的问题；实际失败已经反证，原收据保留不改，本失败收据明确覆盖该结论。

唯一327实际尝试于北京时间03:11:58启动，终态`failed_no_retry`，exit1，耗时0.370523834秒，报`original complete98/95 domain mismatch`。计数为cache1、econ0、dataSQL0、fit0、cash0、financialD0、forward0；T0仍为空。前后绑定源stat一致，未重hash大源。新terminal未含session ID，本审查不补造。

**P1：目录域与有报价源域混淆。** 326从非空native epoch派生products，再要求98/95且与roster相等。小004 roster共有98产品/95families，其中97产品有source observation，DCE.S的source_observation_rows、qualified_candidate_rows、contracts_with_candidates均为0。因此完整母域不能以必须存在native epoch定义。本审查没有为验证精确缓存产品数再加载110MB缓存；因果由失败位置、已核逻辑和小roster共同支持。

最小修复应由roster保留98/95完整母域，native源域单独核其覆盖；无native/current者明确无观测，不造报价、不填0、不缩域。root已将必要修复隔离为330新文件/一组目录回归，旧326/327不改、不自动retry。后续任何新实际需新冻结授权。该故障发生在econ、SQL及325调用前，所以本轮没有完整观测/raw26/design52/score/资格/K/clock/journal或Wilder实值可供全数独核，不能宣称这些实际已通过。

复核只读新小terminal/source_failed/protocol和小roster；reviewer cache/econ/SQL/测试/fit/cash/网络/大表均0。原static收据与新failure收据在`outputs/stage328_historical_snapshot_review/`，均有精确bindings。

过拟合反思：否，本次修复的是金融结果出现前的可观测产品域错误，不涉及收益反馈或参数；但它不提供alpha证据。继续价值：仅限一次最小正确性修复及独立核验。收益、权益、DD、Sharpe、交易数、胜率均未运行；receiver、实际源完成/PIT、D开盘时钟、正式forward和T0仍未建立。
