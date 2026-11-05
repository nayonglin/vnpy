# Stage063 复盘开平仓线按各周期所属 K 线对齐

- line_id：`futures_weekly_two_close_momentum`。
- 记录时间：2026-11-05 14:20 上海时间。
- 工作区：`weekly19-stop-reversal.local`。
- 性质：冻结回测展示修复，无新增金融回放，不是重要策略突破，不触发 A/B。

## 外部调研与判断

参考 [Plotly 官方 shapes 文档](https://plotly.com/javascript/shapes/) 与 [Plotly 官方 GitHub](https://github.com/plotly/plotly.js)。形状可绑定各面板的 x 轴，并限制在各面板的纵向范围内。

根因已从实际数据和真实 WebKit 重现：原周 K 按周内交易日坐标均值放在中间，而全图开平仓线沿用日 K 的成交日坐标。纯碱周期 7 的 2022-02-14 日坐标为 528.5，对应周 K 中心为 530.5，所以原线偏在周 K 左侧。判断应按每个周期自己的日期桶定位事件，而不是改动真实成交日或移动 K 线。

## 设计与变更

用户已明确要求各周期开平仓线落在对应 K 线上，采用唯一直接实现：依据各周期原有日期标签确定所属 K 线，事件线和成交三角形放在该 K 线中心。日 K 保留真实交易日；月 K、周 K、10/30 日 K 分别按自己的桶匹配。线及持仓阴影限定在当前价格和成交量面板内。相同 K 线内开平仓保持同一坐标，合并文字，悬浮显示真实起止日。

不使用临近 K 线兜底，没有对应桶则不制造标记。分钟线只有日级成交证据时保留原日级定位，不推断精确成交分钟；本次 167 笔没有可绘制分钟数据。

修复共享 canonical renderer `futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py` 的活动 HTML 渲染函数，保留现有历史修改及 legacy renderer。新增本线 `tools/stage063_aligned_recap.py` 读取并验证冻结 Stage061 记录，再调用 canonical renderer 和原适配器的账本格式化函数。没有复制旧 HTML、Plotly 实现或重建行情。

无策略参数新增、修改、删除，无回测结果改写。新目录保留旧目录，原页面未覆盖。

## 冻结来源及结果

来源为 Stage060 的原 21 品种、20 万元、固定一手、全品种触价止损，2022 年初独立空仓起点。源回测截至 2026-11-04，复盘按 2022 年开仓筛选，保留两笔跨年退出。

| 项目 | 原版与修正版一致 |
| --- | ---: |
| 完整周期 | 167 |
| 盈利 / 亏损 | 52 / 115 |
| 跨年周期 | 2 |
| 完整周期成交笔数 | 360 |
| 完整周期净损益 | +40,080 元 |
| 2022 年账户净损益 | +38,980 元 |
| 2022 年末权益 | 238,980 元 |
| 2022 年账户收益 | +19.49% |

源 summary 中全回测指标不变：期末权益 806,115 元、累计收益 +303.0575%、最大回撤 -52.28502319%、Sharpe 0.91608776、完整交易 1,022 笔、成交 2,376 笔、胜率 30.234834%。成本为源回测原滑点 61,115 元与零手续费。此处没有新增该窗口的金融估计。

新旧内嵌 167 个 record 全量相等，包括所有 OHLC、MA、meta、成交价、日期、利润和缺失披露。summary、chart_manifest、scoped_fills、annual_contributions 逐字节相等。新增 `alignment.csv` 记录五个周期的 1,670 个开平端点，便于追溯显示坐标与真实日期。

## 验证

1. 先写真实 WebKit 回归测试，在旧页得到预期失败：周平仓线应在 530.5，旧线为 528.5。
2. 修复后真实 WebKit 通过：纯碱周入场/出场为 515.5/530.5，日入场/出场为 513.5/528.5，月平仓为 531。全部 1,670 个端点、局部面板范围、成交三角形、同 K 开平、无桶不吸附、周期重排及周单图通过。
3. 真实浏览器的默认 30 日加日 K、52/115 盈亏筛选、前后笔、联动缩放、止损触发日与模拟价格保留通过，控制台错误 0。人工视觉检查纯碱示例截图通过。
4. 两块 JavaScript 由系统 JavaScriptCore 语法检查通过。现有复盘测试 14 项和 Stage061 测试 3 项通过，`git diff --check` 通过。
5. 独立 agent 完成审查，P0/P1/P2/P3 问题均为 0。独立核对 167 条原始 JSON 字节、四份复制文件及内嵌账本不变、父子 manifest 全部通过；1,670 个端点唯一落桶，另从真实日线独立复算 1,336 个聚合周期端点桶中心及 OHLCV，全部一致。JavaScriptCore 执行原始嵌入 JS 的 167×31=5,177 次渲染，覆盖 13,360 面板、26,720 端点、5,424 同 K 面板、10,943 关联事件，全部通过。空筛选、空周期、缺分钟与无所属桶均保持保守。分钟行为仅合成边界检验；真实 WebKit 验收由作者执行，独立证书不冒称重复浏览器验收。

独立证书 `reviews/stage063_alignment_audit.json`，SHA256 `39f6e4327d0a5cb80366c3db0c07ad8639b4144db1b467f91303a8916e97a03b`。

## 输出与身份

新版页面：`research/lines/futures_trend_winner_trade_forensics/outputs/stage063_s21_200k_touch_2022_recap_aligned_v1/index.html`。

旧复盘 manifest SHA256：`d51586ebb2aa6f9c1cc9752f76ab5d5a4053cc97bca2a3f0519110c8f6c59e01`。

原回测 manifest SHA256：`c8bff538f87f7625fa446c4eb710d5e1e8d1d7f05a5b8926ccdee557150d18cf`。

原回测独立审计 SHA256：`a378b07df043792469b5e3f07748ed153d1645c620e4d47b32b321a7f80450bb`。

新版输出 manifest SHA256：`c4e7080e1081798d6cf9f7ee15658c1b6fefb5a34201cd86dbcec5143f8aa173`。

浏览器脚本、结果和截图分别为本线 `reviews/stage063_alignment_browser.js`、`reviews/stage063_browser_result.json`、`reviews/stage063_alignment_browser.png`。

## 运行前后反思

过拟合判断前后均为否：没有调参、筛选或新增策略证据，原研究的历史选择偏差保留。继续价值判断前后均为是：修复周期位置误读，能把交易触发日与所属周 K 对照清楚。

没有策略重跑、行情下载或生产访问。后续复盘使用修订 canonical renderer；已经冻结的其他旧页面不会自动改变。本阶段不更新 registry 和根历史总账。
