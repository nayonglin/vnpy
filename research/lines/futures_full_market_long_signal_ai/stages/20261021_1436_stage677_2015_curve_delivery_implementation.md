# Stage677：2015起资金曲线交付脚本

- line_id：`futures_full_market_long_signal_ai`；时间2026-10-21 14:36 CST；本次非重要突破，仅实现已冻结673的图表交付。沿当前研究线，未改LINE、registry、旧策略或其他线。
- 本分工只新增`tools/stage677_plot_2015_curve.py`及本唯一stage，未读取actual675金融数据，未运行训练/预测/策略现金/SQL/下载/浏览器。675终态后由root运行交付。
- 开始/结束是否新增过拟合：否，图表只呈现固定基础/压力两条连续资金曲线，不选优、不改参数、不抽样。继续价值：是，清晰显示长周期回撤并交付完整日频CSV；不据图表自动晋级或加注。

## 输入和读取边界

675实施者确认固定schema为`stage675_common52_2015_extension_v1`；入口要求manifest/terminal completed、mode actual、1新fit/2新cash，但自身不触发任何金融计算。两账户均为`all_2015_base/stress`，arm=`VOLUNTARY_RESELECT`，window=`all_2015`。

脚本只核manifest/terminal、两本daily与summary、wide `equity_and_drawdown.csv`、年度表的准确SHA，读取其小数据。daily直接读取`date/equity`；wide曲线字段`date/base_equity/base_drawdown_pct/stress_equity/stress_drawdown_pct`逐日与daily独立核算的回撤一致。年度表按manifest准确绑定直接解压为plainCSV，不生成另一套年度收益定义。

日期要求已排序、唯一、两成本一致，首日在2015年1月、末日2026-10-16。回撤为`(equity/max(初始100万,截至当日权益峰值)-1)*100`，含初日亏损；核期末权益、最大回撤和已有summary收益。年度表需完整覆盖daily年份且无重复账户-年。缺执行未知或历史陈旧状态拒绝，不能把缺失写成“否”。

## 图和下载

采用当前`.py311`已有Plotly 7.1.0标准Scatter+subplot，离线HTML内嵌Plotly JS，无matplotlib、PIL、kaleido、安装或手绘SVG。双面板为权益万元和负回撤百分比；两成本完整日频、不抽样。中文标题写明2015起、截止2026-10-16、初始100万元。2020/2023模型更新细竖线及说明明确资金连续，未伪装重启。

图内显示实际`execution_unknown/any_historical_stale`，标记研究回放而非实盘成交。HTML自身的可访问按钮“下载资金曲线PNG”调用`Plotly.downloadImage`导出1600×1000标准PNG。root可正常等待浏览器download事件、点击按钮并保存；本分工不操作共享浏览器、不调用浏览器evaluate或toImage。

默认输出`outputs/stage677_2015_equity_delivery/`：

- `equity_curve_2015.html`，自含JS交互图。
- `equity_and_drawdown.csv`，原宽资金与回撤CSV，UTF-8 BOM便于Excel读取。
- `annual_slices.csv`，完整原年度数据，UTF-8 BOM。
- `plot_manifest.json`，输入与输出准确binding、Plotly版本、全日频数量、初始peak与一致性检查、两户未知状态、待导出PNG元数据。
- root下载PNG后可用`--register-png`检查PNG头/1600×1000尺寸、保存为`equity_curve_2015.png`并登记准确binding；视觉核对仍由root完成，不以登记代替视觉检查。

调用：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage677_plot_2015_curve.py --manifest <actual675目录>/manifest.json
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage677_plot_2015_curve.py --register-png <浏览器下载PNG绝对路径>
```

## 验证与限制

本分工运行完全合成3日临时夹具：初日权益90万的回撤正确为-10%，基础/压力两户端到端HTML+plainCSV成功，wide回撤匹配、真实execution_unknown显示、失败actual拒绝且未创建输出。合成HTML约4.83MB，使用Plotly 7.1.0；夹具全部位于临时目录并已自动删除。`--help`通过。真实金融读取0、重放0。实际日频行数、真实结果与PNG视觉核验本阶段尚无，应由675/676终态后root收口。

本脚本18,424 bytes，SHA `28a929f3c416f1c06fa46f700b6f35330b55baa6e65675b2c8d8139d0399c38c`。14:37对PNG底部注释位置作留白修正，合成figure验证末行中心距图片底部19.15px，防止裁切；不涉及数据。外网/GitHub研究由root在673固定合同前统一完成；此子任务仅复用已有044先验绘图校验原则并查询当前本地Plotly签名，不引入新策略假设。

策略新增/修改/删除参数0；本分工新增/修改/删除回测结果0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率本阶段N/A，不能拿合成夹具数字当研究结果。
