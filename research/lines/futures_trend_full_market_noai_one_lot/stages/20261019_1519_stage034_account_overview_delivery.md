# Stage034 整体资金曲线与回撤图交付

- 时间：2026-10-19 15:19 CST；line_id=futures_trend_full_market_noai_one_lot。不是重要策略突破，仅补充既有冻结账本的展示。
- 用户问整体资金与回撤；旧逐笔页没有账户总览。本次新增tools/stage032_account_overview.py及outputs/overview_20261019_lifecycle_unlimited_v2/，含index.html（5,099,555字节，约5MB）、高清equity_drawdown.png、2862行equity_drawdown.csv、figure.json、summary.json。旧225MB逐笔页和金融源全部不改；新页提供旧逐笔页与高清图链接。
- 资金曲线直接取run_20261018_lifecycle_unlimited_v2/daily.csv，源manifest SHA256=b0893921b612ed284458625bd6405fef5a994a36beb9214839a8a4a7b27be983，与用户当前reviewed逐笔页身份绑定；2015-01-05—2026-10-16共2862点。权益逐点等于100万+cumsum(net_pnl)；原生highlevel/drawdown/ddpercent逐点核对。账户总权益含成本和未平仓浮盈亏，不等于已实现可提取现金。
- 本次未新增/修改/删除策略参数，无金融回测、行情下载、账户/生产/CTP/订单API。原冻结指标未变：期末权益1,376,927.91元、总收益37.6928%、最大回撤-37.9389%、Sharpe0.180500、滑点156,840元、手续费49,387.09元、6448成交/3218完整交易、净胜率33.6544%。原日线近似/日内C2/C9与供需停用、12期末正常仓、静态费用/元数据等限制不变。
- 最大回撤高点2022-04-26（1,525,997.450849元）→低点2025-06-27（947,050.268466元），回撤金额578,947.18元；期末回撤-13.2792%按截至期末的新历史高点计算，不与最大回撤起始高点混淆。页面/PNG中单位是万元和百分比。
- Stage033独立展示复核PASS：2862个点及HTML嵌入data/layout与figure JSON逐值一致，所有source/artifact/generator绑定与PNG视觉检查通过。该审查不是一次新的金融策略审查/回放。
- 根任务实际浏览器观察两panel成功渲染；点击Zoom in后两panel的SVG线条路径均变化，Reset axes后逐值恢复。3段内嵌JavaScript（配置、Plotly库、render调用）全部解析；首次校验器沿用旧页面的两script假设而失败，实际三段均已解析，已修正为检查所有实际script而非固定两段，未修改产物掩盖错误。证据stage032_overview_ui_js_validation.json。
- PNG已用view_image目视检查，文字、注释和两幅全周期图完整；只新增overview展示，没有复制或改写canonical逐笔渲染器。旧逐笔页上次被中断的UI验收仍不能因这次独立overview通过而称完成。
- 临时127.0.0.1:8765服务已Ctrl-C退出并确认端口关闭；open_in_codex已排队打开永久file页面，不能声称用户当前已看到。最终以绝对文件链接/PNG交付。
- 调研：[Plotly官方共享时间轴文档](https://plotly.com/python/subplots/)及[vn.py官方组合回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。判断：沿用已独立对账的日MTM，不从已平交易累加另算资金；两图共享时间轴便于比较风险，PNG用于直接查看/保存。没有采用平滑或删除亏损日。
- 开始/结束过拟合判断：否，仅展示现有账本，未调信号、参数、年份或品种。继续价值：是，整体曲线有助于识别2024—2025长期回撤；不因此提高alpha/生产结论。后续若研究风险来源，应另作只读归因，不凭图扫参。本阶段未新增/修改/删除金融业绩。
