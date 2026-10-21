# Stage007 月末原始输入矩阵：实际运行前范围

- line_id：futures_ai_monthly_pool_generalization；day；2026-10-20 19:01 CST。
- 用户补充授权：仅本次全市场AI训练源关闭0.5R。独立profile为`config/training_source_v1.json`，唯一覆盖`enable_stage847_half_r_stop_retry=False`，同时禁用依赖的retry；原始正式配置不改。C2仍独立依赖分钟路径，不能因关0.5R声称整个源成为日线等价。
- 本轮先生成无收益输入矩阵，不执行金融回放、模型拟合或正式A/C；不声称产出经济标签。

## 结果前固定

1. 沿用2010-01—2026-09完成月和98个metadata产品域。以当月末可观察真实合约正成交量最大、收盘持仓最大、epoch字典序选研究代表。未来是否有行情不参与选择；全部产品月保留，缺失记unknown。
2. 从Stage266已验收clean库读取代表同一epoch历史，要求当时及前40个继承日历交易日都有真实OHLCV/closeOI，禁止跨合约拼价或用旧bar凑41。日历仍是共同来源代理，不冒称逐交易所历史PIT。
3. 冻结m0008文件逐字节SHA校验后AST抽取信号及硬阻方法。严格AM41，RSI6直接TA-Lib，MACD在41根上重新算；影线、MA5和shock/range参数从Stage005合同绑定，不扫描阈值。
4. 保留raw signal与fresh方向资格之别：raw空case2/3不删除，但fresh空只允许case1a；硬阻状态单列，不以缺ATR默认通过。RSI非有限时输入unknown。
5. 产物为月末覆盖/确定性原始特征，不是原108输入表，也不是未来60日经济标签。月度三窗口的策略轨迹统计尚未生成，不拿本矩阵直接fit或补0喂给旧模型。
6. 原始候选资格不读未来，暂无标签不做排名；从完整可见宇宙定义标签的前置合同仍然成立。

## 验证与边界

- 实际前已跑7项小测试通过：profile仅关半R/重试、不改base及C2，代表选择不读未来、tie确定、严格41源日缺口/重复/非法价拒绝。首合成adapter probe发现shock字典键不一致，真实数据运行前更正并加冻结方法整合回归；不计作金融重跑。
- 实际后独立agent核矩阵行域、代表选择、窗口、源hash、参数与一组确定性信号；不得把数量当收益有效性。
- 本轮不增加资金参数；金融指标全N/A。只有观察覆盖计数和输入质量状态。
- 过拟合：无新增按收益选参，但代表选择/新来源仍是研究自由度，须固定。继续价值：是，先证实全市场可构造同口径确定性输入，再审查收益源。

## 调研与判断

- AQR长期趋势研究支持跨市场/跨周期检验这一方法方向，不证明本模型有效：[原研究说明](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)。
- vnpy官方撮合与on_bars顺序说明频率属于执行语义，故本轮只复用确定性信号：[官方源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。
- sklearn官方泄漏说明支持在真实训练时隔离预处理与训练测试：[官方文档](https://scikit-learn.org/stable/common_pitfalls.html)。本轮无训练，不提前签泛化结论。
