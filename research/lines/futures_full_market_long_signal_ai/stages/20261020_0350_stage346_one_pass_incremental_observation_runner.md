# Stage346：u19一次观察root runner准备

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 03:50 CST。非重要收益突破、非正式A/B/C。
- 本阶段只交待授权实现，0actual；未读343实际date_rows/raw_index、331状态/inventory、calendar数组、roster或经济投影内容。0行情API/SQL/native cache/fit/cash/forward/T0/资金state，未重跑339或其他旧组。
- 调研判断沿已接受335/337，无新增网络探测。接线有价值，但不增加AI优越或alpha证据。

新增[runner](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage346_incremental_observer.py)、一个[loader synthetic组](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage346_incremental_observer.py)及[未授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage346_incremental_observer/implementation/authorization.template.json)。不改339/325/343、344实际目录、LINE/registry或其他线。

## 固定接线与接受范围

直接绑定337总actual_receipt（6020B，SHA `8c86c62d94d86cefaa6f4cb4fc06652bea4bcc5fc0ba3b10ac34cddf16bff697`）的本批u19 factor1范围。runtime一次读343 date_rows gzip并校验同次读取的bytes/SHA，筛`2026-10-19`；geometry按finite正OHLCV、合法OHLC关系及closeOI非负或None，不用商品名dict去重。865个u19行只允许726明确身份/有效行入overlay；13身份未知有效形状、126无效/零量均保留拒绝原因，u20与所有其他日期不入。

另经root明确授权一次读343 raw_artifact_index（153911B），把symbol/rawSHA/received_at与原完整321receipt精确join。每accepted行保留原native_values、missing列表、raw位置/SHA、343行SHA、原321receipt与337接受binding，显式写volume/OI factor1；原closeOI missing保持None，不填0。343文件本身的provider_raw_units_unverified与raw资格不修改，新的accepted只是337限定的独立overlay。

runtime再各一次读取331的744 final states与完整9520 inventory，原5587源calendar、98/95roster；原econ8MB最多一次json load，继承原SHA与stat而不预hash。model/scaler小JSON各一次。确认原source坐标u16=5288/u19=5289/D20=5290，调用339时注入`caller._components().core`；713精确前u续接与13已知gap起点计数必须吻合。未知新经济/lifecycle依旧未知，不借factor1授予代理经济参数。

使用原325 observe_only、states=None，unknown source_completed_at/D_open_at保持None，T0=None。D日期已确认不等于D首开时钟已知。model journal是新独立目录，由原321实际UTC追加；不把原receiver receipt冒称本次模型决策时间。返回activeFalse/statesNone并检查new_state/advance_D/seal_u三接口调用全0，不重训、不回放资金。

## actual授权后才产生的输出

runner写canonical_overlay/receipt、u19_rejections、完整result及current_economics（从本次RAM导出供独审）、continuation_evidence（before/新bar/final，含713+13）、epoch_inventory与warmup_state供下一日、source_receipt、terminal和唯一model_journal。独审可用新compact复算Wilder/26raw/52设计/score/母选择，不必再读旧cache、SQL或第二次econ。source receipt保留原338 partial与原时钟未知，不把新计算完成状态升级为全市场源完整/PIT/forward资格。

授权模板`authorized=false`，sources/输入exactbinding均已填；root只需设为true并指定fresh344实际目录。入口：`.py311/bin/python tools/stage346_incremental_observer.py --execute --authorization ROOT_AUTH`（文件实际位于本线tools），或`module.run_once(auth)`。本agent未执行入口，不创建344目录，也不轮询其结果。执行失败由terminal记录failed_no_retry，不自行改口径或重试。

## 唯一新组与冻结

loader组先RED（runner缺失），再GREEN1/0.039秒；只检查factor1值不变、missing保留、原321/343来源、unknown/zero/u20排除与重复/来源不符阻断。未mock或重测339数学；自有两文件py_compile及help exit0。GREEN后仅把stat门前移到fresh输出创建前、current_economics导出复用原caller._clean；无策略修改或新增测试组。

| 文件 | bytes | SHA256 |
|---|---:|---|
| stage346_incremental_observer.py | 15753 | `fcc865ec122dab8a51c21f99490ecf5359ae19a477286611c59c0a22772fa695` |
| test_stage346_incremental_observer.py | 3812 | `445743e881923dd66eb658cee6130841d68a2ac08ab54428286131a2ac20ad4a` |
| [source_bundle.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage346_incremental_observer/implementation/source_bundle.json) | 2359 | `255efc28420deef41ab64adccedb728b881e54d89058046fa37a4313a8126957` |
| [fixture_terminal.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage346_incremental_observer/implementation/fixture_terminal.json) | 938 | `79b374e3c72928e3b9b3c5ed513dd8d4698a9c427d12b655f01b544ab3a60b1e` |
| authorization.template.json | 6909 | `0a2884d323e5ec481352bc93d4df4afe8c4502d5d127dedcd3e6f26917eed598` |

已交root和337作一次新源静看，随后actual由root独家授权。没有本轮金融成绩；权益、收益、DD、Sharpe、滑点、交易次数、胜率均N/A，累计fit/cash不变。开始/结束反思：本次没有按收益寻优，旧政策选择偏差仍在；继续价值是完成一次接收→状态→观察接线，而非据此重开历史参数搜索或宣称完整用户目标已达。
