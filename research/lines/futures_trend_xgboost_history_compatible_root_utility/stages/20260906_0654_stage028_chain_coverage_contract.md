# Stage028 合约链逐日覆盖与决策前资格合同

- 时间：2026-09-06 06:54 CST；line_id：futures_trend_xgboost_history_compatible_root_utility。
- 类型：来源资格；现有流程有限扩展，不是重要突破、不是模型或回测。用户已授权持续研究，无重复审批及reviewer。
- 输入冻结：Stage027原生源summary SHA 1cc361ac370fa3d300eaa86d51ac9f151d063b0c7668242e426d7067192969c4及全部输出；Stage026目录；原276事件身份；原A daily仅date列；旧冻结只读数据库仅DISTINCT日线日期，SHA a683e8d99c1925ef2af546e62b61f62c9946d21ea4e5be4af42737a80f77eef5。
- 原A完整2020-01-02至2026-08-28/1614日不变，源2019-11-01至2026-08-28。数据库日历1657日（含43暖启动日），需与完整A区间日期精确一致。数据库绝不写入。
- 首次观察日不是上市日。给每个已在历史出现的合约，从首次观察日到元数据到期日/截止日逐交易日检查原始日线是否真实存在；不以未来最后一条数据提前缩短预期寿命，不前填/后填/补零。后续才出现的合约不能进入过去已观察集合。
- 逐品种逐日保存应有/实际合约数、缺口数、已观察合约的总close_oi及正持仓合约数。已观察合约无缺口且总close_oi>0才为该日的完整观察链；尚无合约的历史明确标为not_yet_observed，不等于零持仓，不宣称真实当日上市全集。
- 决策覆盖固定为每个事件严格之前6个完整交易日，供未来固定5日迁移差使用；这是事前时间尺度，不根据盈亏选窗。6天链快照须完整，原实际合约6天均有真实记录、产品与到期关系正确；全部276事件保留，失败列明，不删事件或降门。
- 另保存完整A日历×18品种的源窗口状态，未上市/尚无观察历史单列；不给尚无交易可能的历史假造信息。当前C新状态可能需要的实际合约仍需运行时严格检验，不靠A事件全部合格代替。
- 本阶段只读身份、时间、合约、volume/open_oi/close_oi。不读取新的收益/回撤关联、不生成模型特征数值、不读训练标签，不fit/predict/策略回测。先合成反例TDD，再唯一执行并独立复算。
- 通过只允许预注册迁移特征，不能证明alpha、PIT原始发布版本或历史上市全集；若缺口使事件不可用，保留完整失败结果，不救参。
- 调研：CME Pace of the Roll说明OI在合约间迁移的经济含义；QuantConnect futures history文档与GitHub的逐合约OI格式支持区分真实合约和连续映射。https://www.cmegroup.com/trading/paceoftheroll/user-guide.html 、https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/asset-classes/futures 、https://github.com/QuantConnect/Lean/blob/master/Data/future/readme.md 。不从美国合约的描述推断中国商品存在相同alpha。
- 开始过拟合判断：否，本阶段只作完整来源检查；整体历史反复研究仍有选择偏差。继续价值：是，模型前先验证新增信息能否实际取得；不把接口返回成功当有效特征。
