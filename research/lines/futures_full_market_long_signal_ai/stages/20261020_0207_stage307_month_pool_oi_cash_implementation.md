# Stage307：OI份额候选四现金适配实现

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 02:07 CST。非重要突破，当前只实施，无新actual。
- 新增工具`stage307_month_pool_oi_cash.py`及单项身份fixture。最小复制已接受297，仅修改304协议/306新源选择/307输出/CANDIDATE身份与对应schema；原157/131/070/042核、预算、风险、成本、choice/domain/先因果预留、统计及CI完全不改。
- 新fixture先RED因适配器缺失，再GREEN1case/.284s；未跑旧297 suite、未加载行情/模型/启动现金。代码SHA `c043d300e1610b616688973458386547a4cffb61924a10b1b817ecc306679daa`；testSHA `7e1a30ad34be9cfc55d7bfdf7812fc9a6cc52357f86bb2632bd55a3d2014405a`。
- 冻结304，100万、2020连续/2023空仓、base/stress，最多4候选cash，0旧控制重放/fit/SQL。只有306完成且main执行变化/308预审后root精确授权才actual；无动作变化走独审等价skip，不以heldR符号跳过。
- 完整source_bundle与未授权模板在`outputs/stage307_month_pool_oi_cash/`。当前actual0、累计447fit/242cash；权益/收益/DD/Sharpe/滑点/交易/胜率N/A，旧参数及回测结果修改删除0。
- 外部依据沿302/304的OI期限结构先验；本适配器本身不产生alpha证据。开始/结束新增按成绩调参否，历史择题风险是；复用已验核并做一个身份边界有价值，重复旧金融/小测试无价值。完整目标active，未签PIT/正式/加注资格，不改其他线或生产。
