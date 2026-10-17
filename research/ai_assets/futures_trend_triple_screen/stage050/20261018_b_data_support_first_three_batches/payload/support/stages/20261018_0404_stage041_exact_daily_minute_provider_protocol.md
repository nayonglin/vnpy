# Stage041：实际请求独立日线 reference 的分钟 provider 接合

- line_id：`futures_trend_triple_screen`；2026-10-18 04:04 CST，当前冻结时间以离线preflight为准；不是策略突破版本。原041尚未使用的SM005草稿在本次授权内定稿；原013/037/040、引擎036及035冻结审查资产不改。
- 来源是冻结037正常provider。仅新增由prepare显式传入 `--daily-review-path ABS --daily-review-sha256 SHA` 的独立日线收据来源；没有自动发现、下载新日线或自动信任新source。run/worker禁止这两个flags，必须从packet内已持久化的review路径/SHA及输入指纹再次核验。
- receipt的request digest必须与真实已存在request一致；accepted_target_keys是该request实际requirements的非空唯一子集；qualified_rows、target_rows、CSV、audit、逐key checks行数/身份完全一致。可有多个active order，保留原037每包最多8合约和full/anchor canonical规则。不会提前资格未来日期或理论B上界。
- 必须independent_review=true、reviewer非空、qualified_research_daily=true、P0/P1=0、six_fields_checked=true、actual_raw_forward_successor_checked=true及DB.closeOI=N/A。所有receipt source_fingerprints完整验证并加入packet绑定；CSV/audit/checks本身均须被receipt哈希绑定。
- 每key须全部七值合法，CSV/audit/独立checks真实后继id/time一致，实际source时间落在准确交易日；checks的准确DB六字段与CSV按原容差匹配，DB.open_interest明确映射provider.open_oi。closeOI来自真实已完成日线，DB为N/A。
- 禁止新收据覆盖原始日线CSV、013原有approved或rejected key；即使key在本次其他分包也提前拒绝覆盖。其他target仍走原037日线选择逻辑。
- 当前唯一新增参考为实际 `2175ea018b1e88a029df76629ede0767636baa752ae2e3c04aea4f024bdeb65b`：`au2006.SHFE / 2020-01-08 / full_session / 555`，物理2020-01-07 21:00至Jan8 14:59。独立042日线收据SHA `0b215c102d9d4eaf0da67bf2c17748e1c4ee2ec3b643ddea102f9dc198bad0c8`，来自已绑定013 raw并重新核验精确DB/后继；本地491/459/462目标交集均0，需正常provider。
- 原collector、570秒soft/600秒hard、一attempt、正常鉴权/SDK/端点、父子receipt/输入未改闭环完全沿037。full_session必须完整canonical grid、所有已完成后继、七值聚合；anchor只授原anchor权利，不升级为full。不能用日线价格代替分钟。
- 041不签独立数据receipt、不写engine response。本agent是042日线独立审者，同时实现041，所以不自称对041代码独立review；由root另行审查diff与离线prepare后，root自行运行一次正常网络provider。实际terminal后另做分钟独立签收。
- 策略参数新增/修改/删除=0/0/0，金融结果新增/修改/删除=0/0/0；权益、收益、DD、Sharpe、滑点、交易、胜率均N/A。当前provider尚未网络，金融/模型/订单均0，production=false。
- 过拟合判断：否，只验证实际冻结候选当前请求，不按收益选日期或调参。继续价值：是，保持同一B引擎及原数据资格；缺失或不符则保留失败。
