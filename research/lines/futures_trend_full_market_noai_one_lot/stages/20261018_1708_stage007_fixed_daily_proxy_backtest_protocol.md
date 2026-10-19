# Stage007 日线近似单次全周期回测协议

- 时间：2026-10-18 17:08 CST；line_id=`futures_trend_full_market_noai_one_lot`。不是重要突破，结果尚未产生。
- 用户授权：独立master研究工作树；100万、无AI、全部空头case、全市场每品种1手不加仓；缺分钟先做日线近似并明确停用C2/C9；供需冻结CSV缺失亦明确允许停用并披露。
- 版本：Stage037/m0008正式物料上的独立研究delta，原策略代码未改；`codex/full-market-noai-one-lot`起点e41a0a01d53b7256001e45e686acad53667ef7bf。
- 新增/修改参数：本金/account/c3=1000000，fixed_size=min/max_position_size=1，AI月池/pairwise全部false，加仓false，多空case1a/2/3可入场；日线近似C2/C9 flags false，供需filter false。
- 保留：Stage037形态过滤、目标合约历史、五日换月延迟、完整profile保证金/相关性/集中度/退出风控，最大同时持仓仍4。
- 数据：六所93历史品种，809279真实日线，2014预热，2015-01-01开始交易分析，2026-10-16截止。前一源日历日OI/V主力，不使用当日量仓；静态条款非历史逐日PIT。
- 命令：`PYTHONPATH="$PWD" .py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage004_run.py --mode daily-proxy --supply-policy disabled-research --output research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261018_daily_proxy_v1`。
- 预声明观察指标：期末权益、总收益、最大回撤、Sharpe、手续费/滑点、总成交/完整episode/胜率、年度净值路径；账户账本与策略权益误差<=1e-5，所有成交1手、每品种持仓<=1手、无陈旧bar成交、完整回放至固定截止。
- 结论资格：仅本研究政策的单窗口描述，A正式基线未重跑、B无独立模块；不做正式晋级、不能宣称较正式版更优或OOS穿越周期已证明。研究有价值不等于候选已通过。
- 当前真实金融启动1次，尚在运行；新增/修改/删除完成结果0，权益/收益/DD/Sharpe/滑点/成交/胜率均待运行。运行失败也留原包/日志，不覆盖。
- 开始过拟合判断：否，固定整体政策，不按收益救参。继续价值：是，能观察无AI全空头case一手的全周期行为；不得把近似结果冒充完整C9。
- 后续：每次完整回测后新独立agent审查，再冻结结果生成规范复盘并浏览器验证。
