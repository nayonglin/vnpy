# Stage105 含周门完整复盘与失败状态总览独立展示审查

时间：2026-10-20T02:18:28.343807+08:00。结论：**PASS_WITH_LIMITS**，P0=0、P1=0。本审查只验证既有冻结展示，不重跑金融、不改源码/结果/LINE/Git、不下载行情或访问生产；无新增金融参数，不是策略突破。浏览器交互由root实际CUA记录提供，本审查者独立核数字/代码字节/PNG，未冒称本人操作GUI。

最终复盘：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v3/index.html`，SHA `382abac2b94232f0b485da6c4246ff9f3d1a6b36b081a64573da919c4571edee`。最终状态总览：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/overview_20261020_risk025_v1_status_v2/index.html`，SHA `02418a64ea4054dc884078495123167bbf8b0159151262f5a0b0b493f83ca6d1`。两者均绑定金融源manifest `7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35` 与Stage101实际审查JSON `3a0ba1efa4d54e887dc7862ee4be48baab0dfafd3b38952ceb0b2de29f7f950e`。关闭臂原失败无完整manifest，本报告不拼接或比较其前缀收益。新容量退出共同模型仍未获范围答复，未实施或重跑。

## 完整复盘独立计算

从实际fills重新配对完整原entry：1311笔/6974手，残余7entry/29手；全部成交成本254660.2554227874，其中未平entry成本564.75434已计账户、不重复分摊。真实数量、gross/net盈亏、整entry成本、R=毛价差/实际接受整笔初始止损风险逐条对账，不把每手或分平算独立样本。12个完整entry含分平，加权退出与最终退出均不同；最终紫点全部等最后一笔真实成交价，价格涨跌仍按所有退出数量加权价，日期与源一致。

毛价差筛选分类426盈/880亏/5平；扣成本净分类418盈/893亏，净胜率31.884057971%。二者明确区分，避免用毛额筛选误称净胜率。raw→094非风险数据、094→095非周数据受保护；最终records与weekly版本原字节相同，SHA `99a5aaac295e92fc226cd466e724fbd581b6bf13884c71a4d8a3be16a94d992b`。

独立完整calendar+exact accepted-clean日bar重建1004个真实合同、96857个显示周槽，保留35778缺槽；484285 OHLCV与387428 MA值全部对齐，最大绝对差0，不压坏周、不用其他合约补历史。15m真实bar为0，缺分钟/上市截断/其他周期背景或退出报价按页内原说明保留；不把全部背景K线当全段exact。

root CUA发现旧v2排序选项写“净利润绝对值”，实际算法按毛额。这一P2在v3只改两label并加普通说明；本审查独立反替换并移除唯一说明div后，精确还原旧HTML SHA `b0eca000d4af4b1af0f7868127da7c46bd267cec2b4e6a9136088c6990b74a48`。15个原非HTML文件、所有JavaScript文本均逐字节未变，新的v3再经Node语法验证3块通过，R/图/交易顺序未变化。

## 状态图与来源

2862个每日权益点独立按100万+cumsum(netPnL)重算：期末809719.744577212、总收益−19.0280255423%、最大回撤−37.1119680089%，峰2015-07-08→谷2026-09-21，期末回撤−34.4747980389%。图为3条全长曲线（权益万元/历史高点万元/回撤%）+1个最大回撤点，共4traces；每个值/日期、CSV/native DD、坐标单位、shared x、嵌入HTML JSON与figure.json一致。13项指标按冻结源显示；关闭版全部未完成/N/A，无假数据、替代曲线或排名。毛账户损益64380元减全部成本254660.2554227874=净−190280.255422788，属于同账本成本解释，不是新的去成本回测。

新status_v2的figure.json、CSV、PNG均与已核原status逐字节相同，HTML仅把复盘链接v2→v3；source review/失败MD+JSON/方案和当前provenance绑定通过。PNG2240×1200签名、全部chunk CRC通过，本审查者已直接view_image核清晰度、标题/单位/两面板和标记；没有关闭臂数据。状态脚本初次PNG库缺失仅是本地审计环境，已用标准库重做并保留失败日志。

## GUI证据与边界

root实际CUA记录：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/stages/20261020_0216_stage106_risk025_enabled_and_status_ui.json`，SHA `ee736f073cae6e6733a7eaed5cd4f98aaa501def9a2814e9e1e8996cb4103c1a`，状态PASS_UI且页面hash等于上述最终文件。记录含1311options、默认30日+日、2024亏损92笔、跨笔next/prev、rr202409 short35的真实qty/gross/net/cost/R；三周期6subplots477candles的zoom→Reset恢复当前2023—2024记录原18ticks，未跳首笔；新gross文案可见。status_v2的linkv3、13 N/A、4legend及缩放/复位通过，两个最终页error/warn日志空。这里引用rootGUI事实，本审查者没有另行GUI复测。

静态实际脚本/结果/日志共17份原字节在`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/stages/20261020_0218_stage105_actual_enabled_display_review_audit_code`，含独立081原算法及明确季度适配，SHA逐项在配套JSON。未把094—097作者PASS用作自己的oracle。

本页只是一完整一失败状态，不构成完整两版比较。日线/C2C9停用、缺供需过滤、静态非PIT费率保证金、AON容量与名义stop预算不保证gap退出仍沿Stage101；展示成功不产生alpha、样本外或生产晋升证据。

过拟合反思：本次展示核验否，没有金融改参/重跑/选样；源实验已有样本内选择风险，保留真实负结果与失败臂N/A。继续如实保存展示与修正文案有价值，新共同执行模型仍待用户范围决定。
