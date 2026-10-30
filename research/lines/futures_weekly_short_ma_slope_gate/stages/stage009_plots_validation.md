# Stage009 纯展示五图：实现与合成验收

- 新增仅 `tools/stage009_plots.py` 与 `tools/test_stage009_plots.py`、本组 Stage009 绘图日志。未修改已稳定 reserve wrapper/test、金融 runner、旧 Stage001—008、LINE 或其他研究线；未运行金融、未 commit、未发布真实图表。
- API：`render_five(summary: pandas.DataFrame, paired: pandas.DataFrame, daily: pandas.DataFrame, reviewed=False) -> dict[str, matplotlib.figure.Figure]`。返回固定五名、固定顺序的未保存 Figure；无输出目录参数，不写报告文件。调用方负责 save/clear、独审和原子 manifest。
- summary 严格92个唯一 start/variant（23起点×A_idle/A_R/C_idle/C_R），paired 严格46个唯一 start/arm，daily 严格141996点/92组。start 清单固定2015—2025各1/1、6/1及2026-1/1，截止2026-10-29；同起点四组日期完全相同、逐组完整端点和交易日数匹配。summary 支持 actual_end 或 end；paired eligible 是可选同义字段，如存在必须与 vote_eligible 一致。
- 数据门：所有必需数值有限；费用、成交及天数非负；初始总财富30万；W=E+R、R+累计T=15万、备用金不增、idle不转账、W=30万+累计净PnL；NAV按30万、DD包括初始30万高水位；末值/收益/DD/Sharpe/桶末值/非正权益天数均对逐日重新核对。各pair门按同30万idle vs reserve核对，权益相同不通过。
- 全部数据校验先于分配 Figure；漏窗、重复、元数据矛盾、15万NAV误分母、内部转账计利润等拒绝渲染。数据源SHA、资金规则触发/执行审计、收据和最终发布全量gate由调用方负责，此模块不替代独审。
- `reviewed` 只改总标题状态，数据序列、热力图矩阵、轴范围不变；测试逐图逐轴比对。图例：A_R蓝、A_idle灰虚线、C_R红、C_idle橙虚线；全部英文，线性NAV保留非正权益。图4各指标A/C共用对称色标。
- 2026Jan不足一年只展示、不投票；每arm有January11+June11成熟窗。图5独列2026观察四variant表，其余cohort门计数、负收益窗与补资消耗分布均仅成熟窗，不以不同长度总收益均值当预测。

## 固定五图

1. `01_full_2015_nav_drawdown.png`：2015年初四组总本金NAV及DD。
2. `02_january_starts_nav.png`：12个年初独立起点，每格四线。
3. `03_june_starts_nav.png`：11个6月起点，每格四线。
4. `04_reserve_effect_heatmaps.png`：各A/C、全部23起点，补资相对idle的总收益百分点/DD百分点/Sharpe变化。
5. `05_cohort_reserve_summary.png`：各arm January/June成熟门计数、负收益窗、备用金消耗分布和独立观察表。

## 验证

- 初始RED：`stage009_plots_red.txt`，5项均因缺渲染器失败。
- 最终GREEN：`stage009_plots_green.txt`，5项全部通过；py_compile通过。测试输入全部为显著合成fixture，虽保留141996点/92/46完整结构，但不是交易所日历或回测结果。
- 合成五图仅保存 `/private/tmp/stage009_SYNTHETIC_layout_v2_ohnx950n/`，均有 SYNTHETIC DATA / LAYOUT ONLY 水印与顶部红色声明，未混入真实 artifacts；已检查五图版式，调整页头空白并保留清晰图例。真实图仍必须在完整财务/独审收据就绪后由根调用，另做真实视觉验收。
- 此处未回测；不据合成展示判断收益/策略价值。固定展示不引入新阈值或挑窗；历史内过拟合及资金暴露变化不等于alpha的限制继承设计。
