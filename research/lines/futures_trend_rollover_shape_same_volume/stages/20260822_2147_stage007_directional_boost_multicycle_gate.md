# Stage007 A/C/D 多周期资金曲线运行前 Gate Manifest

- line_id：`futures_trend_rollover_shape_same_volume`
- 冻结时间：`2026-08-22 21:47 CST`
- 阶段性质：用户在 Stage006 最小全周期门失败后明确要求补跑多周期；本阶段只做固定格式诊断，不改变 Stage006 失败事实，不自动重开晋级
- 是否重要突破：否；结果尚未生成

## 外部调研与判断

- 时间序列动量研究支持检验过去收益方向与趋势信号的一致性，但不直接支持固定30日或1.2倍。
- backtest overfitting 研究提醒，多次查看结果后增加窗口或选择性汇报会提高研究者自由度；因此本次只允许复用已经固化的半年起点与周期，禁止改参数、删弱窗口或修改 gate。
- 调研判断：补跑有诊断价值，可以判断 D 的高收益/高风险是否跨起点存在；没有参数晋级价值，结果只能加强或削弱否决证据。

## 冻结身份与参数

- A：当前正式 C9/15万，关闭换月形态续仓和30日风险增强。
- C：A + `enable_rollover_shape_same_volume_reopen=True` + `backwards_ratio_continuous` + `shrink_to_allowed`，关闭30日风险增强。
- D：C + `enable_directional_30d_risk_boost=True` + `lookback=30` + `multiplier=1.2`，覆盖普通开仓、反手、换月续仓和三类加仓。
- 资金：`150,000`；数据截止：`2018-01-01 -> 2026-05-29`；手续费、滑点、AI池、品种池、保证金和 broker 口径与 Stage005/006 保持一致。
- 新增参数：无；只组合运行已经冻结的 A/C/D。
- 修改参数：无。
- 删除参数：无。

## 冻结窗口与运行合同

- 完整全周期：共同可用起点至固定截止日。
- 1年、2年、3年：每年1月1日和6月1日分别独立冷启动，不得从全周期曲线切片。
- 完整窗口计票；距离自然终点不超过7天的 terminal near-complete 窗口各周期最多1个，只观察并以 `*` 标注。
- 固定窗口共 `43` 个；1年完整 `15=January 8+June 7`，2年完整 `13=January 7+June 6`，3年完整 `11=January 6+June 5`；三臂共 `129` 次真引擎运行。
- 每个窗口重置引擎、本金、持仓和账户状态，warm-up 只使用点时历史。

## 冻结比较、指标与门

- 窗口比较固定为 `A_vs_C`、`A_vs_D`、`C_vs_D`。
- 每个周期/比较分别输出 `combined`、`january`、`june`，共 `27` 个 aggregate 行；不允许只汇报 combined。
- 每臂记录期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率、账户生存、broker10峰值和超100%天数。
- 完整全周期门：右臂收益不低于左臂、DD恶化 `<=1pp`、Sharpe差 `>=-0.01`、滑点比 `<=105%`、账户生存、broker10峰值及超100%天数均不恶化。
- 每个1/2/3年 × combined/January/June 门：收益胜率 `>=50%`、收益差中位 `>=0`、DD非劣2pp比例 `>=80%`、DD50失败数不增加、Sharpe非劣0.05比例 `>=80%`、滑点比 `<=105%`、全部账户生存、broker100失败数不增加。
- D 必须同时通过 `A_vs_D` 和 `C_vs_D` 的全部完整周期门与27行中属于 D 的18行周期门，才允许 `directional_boost_multicycle_evidence_supports_reopening_review`；否则为 `confirm_directional_boost_not_promotable_after_multicycle`。
- 即使全部通过也只允许重新评审，不自动晋升；Stage006 已失败的事实必须在报告开头说明。

## 固定输出格式

- CSV：window summary、三组逐窗 comparison、combined/January/June aggregate、全部逐日 equity curves。
- JSON：decision、全部预声明窗口和每个 gate 结果。
- 图片固定5张且顺序固定：完整周期、1年、2年、3年、aggregate；所有资金曲线同时显示 A/C/D，颜色和单位保持一致。
- 中文结果必须写入 Stage007 stage 文件，并同步 `LINE.md`、`research/registry.md`、`back_log.md`；若结论改变未来研究政策，再更新 `memory.md`。

## 安全边界与运行前反思

- 不修改正式配置、正式物料、master、production、CTP、订单或撤单链路。
- 运行前过拟合判断：有中等选择性验证风险，因为 Stage006 已失败后才补跑；但本次不改参数、窗口和阈值，并完整汇报 January/June 与弱窗口，可控制新增自由度。
- 运行前继续价值判断：有诊断价值；它可以回答风险恶化是否跨周期和起点稳定存在，但不应被用来为失败参数寻找晋级借口。
