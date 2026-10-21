# Stage497：具名会员身份 B/C 八本现金账接口准备

- line_id：`futures_full_market_long_signal_ai`。
- 时间：2026-10-21 01:44 CST；当前模式 day；当前分支 `codex/ai-training-data-expansion`。
- 性质：已研究方案的执行接口实现；不是重要突破。仅本阶段新文件，无正式版、生产、其他研究线、LINE/registry 或旧源码改动。
- actual 授权：**未取得**。本阶段真实训练、真实现金账、缓存恢复、SQL、行情及旧账读取全部为 0。

## 调研与判断

本阶段不另开择题或数据获取，承接 493 对现存具名会员向量与 494 对身份信息的科学审视，再由 root495 冻结最终科学合同。会员是经纪会员或其客户汇总，不能称为末端投资者或“聪明资金”；披露缺席不代表真实持仓为零，名称连续也不代表法律身份连续。这里实现的现金账户比较不能改变这些来源解释限制。

现金层直接复用接受过独审的 Stage491 纯读写、汇总、配对统计、经济门槛工具，以及 Stage157/131 原执行核；没有为新会员包另造撮合、风险或交易成本规则。Stage491 的 FOMC 臂、协议和 actual 入口没有被调用，也没有修改其模块全局值。

## 本次变更及参数

- 新增 `tools/stage497_member_identity_cash.py`、`tools/test_stage497_member_identity_cash.py` 和 `outputs/stage497_member_identity_cash/implementation_binding.json`。
- 新外部标识为 `B_MEMBER_AVAILABILITY` / `C_MEMBER_IDENTITY`；内部仅使用旧核原 `NARROW/VOLUNTARY_RESELECT` schema。
- 新增策略参数 0、修改参数 0、删除参数 0。root495 的最终协议 SHA、root 精确授权 SHA 和完成496 handoff SHA 均由 CLI 明确传入，未猜测或硬编码尚未冻结的数值。
- 继承本金 100 万、0.25N 初损、20low、同源共同 K、单 family 0.25% 风险、总风险 2%、缓冲保证金上限 25%、margin buffer 1.1、成交参与率 1%、原费用/滑点/容量及未知处理。

拟最多 8 本新账：B/C × 2020 连续/2023 独立冷启动 × base/stress。连续账户不按年度重置，冷启动仅在既定2023起点建立。全六所98目录产品/95family、161014 forward 母体均保留；外部源只覆盖部分交易所时，未覆盖域的回退由496冻结，现金层不得删去。

只读496新派生七身份母表、两份完整 main choices、966740行16字段因果 action 的 selected union；不重读原129未来结果、母表、COMMON 或原 score。缓存最多恢复一次，原行情SQL 0。未被选中的不合格 action 仍保留在完整派生源中，不把旧157所选合约当新政策入场域。

A 明确为157自身四本 `NARROW_VOLUNTARY_RESELECT_*` 账户，不能使用其 `baseline_references` 中的131B。A只读原summary/daily/diagnostics及全family年贡献，旧A回放0。

每本现金核成功返回后立即保存独立压缩 raw-book checkpoint，并记录 started/completed 计数；八本完成后才导出报告。报告失败、后续核失败都保留原目录和已完成账本，不自动重试现金核，防止报告修复被算作重新回测。

## 输出与经济判断

计划输出八本新账的全部账簿、原A四本只读比较、权益/收益/回撤/Sharpe、费用与滑点、成交笔数/数量、闭合根数与净胜率、历史 stale、entry/capacity unknown、年度和完整95family含零归因、12组配对比较以及尾部贡献。

bootstrap 复用既定原索引，252源日块、2000次，不另抽seed。C−B与C−A均需原严格主stress收益/DD和CI门及其余三个账户不反向；B−A仅披露。两个family held诊断从496继承，未知不填0。通过历史名义门也不等于独立泛化、真实历史首发/PIT、因果识别或加注资格；极窄初损不能限制跳空损失。

截至2025对照只截取同一本连续账的日权益；不是新增账户，不清仓、不返本、不按年重置。

## 合成验证

四项新合成边界先观察到4个“缺实现”断言红灯，再实现后4项通过；最后一次命令 `.py311/bin/python -m unittest research.lines.futures_full_market_long_signal_ai.tools.test_stage497_member_identity_cash`，0.032秒，exit 0。

覆盖完整母身份/缺失域保留、新身份臂与旧宏观臂隔离、16字段未来结果拒绝和selected union、C−B/C−A双门与held未知、同账2025截面、八次合成回调后报告失败及第三个合成回调失败的checkpoint/no-retry。回调只返回小字典，没有调用任何真实现金核。没有运行庞大旧测试套件或原金融数据验证，避免把局部验证冒充全包实际通过。

源码精确绑定：自身 25068B / SHA `7e0f6fc4f67bb8d733a5200f5d56e6b0d112185cba8390540146a81e7aa1c89f`；测试 6853B / SHA `a6df7c22f8ee72250a2a10c86fd4553fd20befbed330c7d5ae51782f21badac5`；原491 helper 32281B / SHA `c97983509f726a89bb63f87ca67c69fd3c104bf4491c34100ffe35ae7aca5f35`。精确CLI、authorization与handoff字段合同见 implementation_binding。

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均 **N/A，尚未实际回测**。新增/修改/删除回测结果均0。

## 反思与下一步

- 运行前过拟合：本次没有按成绩调参；整条历史反复择题风险高，因此不能把新包装或来源字段等同新优势。
- 运行后过拟合：判断不变；合成接口通过不是收益证据，不提高下注。
- 运行前继续价值：有条件有；一次明确分离来源可得性与身份信息的冻结实验，可直接证伪身份增量。
- 运行后继续价值：有条件有；等root495冻结、496完成与root精确授权后，最多一次八本现金账，再由独立agent审查。未取得授权前不读取实际大输入或启动任何真实账。
- 本阶段完成不代表整体目标已达到；尚无新的更高收益/更低回撤、全市场高质量做多或窄损加注资格。根 memory/back_log 不追加。
