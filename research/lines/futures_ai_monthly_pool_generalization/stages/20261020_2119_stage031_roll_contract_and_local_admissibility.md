# Stage031 换月合同与本地shape/delay helper

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:19 CST；day。
- 机制进展，非重要收益突破。先读registry、Stage030、Stage021/022，参考VeighNa官方GitHub target/actual position模板；本地绑定才决定delay/shape规则。
- 只写本项outputs、helper/tests及本stage；未改LINE/registry/正式策略/配置/数据。

## 映射结论

冻结m0008与当前18方法中17 AST相同，on_bars不同；不声称全源等价。有效roll delay5、target_contract_only、shape同方向MA5/10/20/40+MACD、shrink_to_allowed。首次发现目标elapsed0，distinct处理日期+1、同日幂等、改目标重置。等待管理旧仓日退出不加层，due先roll后普通退出。旧当日bar缺失保留unknown；旧bar有而新目标/history/shape不够仍先排old close再不重开。

“先平再判重开”是D.close策略内部顺序，非实际两腿原子成交；两腿各自next-session open/physical anchor。当前引擎chronological queue不得被同时fill或D.close价格代替；root若选old-fill确认后new-open是额外研究约束，须明示。新stop用target D bar/history，D+1新entry独立算C2 R/重置入场日，episode初始currency-R不变，跨合约价差不算PNL。

完整正式qty取min(旧量,账户selected量)，后者依账户margin/equity/cluster/风险门。固定外部整数qty只能作新研究delta，不能冒称正式shrink_to_allowed。新helper不处理账户qty、完整shock/range或其他非账户硬门，也不识别完整asof mapping。未来driver须消费这些门，不能从shape allowed推出formal complete。

## 新增实现与验证

新增`tools/stage031_roll_admissibility.py`和12项测试。纯shape AST+MACD来自冻结并核manifest SHA；effective short=True读取build setting覆盖base False，参数MA5/10/20/40绑定。`evaluate_roll`要求41合法正OHLCV、strict ISO升序dates/末日绑定；calendar连续性、contract身份、历史经济PIT由root外部核验，返回资格False。不生成订单或actual fill。newstop复用Stage012冻结Stage804 host。

`advance_delay(previous,target_contract,day)`5从Stage037配置读取；首次0、同日幂等、目标变更清零、拒绝倒序和非法状态。不认证被计日期是真交易日，不将日历距离计数。

TDD先12 assertion失败，再12通过。21:18:56单次4组合成shape/stop fixture、8个delay观察落盘，非金融回放。全线discover在Stage034并行施工时95项：94项通过，唯一error是test_stage034_episode_driver导入尚未创建module（完整日志保留），root完成后须复验，当前不报全线绿。Stage035独立复核待root安排/接纳。

新增研究API/资格字段；正式/模型alpha参数新增、修改、删除0，金融回测结果新增、修改、删除0。权益、收益率、最大回撤、Sharpe、总滑点、交易次数、胜率N/A；真实金融回放、模型fit、净60日标签、下载、订单、生产修改均0。

## 反思和下一步

开始/结束新增按真实收益选参过拟合：否；只冻结既有规则、合成路径验证、不按收益选择参数。历史数据/分钟覆盖选择偏差仍存在。继续价值：是，避免把fixedepoch或临时目标误作完整换月和收益。下一步由root将外部mapping+逐日driver接此局部helper，所有unknown保留；独立review后再讨论60日成熟，不从本项宣称可训练。

详细合同、最小外部已识别roll请求接口、拒绝/unknown、AST依赖、配置覆盖与哈希见`outputs/stage031_roll_contract/README.md`、bindings/configuration_bindings/external_request_schema及synthetic run。
