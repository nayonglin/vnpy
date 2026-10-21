# Stage144：ECB汇率归档内容独立核对

line_id=`futures_full_market_long_signal_ai`；2026-10-18 23:47 CST。有限来源内容复核，非模型/资金复审；非重要突破。

**结论：保存归档→归一表→content_receipt 的内容一致性通过，20项检查全真；严格PIT与alpha均未证明。** 使用 `.py311/bin/python`、仅stdlib，一次独立解析真实ZIP和完整CSV，自行重建结果；未调用作者解析器或修改其产物。

| 核对项 | 独立结果 |
| --- | --- |
| ZIP与成员 | ZIP 641,332B；仅 `eurofxref-hist.csv`，解压1,927,337B；`ZipFile.testzip()`及独立 `zlib.crc32` 均通过；大小/SHA与receipt一致。 |
| 全日期 | 7,116行，1999-01-04—2026-10-16；原表及归一表均无重复日期，周末0；归一表逐行升序日期与完整原表一致。 |
| 交叉汇率 | 每条原始有效值均有限且>0；逐行用 `CNY_per_EUR / USD_per_EUR` 独立算得 `CNY_per_USD`，方向正确。18,150个非缺失数值逐格一致，最大绝对差0（容差1e−12）。 |
| 缺失不填0 | USD缺失0；CNY缺失1,599，故交叉值缺失1,599；归一表相应3,198个数值格均为空串，无0替代。共同可观测5,517行，首日2005-04-01。 |
| 全年表及收据 | 按原表重建1999—2026全部28年rows/both_observed/missing，逐年全部一致；首尾各3行、weekday、date range、计数、CSV schema、大小/SHA均一致。 |

覆盖缺口有明确时间结构：1999—2004全部1,537行缺CNY，2005年257行中195观测/62缺失；2006年起原表已有日期均有USD和CNY，2026仅截至10-16的203行。没有周末不是完整交易所或中国source日历证明，未生成空缺日期或前向填充。

绑定：ZIP SHA `8e925cef1572f8df5c8743229a761b029180f3b5cd4aa2213592192964ebd793`；成员SHA `657984b9cbe43e25c83481d0f05bc62435c5f54dda13f181091a8d18dd6f8673`；归一CSV SHA `3bf305bdac89247d35ca2943299d6808f0ee8a20ce314882f621c216f8e7686e`；核对的receipt SHA `4efe936bc753199ab7db552b087c700baa1303177063d15b928a1a4ee2b69445`。文件均在本线 `outputs/stage144_fx_source/`，原receipt未改。

接受范围仅为本机保存的ECB归档字节、数值变换及元数据相互一致。没有重下载或独立网络取证，不重新证明传输身份；当前archive不等于历史首次发布vintage。参考交叉汇率不是可成交价格；历史修订、首次公布/可得时刻、中国夜盘时钟及机会母体绑定仍未验收。receipt内 `training_accepted/strict_pit_accepted/financial_experiment_authorized=false` 保持，不能由CRC或算术通过升级。

开始/结束按收益调参过拟合：否，本次无金融结果或参数选择；同史多轮择题风险仍有。继续来源/可得时点的有限资格判断：是；直接据本核对启动fit/cash或主张收益优势：否。新增参数/回测0，权益、收益、DD、Sharpe、滑点、交易次数、胜率均N/A；本次0下载/SQL/fit/cash/旧大库/代码修改，仅新增此唯一stage，不改原novelty、LINE或registry。
