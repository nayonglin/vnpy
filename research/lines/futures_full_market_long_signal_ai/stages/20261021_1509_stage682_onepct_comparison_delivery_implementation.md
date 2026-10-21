# Stage682：0.25%与1%单品种风险连续资金图交付实现

- line_id：`futures_full_market_long_signal_ai`；时间2026-10-21 15:09 CST；非重要突破，本阶段只实现679已冻结实验的展示和原数据交付。
- 先读`research/registry.md`本线及677交付约定；只新增本唯一stage与`tools/stage682_plot_onepct_comparison.py`，不改LINE、registry、677、正式版本或其他线。
- 开始/结束新增过拟合：否，4账户按固定基础/压力和0.25%/1%完整呈现，不选优、不改收益参数、不拼不同起点。历史择题和加注判断仍有同史选择风险，图表不提供PIT/OOS或实盘加注资格。
- 开始/结束继续价值：是，图表可直接对照固定成本下的收益和回撤代价，并交付完整日频和年度数据；不因图形表现再扫风险参数。

## 外部调研与判断

外网与GitHub参考由root统一完成并冻结在679协议：CME仓位风险说明和backtesting.py原作者资金约束实现支持“止损金额与预算决定手数、保证金与整数约束影响结果”的原则；不支持风险提高四倍就能把收益路径线性放大。682只用本地已有Plotly 7.1.0标准Scatter与subplot呈现原始已完成账户，不导入第三方策略或收益。

## 输入与展示合同

680作者确认schema=`stage680_single_risk_onepct_v1`，顶层`protocol`、`terminal`、`input_bindings.baseline_manifest`、`parameter_effectiveness_receipt`、`curve_data`、`annual_slices`均为精确binding；新账户为`all_2015_onepct_base/stress`，`window=all_2015`、`arm=VOLUNTARY_RESELECT`。675旧账为`all_2015_base/stress`。

入口在读取日账前要求680/675均为completed actual、terminal成功，680为0新fit/2新cash，675原1fit/2cash；再核679冻结协议与actual参数生效receipt：`SINGLE_RISK .0025→.01`是唯一授权变化，`TOTAL_RISK=.02`、`MARGIN_CAP=.25`、`MARGIN_BUFFER=1.1`、`initial_stop_N=.25`，旧globals保持原样。675 baseline必须与679的准确binding一致。脚本只消费小协议、manifest、参数生效receipt、4本daily/summary、原宽曲线与年度表，不读取信号、模型、原行情、native大缓存或族年大表。

四账日期必须共同从2015-01-05开始，末日2026-10-16，唯一有序且与冻结source_days一致（真实协议2862日）。权益按原daily全频读取；以`max(初始100万,截至当日权益峰值)`独立计算负回撤，再核summary期末权益、ROI、最大回撤和原宽曲线每一点。缺真实布尔`execution_unknown`或`any_historical_stale`拒绝交付，不能把缺失冒充“否”。

输出年度表保留680原4账年度字段与数值，不另发明年度收益定义，要求每账年份完整、账户年无重复，且675的旧账原字段和值保留。680通过pandas合并年度表，可能改变CSV浮点字符串表达；旧账年度值按相对1e−12/绝对1e−8数值等价核对，非数值字段完全相同，不能把重写表达误判为收益变化。图表为基础成本权益、压力成本权益、四账回撤3面板。0.25%虚线、1%实线；四账各有固定颜色，图内标题写清初始100万、总风险2%不变、实际`execution_unknown`，底注保留历史陈旧估值和研究执行边界。资金全部连续，不拼接不同重启账户。

## 文件与调用

默认生成`outputs/stage682_onepct_comparison_delivery/`，已存在目录拒绝覆盖：

- `equity_curve_onepct_comparison.html`：内嵌完整Plotly JS的离线交互图。
- `equity_and_drawdown.csv`：4账全日频宽表，包含8个权益/回撤列。
- `annual_comparison.csv`：4账完整年度对照原字段。
- `plot_manifest.json`：源准确binding、数据一致性检查、完整日数、实际unknown、参数边界、输出binding和PNG导出状态。
- `equity_curve_onepct_comparison.png`：root通过正常浏览器点击按钮下载后登记，1600×1100。

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage682_plot_onepct_comparison.py --manifest research/lines/futures_full_market_long_signal_ai/outputs/stage680_single_risk_onepct/actual_run1/manifest.json
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage682_plot_onepct_comparison.py --register-png <浏览器下载PNG绝对路径>
```

HTML按钮“下载资金曲线PNG”直接调用`Plotly.downloadImage`，导出1600×1100标准PNG。登记动作检查文件PNG头及尺寸，核原HTML/CSV准确binding后登记，不把尺寸登记当视觉验收。无需matplotlib、PIL、kaleido或安装任何依赖。本分工不操作共享浏览器；root在680/681终态后运行真实交付、下载、视觉核对和收口。

## 本阶段验证与结果

`.py311/bin/python -B ... --help`通过。临时目录内完全合成4账户、每账3日、12账户年，完整HTML/CSV/manifest端到端通过；标准Plotly生成8条trace，HTML约4.83MB，初日90万相对初始100万回撤正确为−10%。失败actual、actual仍为0.25%风险、actual总风险变为3%三种合同拒绝且不创建输出；前一轮也验证宽曲线与日账不一致拒绝。另用2日4账8年度行验证原年度整数金额与合并后`.0`表示数值一致时正常交付。PNG底部末行中心距底部24.25px，一次预留说明空间，未生成/反复修改真实展示。

本阶段真实680/675金融数据读取0、模型fit0、现金回放0、SQL0、下载0；当前真实结果、2862行核数、真实HTML/PNG与GUI验收均未执行，应由root终态后完成。合成夹具全部由TemporaryDirectory自动清除，不能拿其数字当研究收益。

策略参数新增/修改/删除0；回测结果新增/修改/删除0。期末权益、收益、最大回撤、Sharpe、总滑点、总交易次数、胜率本阶段均N/A；实际指标由680/681/root结案记录承担。

脚本24,200 bytes，SHA `ae51911348d1a3d7ca3a0e3e715a3b6e169af2e5b94d77929728979af45740f6`。本阶段不追加根memory/back_log，不改正式生产、CTP、邮件、launchd、Git分支/commit/push。
