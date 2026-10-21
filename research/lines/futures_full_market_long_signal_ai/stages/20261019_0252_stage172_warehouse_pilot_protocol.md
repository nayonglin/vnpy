# Stage172：固定七日报原文来源试取

- 2026-10-19 02:52 CST；line_id `futures_full_market_long_signal_ai`。上一goal turn为progress：170真实12fit/8cash及独审已关闭固定q，不是等待或无进展。本轮新信息为仓单登记供给状态，未按收益选择品种/日期，不恢复q。
- 本轮已读registry/LINE/171、核.python3.11.5+requests可用，bs4/lxml未安装且不安装。重读官方日周入口和维护者详细仓单源码；仅作为URL/格式线索，实际数据以原文为准。
- 事前7日为20251113/14/17/18/19/20/21，052完整calendar确认连续七报告日；前3JSON、后4HTML。每日报告一次公开HTTPS，无自动重试/重定向/关闭TLS/挑战绕过；首次失败保存响应、后续not_attempted，不替换日期。全表所有品种和层级保留。
- 原单位/地区/仓库厂库/总计/官方增减/报告与请求日期分别核；无单位unknown，不以惯例/合约规格推单位，不填0。跨格式差额若单位/覆盖未闭合则unknown，归档不签first-release PIT。
- frozen protocol SHA `7359cd6fbd9d1bbf65d30dd89b8b4b2d7da4d49463de2018d737814a39b17b00`；只读获取脚本 `df386f3c8fe4a432fc53a28c8bed24ba5360895fd1e17232d10ba8b486af16bf`；尚未actual，不把7请求预算称为已下载。本轮0fit/cash/SQL/价格/新标签，累计409fit/218cash；权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。
- 开始/结束新增结果后调参过拟合：否；历史择题风险有。继续这一有界来源验证有价值；立即金融/全历史下载无授权，goal active。

## 2026-10-19 02:55 CST 唯一来源actual已完成

- 唯一fetch session25097 exit0，12.526406209秒，7次报告HTTP请求、7份HTTP200且预期JSON/HTML envelope，0重试/重定向/未请求；原响应共845,130B。原文/HTTP头/获取时点、每日报告收据与SHA保存在`outputs/stage172_warehouse_pilot_raw/actual_run1/`。manifest5362B SHA1460d64762d6e90822aeb7bca3a96299574df3e149721c6548debc08b8c7f545。
- old 11/13样例top明确report_date/o_tradingday和update_date(15:13)，ROW有WGHTUNIT/WHTYPE代码、ROWSTATUS与具名数量/增减；不能把“没有单位文字”写成“没有单位字段”。代码book尚缺，保留原code及语义unknown，不从11/18的吨倒推。HTML样例含正文报告日、单位吨和地区rowspan；34table包含intro，不能把intro当品种。
- 只确认取回与基本envelope，不签数值/单位/层级连续资格、首发PIT、训练或金融。后续173唯一全七离线规范处理及174独立全七原文/输出审查。累计409fit/218cash不变，新fit/cash/SQL/标签/价格0。
- 结束新增按收益调参过拟合否；历史择题风险有；继续有界语义核验有价值，不扩大历史下载或恢复固定q。
