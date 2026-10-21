# Stage012 185个参考观察的下一源日C2识别边界：结果前协议

- line_id：futures_ai_monthly_pool_generalization；day；2026-10-20 19:13 CST。
- 继承训练源halfR=False，C2=True；不改正式配置、1R/1R、MA/RSI/信号或TopN。
- 本轮不是金融回放；只对Stage008已固定的185个fresh月末观察建立条件性入场日probe，不能当185真实交易或完整60日标签。

## 固定方法

1. 显式解析CSV布尔；不把字符串False当真。185行全部保留，不按下一日数据覆盖删除。
2. 以继承源日历下一日期的同一真实epoch日open为参考entry；这不是已认证的canonical session首minute open。无下一日bar保留unknown。
3. 从冻结m0008 AST提取基础与Stage804初始止损方法；基于signal-day及此前两源日bar计算已知初始stop。多头max(close*.98,low)；空头沿冻结基础函数，不重写公式。
4. 单层probe先要求signed R在正确侧且不小于configured tick。错误侧gap不以abs救活，subtick不抬R到一tick。此合法性guard比源abs严格，明确为研究输入条件，不冒称正式已有该guard。
5. 在“真实完整全session第一open入场、R有效、日OHLC正确完整”的条件下，按是否触及逆1R/顺1R分neither、stop_only、confirm_only、both_unidentified。both的顺序未知保留两个可能动作，不以日线保守stop冒称已识别。
6. stop_only仅证明条件C2动作，不证明触发时刻/跳空fill/执行成功；不产出成交价或收益。所有exact_fill_identified=False，canonical first open verified=False。
7. 绑定current repaired `qmt_roll_intraday_execution.py` SHA和版本。冻结m0008 C2与修复版可能事件不同；明确不将两者混作同一完整正式源。

## 本地分钟数据并行盘点

Stage011只检查现有分钟cache、Stage861、session manifests和SQLite已有元信息/时间戳。文件/自然日期证据不等于规范session完整性；旧receipt不自动授权本线新source。未知仍保留。没有新下载或生产连接。

## 测试与复核

8项小测试已通过：多空四分、阈值等号、signed gap/subtick、非法OHLC、真实current helper的同日两路径反例、CSV布尔。首次冻结stop adapter合成probe暴露class名写错，真实数据运行前修复并新增第9项冻结方法整合测试。

实际后由独立agent按185源输入和小SQL重算risk/barriers/分类，核对分钟盘点边界。金融指标全部N/A；fit/金融/60日标签/订单0。开始过拟合判断：否，无新收益后参数扫描；继续价值：是，先量化C2保留下的真实可识别范围，再决定源标签工程。

外部调研：vnpy与Backtrader官方都区分信号时刻和后续撮合，OHLC模型不能推断任意日内顺序。本轮采用次源日open仅作显式条件probe，不认证真实成交。参考：[vnpy源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)、[Backtrader执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)。
