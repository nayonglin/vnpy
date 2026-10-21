# Stage040 全域逐日asof代表与冻结fresh输入面板

- line_id=futures_ai_monthly_pool_generalization；2026-10-20 21:46 CST记录；实际一次21:45:01—21:45:39，37.83秒；非模型/收益突破。
- 新增工具tools/stage040_daily_source_panel.py与5项TDD，先模块缺失红→绿，再固定73分层月末点核Stage008及字面stop/prevMA20，全部通过后才全量。只读清库1552456行，stat/inode前后不变。4worker按product构建98安全分片，合并SQLite，未重跑原Stage008脚本。
- 399252行=98域×4074共同source日，全宇宙保留，DCE.S无bar仍4074行。普通95域387030行，_F3域12222行分列。212852代表，181469ready/3407fresh；普通181015/3399，_F454/8。no_asof_observation186400，missing_exact_epoch_calendar_bar30463，insufficient_calendar_history920。
- 每日只当日volume降序→closeOI降序→epoch升序选代表，不读未来、不因未来/41缺失换约；同epoch共同日AM41严格，不拼接填充。daily OHLCV/OI、source_id、frozen raw、RSI6/prevMA20完整；raw方向非空时Stage804 stop。仅allowed fresh方向计算原shock/range，不改过滤公式；其他hardblock明确NULL/not_evaluated，freshFalse不等于0收益。
- 全量后Stage008原8998ready逐点epoch/ready/raw/方向/fresh/RSI完全一致。实际panel SHA444899cdd5c5b6dbfe7554a78e8d57a89836cfbffda79b2983c3e3e90dd4143c。输出outputs/stage040_daily_source_panel/{daily_source_panel.sqlite,summary.json,bindings.json,pilot.json,stage008_comparison.json,status_counts.csv,checkpoints/}。
- API panel unique(exchange,product,eval_date)，epoch/day另索引；0/1布尔/NULL未知；本表仅asof代表，持旧contract日bar/history必须cleanDB按held epoch取，不可偷换新代表。catalog与共同calendar不作历史上市/session/PIT资格；source truth/经济/分钟/C2均未由本步认证。
- root已获schema与全量路径，将接Stage042月末flat冷启动future60覆盖诊断；独立review由root安排，不以本作者5tests/73pilot/8998regression替代独审。97实际有数据/98catalog的缺失域保留，_F不与普通混训。
- 模型/alpha参数新增修改删除无；半R/retry仅训练源关闭、C2保留，正式代码/池/CTP/scheduler未改。金融回放、fit、labels、下载、订单0。权益/收益/最大回撤/Sharpe/滑点/真实交易次数/胜率N/A。
- 调研判断沿Stage005/008映射、Stage010/021官方vn.py/GitHub与source合同：逐日asof选择和未来成熟识别必须分离。开始/结束新增收益选参过拟合否，无收益挑选或调参；继续价值是，连续fresh source的逐日输入已可复验，但尚无预测力或收益改善证据。
