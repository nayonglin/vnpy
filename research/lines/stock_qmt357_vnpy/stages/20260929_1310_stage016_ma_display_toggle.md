# Stage016 股票复盘增加均线显示开关

- line_id：`stock_qmt357_vnpy`
- 记录时间：2026-09-29 13:10 CST；约13:01开始实施，13:09浏览器交互验证通过。
- 阶段性质：纯展示增强；不是重要突破，不触发A/B，不产生新回测。
- 用户确认：增加默认开启的“显示均线”，控制所有周期MA5/10/20/40；布林独立控制。用户要求后续范围明确的任务直接理解并做，不再反复确认方案。

## 外部调研与判断

- 参考[Plotly scatter可见性文档](https://plotly.com/javascript/reference/scatter/#scatter-visible)和[官方属性源码](https://github.com/plotly/plotly.js/blob/main/src/traces/scatter/attributes.js)。
- 判断：对精确`legendgroup=ma5/ma10/ma20/ma40`的均线设置`visible`，保持trace顺序、坐标与数据。不开新计算、不改策略，比修改均线值更符合“显示配置”的要求。
- 按复盘HTML技能复用原Stage015股票适配层及固定SHA的canonical renderer，新增股票独立扩展；旧页面及旧生成脚本保持不变。

## 本次变更

- 新增：`tools/stage016_stock_ma_ui.js`、`tools/stage016_stock_ma_html.py`、`tools/stage016_verify_browser.js`、`tests/test_stock_ma_html.py`。
- 新增展示参数：`moving_averages.default_visible=true`，周期5/10/20/40，覆盖全部周期；切换交易/筛选/周期保持当前开关，刷新页面恢复默认开启。无跨页面持久化。
- 修改/删除策略参数：无。修改/删除回测结果：无。
- 关闭只隐藏均线及相应图例；K线、成交量、布林、信号日、成交点不受影响。先手动隐藏图例再切换总开关，也能恢复全部均线。
- 所有源代码/输出新增均在本股票线；保留其他既有dirty work，不改期货代码/配置/资源及根目录账本。

## 来源和冻结指标（本阶段未重跑）

- 页面来源：`outputs/stage015_commit4ac255e_stock_recap_bollinger_v3/`。
- 原回测：`fixed_2020_20260928_commit4ac255e_repaired_v1`，区间2020-01-01—2026-09-28，初始30万元。
- 原资金/风险/费用配置、次日开盘成交和各项数据限制全部沿用Stage012/015。
- 期末权益252,720.8403元；总收益-15.7597199%；最大回撤-29.2172727%；Sharpe -0.0875277。
- 总滑点26,550元；佣金含印花税29,980.9597元；452次成交/226笔闭合交易；胜率16.3716814%。期末0持仓。
- 39笔BB条件成立、187笔RSI+MACD触发不变；无15分钟数据的披露不变。

## 验证

- TDD：新增15项测试先因功能未实现失败，再全部通过。覆盖六种周期的MA可见性、输入不可变、其他图层保留、恢复显示、父页面状态/哈希/笔数校验。
- 股票全套：`QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD=1 .py311/bin/python -I -m pytest examples/stock_backtesting research/lines/stock_qmt357_vnpy/tests --import-mode=importlib -q --tb=short` → **378 passed in 34.88s**；未运行会涉及其他研究线的全仓库测试。
- 独立只读review：代码与产物无阻断问题；三份冻结数据文件与父页面逐字节相同。reviewer未操作浏览器，以下浏览器证据由主代理完成。
- 25项输入哈希、4项产物哈希全部一致；4段嵌入JS解析通过；`git diff --check`通过。
- 真实浏览器：默认两周期8条MA、关闭后0条可见且3条BB仍在，开启恢复8条；五周期20条MA全部开关；跨下一笔/筛选/空结果/周期切换保持设置；手动隐藏图例再开关可恢复；实际鼠标缩放后切换范围不变且保持联动。
- 原Stage014和Stage015浏览器验收脚本在新版全部通过，保留226/37/189笔筛选、年度/股票筛选、缺分钟提示、默认周期、BB信号与成交日区分。
- 控制台0错误/0警告；已保存`output/playwright/stock_recap_stage016_ma_on.png`和`stock_recap_stage016_ma_off.png`，查看关闭状态完整截图确认普通均线消失、布林/价格/标记保留；验收后恢复默认开启。
- 浏览器验证工具一度因npm解析不到`playwright-core@1.64.0-alpha-1790635538000`而不可用；停止本次挂起的CLI，改用本机已有完整1.63.0 CLI运行，无安装或项目依赖改动。验收脚本修正了两项测试端假设：隐藏的Plotly `_fullData`省略legendgroup、图例文字由`.legendtoggle`接收点击。产品代码未因此改变。

## 输出与身份

- 新页面：`outputs/stage016_commit4ac255e_stock_recap_ma_v1/index.html`。
- 同目录含`summary.json`、`records.json`、`chart_manifest.csv`、`indicator_audit.json`；后三者与Stage015 v3字节一致。
- 新HTML SHA256：`00b17d284733a732e20507e94de440f62c14147699c8d03bd0ecba247934b6c0`。
- 新summary SHA256：`67a0704af603d36bc4b82467d0c296d15df7c4fed741ccec10991d99ec5e1a27`。
- 旧v3 HTML SHA256仍为`1e3c479eb033386d7fcd63868784e71bc363f8b7d6f1474a340b723c461c0d2e`。
- 策略重跑：否；行情下载：否；生产/CTP访问：否；生成进程期货/vnpy模块导入：无。

## 反思和后续

- 运行前/后过拟合判断：均为否，仅调整显示，不改变信号、参数或选样。
- 运行前/后继续价值判断：均为有，减少线条干扰，便于独立观察布林和价格。显示改善不代表策略收益改善。
- 本次任务完成，无进一步阈值寻优或策略改造。仅更新本线LINE，不更新registry、memory.md或back_log.md。
