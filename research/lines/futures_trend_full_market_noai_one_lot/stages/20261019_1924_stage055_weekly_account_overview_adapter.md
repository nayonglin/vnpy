# Stage055：周线开多候选资金总览只读适配器

- 时间：2026-10-19 19:24 CST。
- 研究线：`futures_trend_full_market_noai_one_lot`。
- 是否重要突破：否；这是冻结来源与展示合同增强，不产生新策略或回测证据。
- 范围：只新增本阶段工具、测试和本记录；未修改 Stage042/032、050/051/052、金融代码、旧输出、LINE 或其他研究线。

## 变更与研究判断

新增 `tools/stage055_weekly_account_overview.py`，复用 Stage042 的完整候选来源核验、Stage032 AST Plotly 图形以及静态 PNG 函数。没有复制图表实现；同一数据产生的 `fig.to_json()` 与直接 Stage042 调用逐字相同，保留共享日期轴。

页面标题明确“周线开多候选 / 日线近似”，增加原预算基线 A 与周线候选 C 的核心冻结指标及 C−A 差值表：初始资金、期末权益、总收益、最大回撤、Sharpe、净盈亏比、盈利因子、净胜率、完整交易数、成交次数、手续费和滑点。缺少的可选值显示“未提供”，不补零。下方曲线仅绘制 C；比较是同参数同区间描述，不作为晋级结论，也不宣称完成样本外/多起点验证。PNG 延续原 Stage042 的账户图标题及绘图实现，周线身份由新目录、HTML 和完整 summary 绑定。

显示显著区分：门槛序列是“品种未复权因果主力完成周收盘（accepted-clean）”；canonical 逐笔图仍按实际合约/背景主力拼接的原显示合同绘制，图上周 MA 未必与门槛序列一致，不调整原图 MA 数组。真实门槛依据链接到冻结源的 `weekly_main_features.csv`、`weekly_signal_audit.csv`、`weekly_execution_audit.csv` 和 `trades.csv`；后者明确指向 `stage051_weekly_signal_snapshot` / `stage051_weekly_open_snapshot` 两项 JSON。保留原预算、实际开盘复核、期末残仓和全部源 boundaries，并安全转义文本。

外部调研：查阅 [Plotly 官方 HTML 导出说明](https://plotly.com/python/interactive-html-export/) 及 [官方 GitHub 对应文档](https://github.com/plotly/plotly.py/blob/main/doc/python/interactive-html-export.md)。判断：沿用已有包含 Plotly JS 的离线图和共享轴，无需引入新库或图表实现；本任务不研究或优化金融参数。

## 来源合同

- 显式 `--source C --parent C_RECAP --baseline A --output NEW`，不按最近目录选择。
- 完整核验 C 来源 manifest/hash/code snapshots 与 parent recap summary 绑定；另验证 parent 全部 artifact hashes。
- C manifest 与 summary 必须 `long_weekly_filter=True`，逐项严格匹配 Stage052 的固定 weekly_policy，实际开多周线违规数必须为 0，三份周线证据必须纳入源 hash。
- A 的完整源 hash/code snapshot 核验，manifest SHA 必须等于 C 冻结的 `baseline_run_manifest_sha256`；双方原生风险预算、最多一手、开盘复核、无品种数上限、daily-proxy 标记均验证。基线不得已经启用本周线门。
- 固定基线代码身份为 `87487e32d36a443942f612ac7eeef71ede9ea46a`。A/C 参数字典、分析区间、本金及 manifest 起止相同；源存在的原 market/mapping/合约规格、Stage039/041 snapshot hashes 必须相同。
- 禁止输出覆盖或与 A、C、parent 输入目录重叠；生成前后复核来源、parent、055/042/032 代码未变。新 summary 绑定全部输出 hash、055 generator、042 adapter、032 plot、完整 A/C 来源与比较数值。

## 验证

- TDD RED：新工具不存在时 5 项合同测试全部明确 FAIL；新增周线序列区别/证据链接断言也在实现前明确 FAIL。
- GREEN：5 项专项测试 PASS，覆盖原图完全相同、周线文案/证据链接、XSS 转义、坏政策/基线参数/源 hash/原预算/parent 产物拒绝、输入输出隔离；真实临时目录生成 HTML/PNG/figure JSON/权益 CSV，并逐个核验输出 hash。临时 fixture 完成后清理，不写真实结果目录。
- 全线 `unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_*.py'`：**174 tests PASS，24.951 秒**。依赖测试导入时出现 TqSDK 标准免责声明；本工具不导入金融策略、不连接行情/CTP。
- `--help` 正常列出四个必需参数；`git diff --check` 通过。
- 055 工具 SHA256：`fa426e3235f1c15eaec373e7bc581184441a1b477e99142b64c09059f3acc33b`。
- 测试 SHA256：`c80b50b8c16a336aa6afcfbe70b498d151e97d3eec7a6fb8d2b9e395ce735c0a`。

## 参数、金融结果与边界

- 新增参数：仅展示 CLI 的显式 baseline 输入，无金融参数新增。
- 修改/删除金融参数：无。新增/修改/删除回测结果：无。
- 未重跑金融、未下载行情、未访问生产、未调用订单 API；尚未渲染真实周线 C overview，也未对其浏览器行为作验收声明。
- 不将旧 A 指标或 fixture 数字当作新 C 结果。本工具需等待根任务确认 C 完整冻结，并提供已复核 canonical parent recap 路径。
- 过拟合反思：本展示工作否，没有收益选参或更改周线定义；金融候选仍须面对同样本事后提出过滤条件的研究限制。
- 继续价值：是，建立可复核的 A/C 展示与证据入口；页面成功不构成金融有效性、生产资格或晋级依据。

## 下一步

根任务确认新 source 与 parent 完成后，才可执行（以下 parent 占位需替换成明确路径）：

```bash
/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage055_weekly_account_overview.py \
  --source research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261019_weekly_long_v1 \
  --parent C_REVIEWED_RECAP_EXPLICIT_PATH \
  --baseline research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261019_native_budget_one_lot_v1 \
  --output research/lines/futures_trend_full_market_noai_one_lot/outputs/overview_20261019_weekly_long_v1
```

真实渲染后由根任务做完整来源/指标/JS/浏览器联动检查；本阶段不越权提前生成。

### 19:26 完整 C 来源只读预核

根任务确认唯一 C 金融回放已经完成后，本阶段仅读取其闭合产物：manifest SHA256 `7e6f2647de1d99253ba2cbade3e0852158d50d3cbfde19e8da4afdba6f16fed4`。C/A 完整文件与代码快照 hash 核验 PASS；weekly_policy 严格一致，实际开多周线违规 0，三份周线证据已绑定，参数、区间、本金及共用市场/mapping/规格、Stage039/041 快照 hash 精确一致。

只读确认 C 冻结期末权益 1,128,882.73 元、收益 12.888273%、最大回撤 -24.758359%、Sharpe 0.086829、完整交易 1,868、期末残仓 12；A 为 1,832,070.63 元、83.207063%、-18.346986%、Sharpe 0.405520。C 明显变差，记录本身不改变任何金融结果或结论门槛。此时 reviewed parent 和新 overview 均不存在，因此未真实生成总览，继续等待明确 parent 冻结通知。

### 19:33 真实总览生成与独立逐点验证

根任务明确确认 `outputs/recap_20261019_weekly_long_v1_reviewed` 已完成后，使用上述显式命令生成 `outputs/overview_20261019_weekly_long_v1`，退出 0。未修改本工具或测试，未重跑金融、下载行情或访问生产。

- source manifest：`7e6f2647de1d99253ba2cbade3e0852158d50d3cbfde19e8da4afdba6f16fed4`。
- baseline manifest：`a8696e2b73b25399251d1efc46e47dfd49f89d23bfc80f6bc1f33bfdbe5237c3`。
- reviewed parent summary：`0925075b86077001be1721072d941c19b71a7153a8078c305d01670c22b22990`。
- overview summary：`c8edfe427bf4c8f2e1313f54fe9041a524533e4f3a51e5b077ecac55285b7094`。

| 输出 | 字节 | SHA256 |
| --- | ---: | --- |
| index.html | 5,139,782 | `c4bdef9fc9e41642064471f9d69ebed0ed3a855faea60277414d8381af8a919d` |
| equity_drawdown.png | 278,295 | `afade338b3970b27c7a3bcf146b0a97cec7e4f1ed131c4799a503ec93c3e5d5f` |
| equity_drawdown.csv | 237,654 | `dcdce3b3a60abe74a476748a0ff1bed3fc4e50ba685875620d28edfedaac22bc` |
| figure.json | 281,994 | `56c16c2db25be357875ed83be502ee6ac9cd173e946c3ec4ef1809c5eb6cd06e` |

独立核验结果 PASS，完整机器记录见 `20261019_1924_stage055_weekly_account_overview_validation.json`：

- 从头重新计算 source/baseline manifest、两者全部绑定文件和代码快照、reviewed parent 全产物、总览全产物及 055/042/032 代码，共 105 项哈希绑定通过。
- 读取冻结源原生 17 位 CSV 浮点表示（round_trip），逐个核对全部 **2,862** 日期与 equity/high-watermark/drawdown/drawdown_pct，并从本金+权益重新计算峰值及回撤。CSV 最大差分别为 `2.33e-10` 元、`2.33e-10` 元、`4.66e-10` 元、`4.44e-14` 百分点，均为既有 Stage042 读写显示浮点末位差；未改变任何金融阈值。
- Plotly 三条完整曲线各 2,862 点与冻结源一致；第 4 条最大回撤点准确，两个不同 y-domain 面板及 `xaxis.matches=x2` 结构正确。HTML 内嵌完整 data 和 layout 与 `figure.json` 精确一致。
- 12 行比较值及全部差值逐项对账 A/C 冻结 summary；全部源边界及周线图表区别披露保留且转义正确。
- HTML **3 段 JavaScript** 均通过 bundled Node `--check`；PNG 可解码、尺寸 **2240×1200**，目视资金/高点与回撤两面板清晰，期末 **112.89 万**和 **2021-04-22 最大回撤 -24.76%** 标注正确。
- 独立校验最初因当前解释器顶层未加载 PIL 而退出，尚未写报告；随后沿用 Stage042 已有绘图 site-packages 路径只读加载 PIL 后完成，没有安装依赖或改代码。
- 本阶段未做浏览器交互验收，保留 `browser_check=pending_root`；根任务负责真实页面缩放/复位与最终交付。174 项单测结果不替代浏览器检查。

执行后反思：展示工作没有过拟合或新增阈值，仍有证据闭合价值；C 相比 A 收益、回撤和 Sharpe 均变差，此次页面只作可复核研究记录，不构成晋级理由。
