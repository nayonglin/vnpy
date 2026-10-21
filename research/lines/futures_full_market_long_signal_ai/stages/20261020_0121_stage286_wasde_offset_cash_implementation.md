# Stage286：WASDE单项offset的新候选现金薄封装，未实际跑账

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:21 CST；非重要突破、仅实现。本阶段新增fit/cash/SQL/网络/旧测试/大数据读取=**0**；284事前累计439fit/238cash，285后续实际fit另记，不在本阶段重复计数。
- 先读registry、279 stage/refs及284全文；复用279已闭包接口，不重做94依赖盘点或旧大hash。外部调研复用279/284及283审查，不新增网络。

## 固定身份和实现

284 protocol SHA `b604940cf2d43fa504883796a8532a734101a7d2291d7fee225296c384e39193`；technical_clarifications SHA `b67e22d679d375d5f4eddd66d53e458a6dcdca2240f2366bcaf575baedc1580f`。新增[286源码](../tools/stage286_wasde_offset_cash.py)及[新边界fixture](../tools/test_stage286_wasde_offset_cash.py)，外部候选身份统一为`WASDE_PUBLICATION_MONTH_OFFSET`。不改任何旧source/kernel、LINE/registry/他线或生产。

285接口已与作者直接对齐：manifest schema=`stage285_wasde_offset_fit_select_manifest_v1`、status completed、protocol_sha256及candidate；`artifacts.choices_main`为完整161014 main父行，`artifacts.boundaries.epochs`沿156 K结构，`inputs.mothers/actions`沿129。完整父身份和顺序逐列校验；仅私有choices副本alias `VOLUNTARY_RESELECT`供157 helper，原外部身份不改。

**全部新selected IDs**从129.actions一次gzip流读原16 ACTION_FIELDS；新正分动作可以在旧4365以外，不能用266过滤器或旧signals限制入场域。一次流覆盖1552456动作，拒绝缺失/重复选中ID；完整399252母表用于canonical。随后157.make_voluntary_signals重建选中信号/原K与有效边界 → 131.organize → 原131kernel。132 cache仅恢复一次、SQL0；原100万/0.25N、0.0025 family/0.02总risk、0.25 margin/1.1buffer、容量/费用/tick/退出均不改。冻结大输入只继承绑定并stat，无额外预hash；原cache restore自身精确读取校验仍沿用。

固定只开2020连续/2023冷启×base/stress四候选；原157四控制summary/daily/诊断只引用不重放。每本在原核调用前记started、返回后记completed，fresh输出禁止覆盖；partial失败保留progress/terminal/manifest及已完成账本，不自动重试。输出完整原账本、候选summary、未知/容量/拒绝、费用/滑点金额与可计算tick-lot、closed根胜率/closed根数/fills/数量不同口径、年指标与配对差、family-year含零及原sector归因。

统计严格沿284和technical：调用旧148.paired_statistics，真实口径为mean daily log-growth差；原070两份2000/block252 indices只读复用，不新seed/window/CI。逐年列候选/控制收益、增长金额、DD及配对差，2026截至10-16标partial。唯一名义门是两stress各自期末权益更高且DD更浅，四谓词全真；缺指标或等于0不通过，base不进门。CI及日行不能冒充独立USDA报告证据；名义通过也无PIT/held泛化/alpha/晋级或goal证明。

## TDD证据与交接

按既读TDD/writing-plans技能先写两项新fixture，缺实现时两项明确FAIL；最终 **2/2 GREEN，0.018s，exit0**。测试仅新边界与合成callbacks：新ID全集/一次流、完整父行/canonical/私有alias；四账户启动完成/失败保留/fresh拒绝，四谓词及年度配对差。未import旧金融核、未跑旧suite；CLI help通过，未执行actual。

| 新文件 | bytes | SHA256 |
| --- | ---: | --- |
| stage286_wasde_offset_cash.py | 20916 | 8a1612d715e1ce9d79ed16c905124f376c9a6506987f34d9db118493f0c94665 |
| test_stage286_wasde_offset_cash.py | 5044 | 59dfc2916415df4ef8432920d29739c0124b95723850098c5cfb48d09cc44690 |

[implementation目录](../outputs/stage286_wasde_offset_cash/implementation/)含计划、RED/GREEN、source bindings及单root授权模板。授权schema=`stage286_exact_root_authorization_v1`，必填`authorized_by/root,protocol_sha256,output,max_new_candidate_cash=4,max_new_fit=0,source_bundle,technical_clarifications,interface_refs,fit_select_manifest`；最后者等285实际完成后填准确manifest binding。本实现授权为0actual，实际执行仍由root另发精确临时授权；这是研究身份门，不是生产资格。

准确CLI（未执行）：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage286_wasde_offset_cash.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage284_wasde_offset_protocol/protocol.json --protocol-sha256 b604940cf2d43fa504883796a8532a734101a7d2291d7fee225296c384e39193 --authorization <filled.json> --authorization-sha256 <filled_SHA> --output research/lines/futures_full_market_long_signal_ai/outputs/stage286_wasde_offset_cash/actual_run1
```

开始/结束新增按成绩调参过拟合：**否**，仅兑现收益前冻结协议，没有读本候选金融成绩；长期同史择题风险**是**。继续价值：**是，仅待新源/实现独审后一次有界实际证伪**，不值得重跑旧控制或扫描符号/窗口/风险。参数和金融结果新增/修改/删除0，权益/收益/DD/Sharpe/滑点/交易数/胜率本阶段全N/A；实际金融批次后仍须独立agent审结果/数据/逻辑/置信度/bug。
