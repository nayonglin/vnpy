# Stage036 两固定历史条件 episode 执行前协议

- 2026-10-20 21:20 CST，line_id=futures_ai_monthly_pool_generalization；非重要突破。此为输入准备，不是已执行的金融结果。
- 固定AU202112@2021-07-30、JM202201@2021-09-30两事件；minute/path/provider均沿既定Stage014/032，不收益择样、不新增下载/源切换。全共同source calendar，第60个后续source日为AU2021-11-02/JM2021-12-30，terminal_mode=mtm。
- 初始qty2诊断，单入场无fresh reentry。只提供D1/D2；其后flat才允许不载bar，若仍持仓必须unknown。target同native不是绕开roll策略。84个精确日键只读含volume，4个AM41历史和日期、RSI6/prevMA20、4个path+SHA首open证据。
- Stage006静态经济按commission_type明确映射per_lot/rate：已知不适用分量结构性0，缺失ratio仍None，historical_validated=False。extra_slippage_price=0显式无额外压力。模型/alpha新增修改删除无；半R/retry仅训练源关、C2保留、正式未改。
- 输出outputs/stage036_real_episode_cases/inputs.json、bindings.json、bound_daily_rows.csv、runner.py、README.md。33项绑定和输入窗口预检通过；CSV推断bool预检空选在driver前fail-fast，dtype=str修复后才准备成功。
- 等root driver测试绿后才运行，之后另写结果与独审；未提前猜数字。本阶段权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A；driver0、fit0、下载0、订单0、生产修改0。
- 调研判断继承Stage010/021/022官方vn.py/GitHub与冻结源码及Stage014/028/032合同；日级request和next-session open fill分离，条件参考轨迹不能等同原账户源或正式交易。
- 开始新增收益选参过拟合否，未扫参、未看driver盈亏；继续价值是，验证持仓早平后仍固定60日成熟钟、费用条件与净值unknown保留。结束判断待实际运行，不能借两点外推收益或模型质量。

## 执行前字段补充

root要求显式区分C2 guard与effective fill tick；当前inputs每个record补c2_guard_tick与Stage014配置来源source_id，取原configured tick而非Stage006经济tick反推。旧准备版仅作pre_guard_v0历史存档，不执行；重新prepare后37项绑定/窗口/guard检查通过，仍未driver运行。
