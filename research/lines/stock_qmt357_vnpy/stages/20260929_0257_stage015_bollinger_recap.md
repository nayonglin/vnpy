# Stage015 股票逐笔复盘增加布林通道与冻结信号证据

- line_id：`stock_qmt357_vnpy`
- 当前模式：已完成回测的纯展示增强，不运行策略。
- 记录时间：2026-09-29 02:57 CST；最终页面于02:52生成，02:56完成浏览器与独立复核。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`；保留既有未提交修改，不提交或推送。
- 阶段性质：用户确认增加日K布林通道、信号日标记及BB/RSI/MACD条件状态。
- 是否重要突破：否，只提高复盘可解释性，不证明策略有效。
- 是否触发A/B：否，无新策略、调参或回测。

## 外部调研与判断

- 参考[Plotly填充区域文档](https://plotly.com/javascript/filled-area-plots/)及[scatter属性源码](https://github.com/plotly/plotly.js/blob/main/src/traces/scatter/attributes.js)，确认可用相邻上下轨填充通道。
- 判断：保留原多周期渲染器和联动轴，仅在日K添加三条线及信号点；不把20根30日K画成策略的20日布林。中轨加粗、上下轨淡色、通道轻填充，支持开关。
- 遵循`skills/futures-recap-html/SKILL.md`，复用固定SHA的Stage038纯展示函数，由独立股票适配层扩展；不复制模板或修改期货脚本。

## 本次变更

- 新增脚本：`tools/stage015_stock_bollinger.py`、`tools/stage015_stock_bollinger_html.py`、`tools/stage015_stock_bollinger_ui.js`、`tools/stage015_verify_browser.js`。
- 新增测试：`tests/test_stock_bollinger.py`（42项）、`tests/test_stock_bollinger_html.py`（12项）。
- 修改脚本：无；原Stage014适配层、策略和期货资源均不改。
- 删除脚本：无。
- 新增展示配置：默认打开日K BB(20,2)；青色菱形表示信号日收盘，原蓝色买入三角仍是次日真实成交价。
- 策略参数新增/修改/删除：均无。BB周期20、倍数2、样本标准差`ddof=1`严格来自冻结策略。
- 按股票和信号日期关联冻结`signals.csv`，复核BB谓词及当日中/上下轨；RSI/MACD状态使用原冻结日志，不重新发信号。
- 每个展示日只使用截至该日的历史复权因子计算，换算到该日原价尺度；原OHLC、成交价格、普通MA、盈亏和其他周期数据逐值不变。
- 信号必须在买入前的最近有效交易日；缺失/重复日志、非法布尔、条件数不符、窗口或价格不匹配均拒绝生成。
- 原v1不覆盖。v2为中间草稿，生成后计算模块增加两项输入保护导致其代码哈希过期；保留草稿但不交付。待代码冻结后生成v3，输入/代码/产物SHA全部匹配。

## 冻结回测参数（本次未运行）

- 数据区间：2020-01-01至2026-09-28；并未延长到记录日9月29日。
- 冻结来源：`examples/stock_backtesting/qmt357_commit4ac255e/outputs/fixed_2020_20260928_commit4ac255e_repaired_v1/`。
- 账户规模：300,000元；最多3只、单只32%、每日开仓预算90%、现金缓冲5%。
- 固定止损2%、止盈45%，沿用commit分级移动止损；BB/RSI/MACD任意2项满足。
- 佣金0.0003、最低5元、印花税0.001、每股滑点0.01元。收盘信号、次日开盘成交，不是QMT14:50回放。
- 样本：全部226笔闭合交易；无利润筛选后再生成。

## 结果（完全沿用Stage012，不是新增回测结果）

- 期末权益：252,720.8403元。
- 总收益：-15.7597199%。
- 最大回撤：-29.2172727%。
- Sharpe：-0.0875277。
- 总滑点：26,550元。
- 佣金含印花税：29,980.9597元。
- 总交易次数：452次买卖成交、226笔往返交易。
- 胜率：16.3716814%，37笔净盈利、189笔净亏损。
- 期末持仓0；无新增、修改或删除回测绩效。

## 展示及验证结果

- 226笔信号全部对齐：BB+RSI为13笔、BB+MACD为19笔、三项全中为7笔、仅RSI+MACD为187笔。因此39笔BB条件成立，187笔不成立，后者并非信号错误。
- 74,649根展示日K；其中1,021根不足20根真实历史的布林值保留为空，不伪造预热。
- 同日志中轨最大误差约1.14e-13元、上下轨约5.36e-11元；原收盘/OHLC误差0。
- 独立reviewer直接逐日取20根窗口用NumPy复算三轨，最大误差约1.04e-10元；旧v1全部历史字段和冻结绩效不变，v3与已审v2数值一致。
- 独立reviewer最终只读结论：通过，Critical/Important/Minor均0；全部输入/产物SHA一致；独立54项布林/展示测试通过。评审不判断alpha或实盘可用性。
- 主代理股票全套测试：`QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD=1 .py311/bin/python -I -m pytest examples/stock_backtesting research/lines/stock_qmt357_vnpy/tests --import-mode=importlib -q --tb=short`，363 passed in 45.37s。
- v3 HTML包含3段JS，全部解析通过；控制台0消息、0错误、0警告；`git diff --check`通过。
- Playwright实际交互通过：开关三轨且保留信号点、跨交易保持开关、BB真/假两种展示、隐藏日K提示、空筛选清理旧信号、226/37/189笔筛选、年度/股票切换、五周期显示、无分钟数据提示、实际鼠标拖动联动缩放及重置。
- 例：600183.SSE信号2020-01-02收盘22.74元，实际2020-01-03买入22.81元，BB未触发、RSI和MACD触发；页面明确分开两日/两价。
- 已查看完整页面截图：中轨、上下轨、轻填色、条件标签和原图可见，未发现新增遮挡。

## 输出文件与身份

- 最终页面：`outputs/stage015_commit4ac255e_stock_recap_bollinger_v3/index.html`。
- 同目录：`summary.json`、`records.json`、`chart_manifest.csv`、`indicator_audit.json`。
- 截图：`output/playwright/stock_recap_stage015_bollinger.png`（仓库根目录下、忽略文件）。
- 最终HTML SHA256：`1e3c479eb033386d7fcd63868784e71bc363f8b7d6f1474a340b723c461c0d2e`。
- 最终summary SHA256：`c14369c70f014de509c4ab794c16d924d9ce6bbfeeed65983fb89415223fce6b`。
- 计算模块 SHA256：`858281df7dd98cb58a39bcf3ffce728b328af78a1aad90c85f39ae4438a25c66`。
- 原v1 HTML SHA256仍为`7323dbd6a3292c07e9c02441af92f4f5bccf5ad06bf6e4607554865017b076b7`。
- 未重跑策略、未下载行情、未连接CTP、未访问生产、未修改期货代码/配置/资源；生成进程未导入vnpy/tqsdk/期货执行模块。

## 结论与反思

- 阶段结论：布林展示与冻结信号证据已补齐。它解释实际交易，不把“画出布林”误当作“每笔都依靠布林入场”。
- 运行前/后过拟合判断：均为否；没有阈值搜索、选样或策略改动，只按固定源码语义展示已有样本。
- 运行前/后继续价值判断：均为有；能区分信号与成交，检查中轨反转是否真正成立，减少视觉误判。不能据此推断未来盈利。
- 后续：本次展示任务完成；若继续研究，优先既定的亏损/成本与剩余数据风险归因，不据图形观感寻优。
- 原有月度池、数据修订残差、复权/分红和执行时点近似等边界保持披露；不晋级正式或实盘候选。

## 合入建议

- 更新本线`LINE.md`：是。
- 更新`research/registry.md`：否，非跨线阶段；保留其既有未提交改动。
- 追加根目录`memory.md/back_log.md`：否，纯展示增强。
