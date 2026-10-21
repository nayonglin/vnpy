# Stage687：0.25% / 0.5% / 1% 六账户连续资金图实现

- line_id：`futures_full_market_long_signal_ai`；记录2026-10-21 17:47 CST；非重要突破；本阶段只交付684冻结的六账户图表，不运行现金回测。
- 先读registry本线，再核684协议。仅新增`tools/stage687_plot_halfpct_comparison.py`和本唯一stage，不改旧脚本、LINE、registry、正式/生产/CTP/邮件/调度或Git。
- 开始/结束对“本次展示是否新增过拟合”的判断：否，完整保留三风险两成本，不筛选最好的一条、不拼不同资金起点、不改参数。但0.5%是在已观测0.25%和1%同史结果后追加，研究选择的自适应历史风险是高，不能据图形宣布最佳风险比例。
- 开始/结束继续价值：是，有限回答用户指定0.5%单点的收益和回撤代价，并交完整逐日/年度表；继续据本图扫描更多小数风险没有自动授权。

## 调研与判断

外部参考沿root冻结在684的CME风险仓位原则及backtesting.py原作者资金/保证金约束实现，不新增策略或软件依赖。判断保持：单品种风险改变的是受总风险、保证金、容量和整数手约束的资金分配，不能线性放大旧曲线。687只做标准Plotly展示，不赋予PIT/OOS、最佳比例或实盘加注资格。

## 复用边界与输入合同

685 schema为`stage685_single_risk_halfpct_v1`，账户`all_2015_halfpct_base/stress`；0fit/2cash、风险0.005、总风险0.02、margin0.25、buffer1.1、initial stop0.25N不变。入口要求completed actual和成功terminal，核684冻结参数、actual参数生效receipt和旧globals未改后，才读取两本新daily/summary。

旧0.25%与1%四账直接复用已验682的`plot_manifest.json`、`equity_and_drawdown.csv`和`annual_comparison.csv`。682必须已登记浏览器PNG、来源窗口/连续资金/全日频等元数据符合合同，并且其source_bindings精确包含684的`inputs.baseline_manifest`和`references.onepct_manifest`。这里只核已验绘图缓存的精确binding、列、日期和末值/元数据，**不读取675/680原daily、summary或其他账本，不重审旧账**。

新0.5%只核daily权益、ROI、含初始100万峰值的最大回撤及真实布尔`execution_unknown/any_historical_stale`。685实际仍仅生成0.25%/0.5%四条曲线和48账户年；687核其0.25%列与682缓存相同、0.5%列与新daily相同，再合入682保留的1%曲线。六账必须同起止2015-01-05—2026-10-16，实际2862来源日，资金从100万连续起算。

合并年度表得到6账×12年共72行。旧0.25%同名年度行需保持全部身份字段逐字相同；仅`starting_equity/ending_equity/cash_growth/return_pct/max_drawdown_pct`五个金融字段允许CSV浮点表达改变，Python float值和零符号必须精确相同，不使用误差容忍救差值。既有1%原年度行原样复用，未重新发明年度收益定义。

## 图形与输出

3面板为基础成本3风险权益、压力成本3风险权益、六账户回撤。基础用蓝色、压力用棕色，分别用明暗与虚线0.25%/实线0.5%/点线1%区分；图例两行、每行3风险。全部日频、不降采样、不拼接。标题写明截止2026-10-16、初始100万、总风险2%不变和六账实际execution_unknown。

PNG为1600×1200，主标题顶部锚点距画布顶部30px，底部末注中心距底26.45px，首版已预留文字空间。HTML自含Plotly JS，保留“下载资金曲线PNG”正常浏览器按钮，调用标准`Plotly.downloadImage`；不安装matplotlib、PIL、kaleido或其他依赖。

默认`outputs/stage687_halfpct_comparison_delivery/`（已存在目录拒绝覆盖）：

- `equity_curve_halfpct_comparison.html`：离线交互图。
- `equity_and_drawdown.csv`：13列=`date`＋risk025/risk050/risk100×base/stress×equity/drawdown_pct，2862日。
- `annual_comparison.csv`：6账户72年度行，保留完整来源字段。
- `plot_manifest.json`：来源binding、旧缓存复用边界、参数与曲线检查、6账unknown、布局留白和导出状态。
- `equity_curve_halfpct_comparison.png`：root浏览器按钮导出后登记，1600×1200。

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage687_plot_halfpct_comparison.py --manifest research/lines/futures_full_market_long_signal_ai/outputs/stage685_single_risk_halfpct/actual_run1/manifest.json
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage687_plot_halfpct_comparison.py --register-png <浏览器下载PNG绝对路径>
```

可选`--prior-delivery`默认指向已验682的plot_manifest，无需用户填写。新脚本复用精确冻结SHA为`ae51911348d1a3d7ca3a0e3e715a3b6e169af2e5b94d77929728979af45740f6`的682无副作用小文件工具函数，源代码依赖也进入manifest，旧文件保持原样。

## 合成验证与真实读取状态

`.py311/bin/python -B ... --help`通过。一次临时合成端到端夹具使用每账12日、六账72年度行，生成完整HTML/13列CSV/年度CSV/manifest成功，12条标准Plotly trace、HTML约4.84MB。48个旧基准金融单元格仅整数/`.0`表示改变，精确float等价通过；失败actual、身份字段`source_days 1→1.0`、旧ending_equity变化十亿分之一，三种违规均被拒绝且未创建展示目录。顶部/底部留白值检查通过。

夹具全部位于TemporaryDirectory且自动删除；旧675/680原实际文件打开0，685真实金融读取0，新增fit/cash/SQL/下载均0，不操作共享浏览器。真实685由root完成，本分工不消费其实际结果；root将在685/686终态后执行本脚本、浏览器导出与视觉检查。PNG登记只核PNG头、尺寸和HTML/CSV绑定，不能代替实际查看。

本阶段策略参数新增/修改/删除0，回测结果新增/修改/删除0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率本阶段均N/A，由685/686/root结案记录承担，不能把合成值当收益。

冻结脚本26,327 bytes，SHA `424578508eadaa962f27d390bf5b18008d9be471c46861c13a3fe675808dd6f2`。本阶段不写根memory/back_log。
