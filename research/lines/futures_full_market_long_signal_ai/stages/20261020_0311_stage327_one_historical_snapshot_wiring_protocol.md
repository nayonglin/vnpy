# Stage327：唯一真实历史快照接线协议

- line_id：futures_full_market_long_signal_ai；时间：2026-10-20 03:11 CST；沿用codex/ai-training-data-expansion。非重要收益突破，非正式A/B/C。
- 325 caller与326 warmup适配完成，2组新tiny GREEN（.355/.227秒）；328一次静审无开放P0/P1/P2，root核最终小绑定。0旧suite，0金融重放。
- 固定2026-10-16，理由为接受132cache的末日而非收益选择。原130 main2023模型/scaler、320/321/322政策与参数全部不变。
- [唯一实际协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage327_historical_snapshot_wiring/protocol.json)绑定新源码、胶水、328静审及326精确input授权。cache/econ各1加载、同日11列只读SELECT1；schema元数据此前root2+author326两次，和本次dataSELECT分开计数。无大库重新hash。
- 一次fresh actual_run1/snapshot加载后仅observe_only：全部98父行/95family，原9520epoch域，26raw+26missing及固定score。没有真实资金账户初始化、D推进或seal；本次fit/cash/旧控制/下载预算均0。失败保存现场即停，不自动retry。
- 326与325注入同一320 core避免类身份冲突。当前月份econ从已载RAM导出供独审，禁止第二次载源。真实snapshot完成后328仅读新compact current/warmup/inventory/result/receipt审查，不重复读110MB/8MB/SQL。
- 当前T0=None，完成/首次发布/D首开未知，保持历史开发演练；源calendar无后继则D unknown，不补造日期。未来接收器和真实时钟另绑，此协议不安装调度。

调研与判断：官方[SQLite URI](https://www.sqlite.org/uri.html)的只读语义用于绑定历史静态库，immutable仅在无WAL/SHM且前后stat一致的有限静态源前提下使用；不用于可变接收库。[Freqtrade维护者因果检查说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)支持前缀不变性检验，不为本期货AI提供alpha背书。本轮不安装或调用其框架。

运行前新增寻优过拟合否，原政策历史择题风险仍是；继续的价值是一次真实输入核对，不是继续在同史换参数。运行后判断和实际终态由329汇总。本阶段无金融绩效，权益/收益/DD/Sharpe/滑点/交易/胜率N/A；完整目标active，累计453fit/246cash及前包1partial不变。仅本线记录，无其他线/正式/生产/Git变更。
