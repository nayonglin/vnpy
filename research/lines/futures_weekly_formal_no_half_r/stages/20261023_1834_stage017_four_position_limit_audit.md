# Stage017 最大4持仓限制是否应用及拦截次数

- line_id：futures_weekly_formal_no_half_r；day；记录时间：2026-10-23 18:34（Asia/Shanghai）；重要突破：否；只读既有账本，0策略/金融回放、0下载、0参数变更。
- 对象：K_attempt001关闭MACD三均线为当前用户版本；H_attempt001保留MACD对照，实际账户2020-01-02—2026-10-22。
- 结论：两者实际max_concurrent_positions=4，所有候选effective_max_concurrent_positions也为4；规则实际应用。K有4条最终skip_reason=concurrent_limit，H也4条但候选不同。
- 源码qmt_roll_portfolio_strategy.py:6101按ProductState的非零当前合约计数，并加pending_active_products预留名额；4671及4694/4745在日批量开仓规划时叠加同批已规划开仓，对达到上限的候选设concurrent_limit。所以限制是最多4个品种持仓/预留开仓名额，不是最多4手。

| K信号/评估日 | 品种合约 | 方向 | 当时名额/剩余 |
| --- | --- | --- | --- |
| 2020-07-10 | ru2009.SHFE 橡胶 | 多 | 4 / 0 |
| 2021-02-26 | rb2105.SHFE 螺纹 | 多 | 4 / 0 |
| 2023-09-01 | ru2401.SHFE 橡胶 | 多 | 4 / 0 |
| 2025-03-21 | ru2505.SHFE 橡胶 | 空 | 4 / 0 |

日期是候选信号/规划日，因被拒绝没有实际成交日。K四条selected_volume均正，最终被名额门拒绝，不把sizing_zero_volume误算为持仓上限。

- K候选363=211 opened+152 skipped，最终拒绝原因为空头信号限制96、手数算至0计52、并发上限4。候选日志不等全量raw信号面板；该计数只回答最终明确标为concurrent_limit的候选，不能推算放开上限的反事实净利润。
- K收盘有4个非零合约持仓的交易日22天，最大4、超过4为0；“满仓22天”不等于“拦截22次”，只有出现新候选才会记录拒绝。此处只核收盘快照，不额外宣称逐tick实盘验证。
- H候选351=197 opened+154 skipped，concurrent_limit4条：2020-07-10 ru2009多、2020-11-20 sp2101多、2021-02-26 rb2105多及ru2105多；收盘4仓12天。两版2026年均没有最终并发上限拒绝记录。
- 原始候选、参数和positions源6文件均与Stage015交付SHA一致；明细artifacts/stage017/concurrent_limit_rejections.csv。无新增/修改/删除绩效。
- 独立agent另行只读复核本次计数，结果在交付清单记录。此次纯查询不改LINE/registry，不改旧工具/回测/清单。
- 过拟合判断：本次否，只核已声明规则及固定日志计数，未调参或尝试放宽限制；继续价值：是，可分清实际约束和主要拒绝来源。结束不由4条记录自动发起取消上限实验，不作为收益归因或晋级证据。
