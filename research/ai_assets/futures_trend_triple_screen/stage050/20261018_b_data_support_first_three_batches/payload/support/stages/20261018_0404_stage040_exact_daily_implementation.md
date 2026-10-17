# Stage040：精确实际请求的日线恢复工具实现

- line_id：futures_trend_triple_screen；2026-10-18 04:04 CST。非重要突破，仅为正在等待的B_TS实际缺口取数准备。
- 变更：新增独立040工具与1项聚焦测试。精确绑定request 53e251e1…、SM005.CZCE、2020-01-06、full225；仅一份日级86400秒/data_length10000快照，原始日线快照独立落盘，由013原始资格算法检查真实后继与DB六字段。DB.open_interest固定对应provider.open_oi，closeOI无独立DB来源，不允许调换。
- 正常TqApi鉴权/SDK/端点不变；原013、037、策略、DB、request只读。570秒soft、600秒hard与1.5GB上限保留；parent/worker闭环、单次attempt，禁止重试。本人未执行网络run；不签独立日线receipt、不写engine response。
- 参数新增：仅数据工具目标与输出范围；正式策略参数新增/修改/删除0。金融结果新增/修改/删除0；权益、收益、回撤、Sharpe、滑点、交易数、胜率均N/A。
- 验证：单测试先RED exit1（模块缺失），实现后GREEN exit0（1项，0.288秒），覆盖精确request拒绝连续合约、只读DB六字段、缺后继拒绝、不得用closeOI救openOI。离线prepare真实terminal exit0，0.389秒，provider connections=0；未扫旧suite，未跑金融引擎。
- 过拟合判断：否，本次仅恢复已冻结策略实际请求的数据权利，无参数/价格/过滤放宽。继续价值：是，避免重启既有B_TS引擎，以有界一日恢复补齐原037缺少的七字段reference。
- TODO：root真实单次网络run终态后，由独立reviewer验证raw日线与后继并签exact key；再由独立分钟provider消费签收来源。production_qualified=false。
- 详细SHA及RED/GREEN/prepare终态见outputs/stage040_implementation/implementation_receipt.json。
