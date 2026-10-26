# Stage031 canonical逐笔复盘构建记录

- 时间：2026-10-26T22:10+08:00；研究线：futures_weekly_formal_no_half_r。
- 重要突破：否；性质：冻结逐笔可视化，不增加金融回测成绩，不构成晋级证据。
- 依照 futures-recap-html Skill，未改canonical源及其他研究线。AST只执行原始纯函数 `_records` / `_html` / 原聚合与窗口函数，不导入其策略/Tq模块；完整canonical SHA：`613672a4cc91493ba17dc055542e4b4172349de210ff932530caf04ce36bb93a`。
- 冻结源HEAD：`59e58f271df58451869c9da3d66f0de750f3b013`。W=outputs/stage030_weekly_attempt001；B=outputs/R_attempt003；日线只读Stage029 data_approved/daily.sqlite及physical_epoch_daily.csv。25个使用源前后SHA不变。
- 原参数新增/修改/删除均0；新增展示参数只有 `?episode=BACKTESTING.N`，按原开仓ID定位。价格涨跌为加权退出/加权入场−1的原始标的涨跌，未方向调整，不能当账户收益；无确切R一律null/N/A。

## 冻结成绩引用（并非本次新增回测）

| 指标 | W周收5%半仓 | B不加5%止盈 |
|---|---:|---:|
| 初始资金 | 150000 | 150000 |
| 期末权益 | 2004940 | 3481370 |
| 总收益 | 1236.6266667% | 2220.9133333% |
| 最大回撤 | -60.6024117% | -56.3121726% |
| Sharpe | 0.8060655984 | 0.8805923398 |
| 总滑点 | 128990 | 254060 |
| 手续费 | 0 | 0 |
| fill笔数（非往返轮） | 785 | 723 |
| 完整已平native轮 | 349 | 355 |
| 完整轮胜率 | 44.9856734% | 44.2253521% |
| 平均盈利/平均亏损 | 23981.8153 / 13353.4817 | 45328.0892 / 25890.9137 |
| Payoff | 1.7959223 | 1.7507335 |
| Profit Factor | 1.4762293 | 1.3952546 |
| 完整轮净损益 | 1214630 | 2016000 |
| 末未闭合轮/纯余仓净MTM | 4 / 470750 | 4 / 1315370 |

## 可视化边界与交付

- W349+B355=704已平轮全部展示；W盈利157/亏损191/平1，B157/197/1。W81、B9个真实非最终平仓marker；这是全部partial fills，不等同74个5%触发。W原reason包含short_profit5_half19/long_profit5_half47/forced_margin_deleverage15；Bforced9。不能仅依reason标签识别因果，74次完整归因由另一只读归因表提供。
- 末仓4+4诚实单列，另导出W6/B4个原始fill；W末仓包括2个部分平仓。未生成末仓伪final-exit或R。
- 原六周期selector、默认30日+日K、前300后50交易日/前后10月窗口、隐藏真实预热、matches联动轴保留；极窄react包装只添真实partial markers；原selector/plot源码均未复制或修改。
- 同一native入场日必须唯一绑定physical epoch，DB逐日与epoch CSV OHLCV一致；704轮持仓期精确源覆盖全通过，无十年同名混图或主力proxy。上市前/到期后、窗外缺行情或MA40预热不足保持真实缺口。MA40图表仅参考，策略MA40关闭；自然W-FRI周图不冒充策略接受观察周（可能跳周）。
- 15分钟0条、未补数；W8922/B8819个按窗期待交易日明确列为缺失。非分钟图有效，缺分钟不阻塞。
- 只读静态验收13375项、全部20交付文件及25使用源SHA通过；两页8段JS全解析，Node VM实际执行deep-link选中/渲染行为通过；13个新行为测试red→green，相关49测试4.139秒通过。最初相关测试因缺PYTHONPATH有1导入错误，随后显式配置examples/vendor通过；子进程sitecustomize缺vnpy提示和上游Tq免责声明原样保留，不冒称无环境提示或全仓库CI通过。
- 新bundle在验收前staging修正分钟缺失语义、加深链及末仓导出，再签最终交付manifest；没有改任何冻结旧源。静态check_js初稿匹配原matches字符串过窄，修正校验脚本后通过，未改canonical。
- 浏览器验收：交主任务独立完成，当前本记录不宣称浏览器已通过。服务 http://127.0.0.1:8766/（本机只读，session76918）；W /weekly/index.html；B /baseline/index.html。
- 本次金融回放0、策略改动0、下载0、生产/CTP/API构造0；相关测试可导入上游模块但不启动金融引擎或TqApi。

- 补充独立均线验收：651120个可见日K MA5/10/20/40值均与完整冻结physical epoch独立滚动值一致；704轮首可见日MA40空值均由真实上市历史不足导致，可避免领先空值0、合成补值0。详见outputs/stage031_recap_tests/ma_validation.json。

## 外部调研与判断

核对Plotly官方[事件文档](https://plotly.com/javascript/plotlyjs-events/)、[函数文档](https://plotly.com/javascript/plotlyjs-function-reference/)及[官方GitHub事件说明问题](https://github.com/plotly/documentation/issues/873)。判断：原canonical matches轴足以保留同步缩放；用原react调用的窄包装加入实际fill与原entry ID导航即可，不需要重造K线图或重新获取行情。

## 开始/结束反思与TODO

- 开始/结束是否过拟合：否，仅展示既有固定结果，不重拟合或挑选交易；这不排除原研究本身的历史选择与非OOS局限。
- 开始/结束继续价值：是，逐笔证据对解释DD路径有价值；不据图形反推参数，不把80多个partial markers误称74个触发。
- TODO：主任务完成浏览器默认周期、筛选、前后导航、深链、真实partial marker和同步zoom验收，再进行独立结果审查；不得把此静态验收当策略或生产资格。
