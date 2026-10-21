# Stage129：EMA限价Task1纯特征与独立状态组件

- line_id：`futures_trend_triple_screen`；当前模式：day；记录时间：2026-10-18 09:30 CST。
- 工作区：`/Users/mac/Desktop/fian`，沿root指定同分支；未执行Git命令，未建worktree。
- 阶段性质：Stage127 Task1组件实现与两个具名fixture组合验收。是否重要突破：否；不认定alpha、金融readiness、A/B/C臂或生产资格。
- 先读registry、Stage124/125/126/127、Stage128实施ledger及TDD技能；registry尚未列本已存在研究线，未新建重复线，未修改LINE或registry。

## 外部调研与判断

承接Stage121/123/124已经完成的原著、作者官网与GitHub有限调研，不另行联网。既有结论是EMA穿透提供结构假说，但不存在已取得的唯一作者算法；本实现明确采用root在126固定的13/SMA seed、26个有效bar、positive-only、DAY和独立身份。当前Task1只实现因果组件，不按任何收益选择参数；不声称Elder原样复刻。

## 本次变更

09:25—09:30新增本线`tools/stage127_ema_limit_model.py`与`tools/test_stage127_ema_limit_model.py`，未修改或删除旧源码。

实现`load_bound_daily_csv`同一次只读bytes核SHA后直接解析，canonical列为date/vt_symbol/OHLC/volume，每row绑定source path/SHA、qualifier SHA、精确合约日期key与真实未复权价口径。冲突/重复key、未获外部qualified key、已知连续符号或不符schema拒绝；本工具只引用资格，不授予资格。外部真实源仍由root后续交付。

实现`build_ema_rows`，每合约独立seed，缺失应有session或无效OHLC清段重暖；第13根首个EMA，至少38根才有26个有效EMA。均值分母只计严格正穿透，侧无正数不生成quote；只使用u及以前数值。`limit_quote`以十进制做多向下、空向上tick舍入，未知tick无单，无fallback。

实现`EmaLimitSetupMachine.on_close(observation,quote)`、`cancel`、`on_fill`。原周/FI准备顺序、同日只观察一次、未知周/FI/资格/持仓清准备保持；EMA unknown只无第三层单，未成不消费，DAY到期拒绝旧fill。目标合约改变清旧准备，新quote必须同u、同合约。全部外部epoch/setup/intent都带`stage124_ema_limit_v1`新namespace，不泄漏B owner，`native_signal`只许None；真实当前DAY fill消费一次。

新增参数：无可扫参数；13/26固定于既有定义，execution_tick为既有输入，rank为intent所需字段（observation可选非负整数，缺省0）。修改/删除参数0。新增/修改/删除回测结果均0。只临时tinyCSV和原生Python纯对象，未构建真实全历史特征，未读取B目录或PnL，未操作provider、进程、账户、API、凭证、训练或生产。

## 实际验证与六项证据

实际命令与全部终态见`outputs/stage129_ema_limit_model_component/receipt.json`。首轮RED chunk`925044` exit1：两个具名测试都因组件不存在的明确断言失败；首轮GREEN`bdb4aa` exit0。边界自查曾观察`c06463` exit1（weekly unknown被quote方向检查阻断的错误，未冒充断言RED）；将该行为写成明确失败断言后`e5af7a` exit1，修正仅在已知±1周方向时校验quote方向。最终同命令`a500e1` exit0，2 tests/0.011秒；两文件py_compile一次`76444f` exit0。未重跑旧suite，符合root本次限定。

1. seed/窗口：close1..13手算seed7，第14根EMA8；第37根不ready，第38根ready且26有效EMA；缺口/无效OHLC后重新38根。
2. positive计数：多侧2个正穿透均值3，空侧2个正穿透均值7；tick0.4时多96.8、空107.2，零值未进分母；另一真实合约EMA1000独立暖机。
3. u未来毒化：u后OHLC改为10亿以及只给u前缀，u完整feature均零差。
4. 源SHA：tinyCSV `a47419bb823dd35f6d8f4bfed581db3d1dedb1cdee2be4dd27a6085c9d706cf9`；只读一次bytes后文件即被替换仍从原bytes解析，下次旧SHA拒绝替换文件。
5. epoch/身份：新合约取消旧准备；旧合约quote在状态变更前拒绝，全部公开ID新namespace，与同输入原027 B不同。
6. 消费：EMA unknown保留准备，未成后次日新intent不消费；过期/错DAY/重复fill拒绝，匹配真实fill消费一次。

源码SHA：model `6568f87ec74bebdb9afa730b3347c5eb52cdf31bd8f3ca3cc9208b1c55c2f7d6`（17347 bytes）；test `b801b79205fa23e6ab0aa8b5a2827c848a0c79bf6608ccfdea2819e865783bce`（12650 bytes）。

## 结果、限制与后续

`fixture_only=true`、`financial_replays=0`、`model_calls=0`、`provider_calls=0`、`network_calls=0`、`production_qualified=false`。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A；无金融结果可用于策略判断。

本组件通过只证明两组纯契约；真实同源日线资格、冻结DB导出、执行tick在u可知、金融owner、账户定价/预算/原生fill及后续经济接合均未验证。继续由root完成Task2/4和一次整体独立审查；本agent不另派审查、扩金融波次或创建runner。LINE/registry/总账不改，由root按必要范围汇总。

开始/结束新增过拟合判断：**否**，没有读取收益、跑金融或扫描参数，只按收益盲固定定义补组件；历史研究选择偏差仍存在。开始/结束继续价值：**是，限于固定语义组件及后续必要真实接合**，可直接防止未来泄漏、错误暖机与身份混用；不等于alpha成立、金融就绪或目标完成。
