# Stage789 两个新 AI 池统一接入 Stage777 年度多起点验证

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-10 17:33 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage777 固定 target 的 AI 产品池交叉验证
- 是否重要突破：否，但补齐 Stage788 的关键缺口：两个新老师池是否能统一接入 Stage777。
- 是否触发A/B：是。AI 产品池可能成为 Stage777/正式候选 selector，已按 A/B 纪律固定 target 和两个预声明池，不扫参数。

## 外部调研与判断

- 参考资料：
  - scikit-learn `TimeSeriesSplit` 官方文档：`https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html`
  - vn.py `ArrayManager` GitHub 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
- 我的判断：
  - 时间序列 AI 选品必须保持 point-in-time，不能把未来月度池倒灌回历史。
  - 本次实验只允许把 Stage788 已生成的两个 PIT AI 池接到同一个 Stage777 target，不允许继续扫 topN、OI 倍率、AM 根数、训练窗或标签 horizon。
  - `AM41` 是为解决早期老师样本覆盖的结构口径，不是正式参数晋级。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage789_stage777_cross_teacher_ai_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE789_MAX_WORKERS`，默认 `4`
  - 三个回测臂：`ai_off`、`ai_pool_am41_no_oi_teacher`、`ai_pool_am41_oi08_teacher`
- 修改参数：
  - 固定 target：Stage777，50万、`AM41`、基础等效风险 `0.40`、命中可交易 `OI上升 + 价格沿方向` 后恢复到 `0.80`、关闭连败缩放、关闭 recovery sleeve。
  - 两个 AI-on 臂只替换 `ai_product_pool_eligibility_path`，分别使用 Stage788 `am41_no_oi` 老师池和 Stage788 `am41_oi08` 老师池。
- 删除参数：无

## 回测参数

- 年度起点：`2018-01`、`2019-01`、`2020-01`、`2021-01`、`2022-01`、`2023-01`、`2024-01`、`2025-01`、`2026-01`
- 统一终点：`2026-05-29`
- 总回测数：`27`
- 对比口径：每个年度起点中，两个 AI-on 池分别对比同一起点的 Stage777 `AI-off`
- 成本口径：正常成本并输出 cost stress 文件

## 年度明细

| AI池 | 起点 | AI-on收益 | AI-off收益 | 收益差 | AI-on回撤 | AI-off回撤 | 回撤差 | Sharpe差 | 交易数差 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `am41_no_oi` 老师池 | 2018-01 | `106.735%` | `711.085%` | `-604.350pp` | `-38.2263%` | `-56.6345%` | `+18.4082pp` | `-0.4159` | `-493` |
| `am41_no_oi` 老师池 | 2019-01 | `97.363%` | `848.035%` | `-750.672pp` | `-35.8801%` | `-56.9794%` | `+21.0993pp` | `-0.5099` | `-465` |
| `am41_no_oi` 老师池 | 2020-01 | `38.863%` | `400.381%` | `-361.518pp` | `-32.0701%` | `-56.2669%` | `+24.1969pp` | `-0.5250` | `-421` |
| `am41_no_oi` 老师池 | 2021-01 | `47.513%` | `52.160%` | `-4.647pp` | `-32.5610%` | `-58.9291%` | `+26.3682pp` | `+0.0323` | `-330` |
| `am41_no_oi` 老师池 | 2022-01 | `-4.133%` | `-40.313%` | `+36.180pp` | `-39.5536%` | `-62.9700%` | `+23.4164pp` | `+0.3267` | `-227` |
| `am41_no_oi` 老师池 | 2023-01 | `20.584%` | `25.147%` | `-4.563pp` | `-25.8237%` | `-35.2992%` | `+9.4756pp` | `+0.0189` | `-193` |
| `am41_no_oi` 老师池 | 2024-01 | `29.745%` | `21.066%` | `+8.679pp` | `-23.4682%` | `-36.3080%` | `+12.8398pp` | `+0.2594` | `-141` |
| `am41_no_oi` 老师池 | 2025-01 | `6.235%` | `43.088%` | `-36.853pp` | `-18.4670%` | `-21.2259%` | `+2.7588pp` | `-0.5988` | `-79` |
| `am41_no_oi` 老师池 | 2026-01 | `-8.336%` | `-14.752%` | `+6.416pp` | `-17.5460%` | `-19.4208%` | `+1.8747pp` | `+0.0916` | `-28` |
| `am41_oi08` 老师池 | 2018-01 | `97.411%` | `711.085%` | `-613.674pp` | `-49.1885%` | `-56.6345%` | `+7.4460pp` | `-0.4859` | `-498` |
| `am41_oi08` 老师池 | 2019-01 | `73.312%` | `848.035%` | `-774.723pp` | `-50.5249%` | `-56.9794%` | `+6.4545pp` | `-0.6248` | `-467` |
| `am41_oi08` 老师池 | 2020-01 | `35.034%` | `400.381%` | `-365.347pp` | `-46.0661%` | `-56.2669%` | `+10.2009pp` | `-0.5616` | `-419` |
| `am41_oi08` 老师池 | 2021-01 | `328.650%` | `52.160%` | `+276.490pp` | `-42.8698%` | `-58.9291%` | `+16.0593pp` | `+0.6310` | `-318` |
| `am41_oi08` 老师池 | 2022-01 | `43.262%` | `-40.313%` | `+83.575pp` | `-44.3335%` | `-62.9700%` | `+18.6365pp` | `+0.7170` | `-233` |
| `am41_oi08` 老师池 | 2023-01 | `73.263%` | `25.147%` | `+48.116pp` | `-22.3583%` | `-35.2992%` | `+12.9409pp` | `+0.5416` | `-194` |
| `am41_oi08` 老师池 | 2024-01 | `102.828%` | `21.066%` | `+81.762pp` | `-17.7290%` | `-36.3080%` | `+18.5790pp` | `+0.9612` | `-136` |
| `am41_oi08` 老师池 | 2025-01 | `67.731%` | `43.088%` | `+24.643pp` | `-17.8553%` | `-21.2259%` | `+3.3706pp` | `+0.5422` | `-80` |
| `am41_oi08` 老师池 | 2026-01 | `-4.640%` | `-14.752%` | `+10.112pp` | `-13.2675%` | `-19.4208%` | `+6.1533pp` | `+0.3818` | `-30` |

## 聚合结果

- `am41_no_oi` 老师池：
  - 全部样本：收益胜出 `3/9`，回撤胜出 `9/9`，双胜 `3/9`，收益差中位 `-4.647pp`，回撤差中位 `+18.4082pp`，交易数中位 `-227`。
  - 成熟样本：收益胜出 `2/8`，回撤胜出 `8/8`，双胜 `2/8`，收益差中位 `-20.750pp`，回撤差中位 `+19.7537pp`，交易数中位 `-278.5`，DD50 失败 `0`。
- `am41_oi08` 老师池：
  - 全部样本：收益胜出 `6/9`，回撤胜出 `9/9`，双胜 `6/9`，收益差中位 `+24.643pp`，回撤差中位 `+10.2009pp`，交易数中位 `-233`。
  - 成熟样本：收益胜出 `5/8`，回撤胜出 `8/8`，双胜 `5/8`，收益差中位 `+36.3795pp`，回撤差中位 `+11.5709pp`，交易数中位 `-275.5`，但 DD50 失败 `1`。

## 输出

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_report_stage789_stage777_cross_teacher_ai_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_summary_stage789_stage777_cross_teacher_ai_yearly_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_cost_stress_stage789_stage777_cross_teacher_ai_yearly_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_curves_stage789_stage777_cross_teacher_ai_yearly_v1.csv`
- comparison_detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_comparison_detail_stage789_stage777_cross_teacher_ai_yearly_v1.csv`
- comparison_aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_comparison_aggregate_stage789_stage777_cross_teacher_ai_yearly_v1.csv`
- comparison_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_comparison_chart_stage789_stage777_cross_teacher_ai_yearly_v1.png`
- equity_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_equity_selected_stage789_stage777_cross_teacher_ai_yearly_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage789_stage777_cross_teacher_ai_yearly_decision_stage789_stage777_cross_teacher_ai_yearly_v1.json`

## 结论

- 可以接到 Stage777 跑年度多周期，Stage789 已完成。
- `am41_no_oi` 老师池不晋级：它是强防守 selector，回撤全胜，但成熟样本收益胜出只有 `2/8`，收益差中位为负，明显砍掉早期复利右尾。
- `am41_oi08` 老师池不晋级：后期收益和 Sharpe 明显更好，但 2019 起点 `AI-on` 最大回撤 `-50.5249%`，触发 DD50 硬失败；它仍继承 OI 单因子高回撤属性。
- Stage777 `AI-off` 本身是高收益高回撤右尾版本，两个 AI 池都显著降交易密度和改善回撤；问题在于一个防守太重，一个仍有生存线失败。
- 不替换正式 AI，不把两者接入正式候选；若继续，只做 AI 拦截样本归因，确认到底砍掉了哪些早期右尾和哪些坏路径。

## 反思

- 运行前过拟合反思：中等风险。两个池来自前序 AM41/OI 研究，但本次固定 Stage777 target，只测两个预声明 PIT 池，没有扫参数。
- 运行后过拟合反思：继续调 topN、OI 倍率、AM、训练窗或标签 horizon 去救其中一个池，会变成过拟合。年度结果已经足够说明结构性冲突。
- 运行前继续价值：有，补齐 Stage788 没有统一接 Stage777 的缺口。
- 运行后继续价值：作为交易候选价值不足；作为 AI 拦截归因和防守型 selector 诊断仍有价值。

## TODO

- 不做参数救援。
- 若继续，做 `AI-off -> AI-on` 被拦截交易逐笔归因：年份、品种、方向、case、OI命中、理论收益率/R 倍数、是否早期右尾。
