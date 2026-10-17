# Stage063：原 B 真实旧值冲突失败

- line_id：futures_trend_triple_screen；记录时间：2026-10-18 05:46 CST。重要策略突破：否；重要实际失败证据：是。分支仍codex/ai-training-data-expansion。
- 原B session70433/PID21822真实exit1；数据session43111真实exit1。工具终态分别为chunk ccfb06/4981c3，不以静态lock、预测超时或driver暂停推断结束。
- 开始2026-10-18 03:47:59.193786+08:00，失败2026-10-18 05:44:11.775177+08:00，真实墙时6972.581391秒，其中记录的数据等待合计6678.624223秒。失败时尚未到原7200秒期限，原因是2022-05-31 fu2209.SHFE full_session在021 actual append前发生qualified_delivery_old_value_conflict，旧保护拒绝覆盖；不是模型PIT发现或运行超时引起。
- 末request191 digest 6873f0a1930106a91bb35355efbf2e9843ddcd9f05aa3ebf1ebf105806ab3730，052 local交付345分钟，resolver已接收独立签收但021 gate失败。前者不等于追加成功，末包禁止进入已accepted复用集合。具体字段与来源另做只读定位，不覆盖原数据/收据。
- 原raw_checkpoint=None、validation_seal=false、summary不存在，只有部分执行/等待审计。完整期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率全部N/A，不能以部分曲线补造。金融attempt累计仍8、独立完整验账仍3，原B第1次失败；没有新模型训练或重跑。
- 新增/修改/删除策略参数和已接受金融结果均0。057/058两项历史模型资格P1另行保留，不是本次实际数据冲突的归因。
- 真实terminal：outputs/stage063_b_ts_actual_failure/actual_tool_terminal.json，SHA 8f556fb6b76c27f28db7ff7799643bda5c7e934c844a29546545efe10d21981b；run_failure SHA f39f9d60b3e975263b0ee9411b70b766a9a8c4a3f12d068b9c35650888928536。有限独立失败审计交064，061复用合同只继承真正021 appended且old_keys_changed0的先前子集；062未来OFF入口须先解决已证实冲突及复用层，不能仅重跑/改budget。
- 运行前后新增过拟合判断：否，原冻结机制未根据途中盈亏改变；原模型历史资格与研究选择风险保留。继续价值：先定位实际冲突与复用已验数据有价值；直接重跑原B无价值。目标仍完整2020—2026更高收益且更低回撤，尚未达到。production_qualified=false，无push/部署/CTP/订单。
