# Stage325：最小caller接线，观察与资金状态严格分开

- 时间：2026-10-20 03:11（Asia/Shanghai）；line_id=`futures_full_market_long_signal_ai`；非重要收益突破，非新alpha臂。
- 先读registry、324 decision/next_scope及320/321/322 final，与326对齐snapshot。只新增325 tool/test、implementation证据与本文；不改原核、其他agent源码、LINE或registry。
- 本阶段0真实snapshot/cache/econ/SQL读取、0fit/研究cash、0旧控制回放/旧suite。唯一integration组使用合成数据与真320/321/322/131，只有本地时钟被mock。T0=None、没有真实state初始化或receiver/调度；累计完整453fit/246cash及315的1个未完成attempt不变。

## 交付与调用

[工具](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage325_forward_caller.py)：11770B，SHA256 `1a4937b204a166155ceefbc3240297802c97ae644493909b327461b994ea1936`。
[测试](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage325_forward_caller.py)：10067B，SHA256 `293285050a231fc41b051875635b6ccb926671366f2bb2e89e268082cea3fd08`。

```python
parts = caller._components()
snapshot = adapter326.load_snapshot(auth, output=path, core=parts.core)
identity = caller.make_policy_identity(snapshot['model'], snapshot['scaler'], frozen_at=None)
journal = parts.journal.ForwardJournal(journal_path, identity)
result = caller.process_snapshot(
    snapshot, model=snapshot['model'], scaler=snapshot['scaler'],
    journal=journal, policy_identity=identity, mode='observe_only')
```

上面仅展示root327获授权后的调用顺序，本325未运行它。326当前series含WilderState，必须注入同一个parts.core，避免同源320重复加载后的class identity不一致；integration使用了这个确切shape。325无CLI或数据loader，root327是唯一实际wrapper/authorization owner。

返回严格JSON-safe结果：完整observations（mothers/candidates/raw_rows/references/statuses）、完整raw26/design52/score、原selection choices/audit/boundaries/signals/prepared、input/observation/decision receipts、clock、counts与可选states。raw合法NaN转null，原missing flags和状态保留，不把unknown填0。已载内存里当前候选用到的instrument_evidence及cost_scenarios也随返回/journal保存，供328复核最后2列/单位而不第二读8MB经济投影。

## 观察mode的硬边界

observe_only不接受states或base_kernel，代码在接触paper方法前返回；new_state/advance_D/seal_u调用数全部0。development_only snapshot禁止切换future；不能靠传入伪T0把2026-10-16历史演练冒充前瞻。无确认D/完成clock时照样输出98观察、missing与完整评分/选择audit，不为得到selected造D。输入由外部受授权adapter提供，325不下载/查询/补日历。

identity绑定唯一原纯52 main2023模型/scaler内容、320/321/322/325小源码SHA及调用者提供的冻结时点，不自行创建T0。root327另外绑定实际原资产/adapter/输入协议与source authorization；当前frozen_at仍None。journal必须为真321 append方法和同一policy identity，不接受任意caller-made receipt provider。

snapshot中的received_at只作claimed metadata；实际received_at一律取321 input_snapshot receipt的recorded_at。该时间由append时本机UTC产生，不能将快照中的1999年或历史日期当首次接收。它仍不是交易所首次发布或外部PIT证明。

## 可接未来的有限链

1. journal追加input取得真实R；320生成当前u完整observations和全部anchor refs。
2. 仅已冻结且u确为冻结后完成、接收不早于完成时，允许对外部已初始化的base/stress状态推进：先用完整当前refs将前seal的D=currentu推进，保留各自own E/F0/margin。phase、日期或policy不匹配不偷偷初始化/补空仓；已有history的state须有同一caller_policy_sha256。
3. 原320评分与全域selector随后给prepared，再用推进后的各自own-state准备预算。源/模型/scaler不改变，states始终副本，不修改调用者原state。
4. 先追加decision_start取得实际pre-gate时刻，321不判timely就不调用322.seal。通过后仅在内存构造候选state；完整候选budgets放入immutable decision_proposal，明确active=False，再取该对象自身receipt S作最终时钟校验。
5. 只有S严格早于Dopen才返回active候选state，并追加派生classification。最终seal时间是包含完整预算的proposal receipt，不用调用者填的时间，也不用后续分类时间回填。若S已经跨Dopen，proposal保持inactive，只追加state_gap，返回已合法推进的事实state；不提交候选pending，不用空仓或零收益替代状态缺口。

未确认D时不以未来bar存在推断D；缺完成/开盘clock保留unknown原因。未冻结状态不会推进D。base/stress分别保留，不把其中一个场景的账户或policy接入另一场景。某次gap使下次u不连续，显式保留gap；本模块没有自动重放、补单或恢复系统。

## 唯一integration组的真实证据

预期RED：325缺失，1fail。首次实现GREEN 1test/.334秒；自查增加“未冻结不advance”“跨policy state拒用”及当前经济证据子例时，因尚无instrument_evidence产生1个KeyError，随后实现缺项并通过最终同组GREEN 1test/.355秒、exit0。py_compile exit0；没有复跑320/321/322三个旧组或增加第二个integration组。

该组真核覆盖：98父域加所知unsupported、无D的observe全评分与null/mask、接收时间不能回填、模型/scaler/source身份、两成本连续own-state、当前refs先于D事实推进、每场景更新权益后才封新预算、future无T0不advance、unknown D不seal、旧state不能换policy，以及pre-gate及时但完整proposal恰在Dopen时变late、不提交候选pending。

字面合成预期为base当前D权益999450、stress998850，各下一u原风险冻结额恰为自己权益×0.0025，证明没有继续用初始100万或另一成本场景状态。时钟mock仅驱动真321 append，数学不mock。组内2次synthetic new_state均在测试外部初始化，caller自己0次；4次synthetic advance_D、6次seal只是小fixture，不是4/6本研究回测，也不公布这些测试金额为策略收益。

- [source_bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage325_forward_caller/implementation/source_bundle.json)：3642B，SHA `9d3b8570df7aae0adff29f38ab864c124ca3216c235eeb68a5f69a9e8f651f1e`。
- [fixture_terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage325_forward_caller/implementation/fixture_terminal.json)：2665B，SHA `90e37ef2d939c4efefa500bdf07e80a2d04e4313586faded1da653fc65e7d2fe`。
- 最终源码/测试/小终态已一次交328静审；本阶段不提前写其结论。root327将另行冻结并独家运行固定历史snapshot，325作者不执行或轮询actual。

## 研究判断与终态

本次沿318/324已核的[scikit-learn官方泄漏与预处理原则](https://scikit-learn.org/stable/common_pitfalls.html)、[Freqtrade维护者lookahead说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)做接线，未再检索/安装/clone。它们支持固定预处理与因果记录，不能证明中国期货alpha。

新增的是caller/identity/receipt接线接口，模型/风险/费用/止损/选择参数新增、修改、删除均0。期末权益、收益、DD、Sharpe、滑点、交易次数、胜率等真实金融结果全部N/A。没有真实forward观察、真实连续账或未来自动化ready声明。

开始及结束反思：新增寻优过拟合操作为否，原政策历史择题风险仍在；继续补这一窄接线有价值，因为下一步才能诚实区分历史开发观察、及时前瞻决定与数据/状态gap。测试绿色不授权扩大历史预算、救solver、加注或正式生产。用户全市场高质量long→小止损→加注目标仍未实现；本325在final交付后停止，等待root唯一actual授权与328实际结果独审。
