# Stage040：B 实际请求所缺日线的最小补齐合同

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18T03:55:32.465308+08:00；本阶段不是重要策略突破版本。
- 所属授权：用户持续自主三重滤网迭代目标；仅离线研究数据，不推送、部署或连接 CTP，不写邮件。
- B_TS attempt1 保持同一引擎 `70433/PID21822`，金融尝试累计8、已接受账户3；不重启或用日线价格替代分钟成交。

## 实际问题与冻结范围

- 实际 request digest：`53e251e1034a04c76c81f26838eec78388484bf2c14742953fb9efecfce040ae`；request 文件 SHA：`f7ba04a28e5b0f99d695c567415c681c91cbd62672bd0469f4034e832302f420`。
- 需求只有 `SM005.CZCE / 2020-01-06 / full_session / 225分钟`。Stage037 prepare 正确拒绝 `qualified_daily_reference_missing`，尚未创建 packet、未连接 provider、未更改输入。
- 原 SM005 日线 CSV 和 Stage013 已批准目标均无此 key。只读主 DB 有精确合约日线 OHLCV=`6378/6380/6262/6280/76307`，open_interest=`68372`。历史 importer 已证明 DB.open_interest 对应 provider.open_oi；DB.closeOI 是 N/A，禁止误当收盘持仓量，也禁止连续 SM.CZCE 代替精确合约。

## 最小实施

1. 单独 Stage040 adapter 从上述实际请求提取唯一合约/日期，读取绑定 SHA 的既有 DB 六值；沿用 Stage013 的正常日级 SDK、86400秒快照、10000长度及真实后继资格算法。
2. prepare 与 run 分离；正常凭证仅本地读取，禁止回显或保存。SDK、端点、鉴权实现不改；1个连接/1个 attempt，570秒soft、600秒hard、1.5GB守卫。原013/037、正式策略和行情源不修改。
3. 只资格实际请求日；源快照天然附带其他历史条目不代表其自动取得资格。保存 raw + 后继证据、六字段比对、closeOI来源/N/A边界和输入指纹，独立日线审查后才允许被后续分钟 provider 引用。
4. 分钟全日225仍必须完整canonical grid、已完成后继、七值日聚合匹配、原key不变及独立签收；不可从anchor提升权限。
5. Stage040不签独立receipt或engine response。root观察真实terminal exit0后通知独立审查者，随后独立作用域 provider 引用新日线收据；原引擎只接受合规Stage021交付。

## 参数、结果与反思

- 策略参数新增/修改/删除=0；已有回测结果新增/修改/删除=0；期末权益、收益、回撤、Sharpe、滑点、交易数、胜率=N/A（本阶段无金融引擎）。
- 过拟合判断：否；仅补已冻结候选真实下单路径请求的数据，不查看收益选日期、品种或阈值。
- 继续价值：是；是完整B实际执行资格的必要输入，保持同一进程和公平成交。若真实数据不能验收则保留失败，不以假价救回测。
- TODO：唯一日线snapshot真实终态→独立日线资格→225分钟交付→同一B引擎继续→真实终态后038独立账户复算。
