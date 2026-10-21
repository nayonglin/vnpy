# Stage426 成品坏消息到原料的次日开盘后检验

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 19:04 CST。独立于正式C9，沿当前分支；不是重要收益突破。
- 424/425的泛静态投入产出图NO-GO保留。root后来读到国内成品/原料原论文与作者全文，这一证据改变最小source/时段识别的价值判断；不把先前审查写成金融实测失败。
- [出版者](https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22440)及[作者公开全文](https://www.researchgate.net/publication/371550940_The_predictability_of_iron_ore_futures_prices_A_product-material_lead-lag_effect)支持固定RB/HC到I短期坏消息研究，但原样本和close-close/可做空/低费用口径不能证明我们的next-open长侧现金优势。Granger结果也依lag准则，不摘正面摘要下结论。GitHub精确DOI/标题未找到可确认的对应实现，未安装搜索噪声。
- 现在仅一次既有源价格时段诊断，收益前完整机器合同为`outputs/stage426_product_material_timing_protocol/protocol.json`；表内字段、日期、公式、252日块/2000次/seed、之后是否值得训练的门已明确。先固定坏消息负部平均，所有98产品/95family母域保留，只给I适用，不用未来主力或Y选源。
- 分解同一真实合约u收盘到D开盘的gap，以及D开盘到收盘的部分；保留所有未知，控制自身当日收益的partial相关只是描述诊断，不冒充完整52条件alpha或因果效应。2021—2026为论文样本外，仍是本仓库已反复研究的历史，不能称真正未见样本。
- 新增科学项为唯一具名跨品种q和一次固定时段诊断；无原模型、风险、成本、止损、正式策略参数修改。预算0新交易模型/0现金/0API/0SQL/0未来D；一次母体metadata与一次110MB旧cache五成员，不重hash大表。
- 本阶段尚未运行新结果；期末权益、收益、回撤、Sharpe、滑点、成交次数、胜率N/A。过门也只可另立有限金融协议，不能直接晋级、加注或接入已封存前瞻账户。
- 开始新增收益后调参：否；固定独立论文和反证问题，不看成绩选lag/符号。历史多轮择题过拟合风险高，不能抹掉。继续一次有反证力的时段检验：是；泛网络/源资格工程：否。完整原目标active未完成。
