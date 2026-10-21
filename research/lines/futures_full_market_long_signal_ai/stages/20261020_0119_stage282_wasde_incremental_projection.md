# Stage282：WASDE 新11原件增量投影并合并（0 fit/cash）

- 时间：2026-10-20 01:19 CST；本线 `futures_full_market_long_signal_ai`。不是金融突破。只新增本282工具、输出与记录，不改LINE、registry或旧源码。
- 调研与判断：沿271官方/维护者原始方法研究、274固定quantity以及276 core0接受的275提取方法；本阶段不联网、不换字段/单位/年份/版本规则。补足新来源有价值，但原件数量与可交易增量不同。
- 输入：281实际session95256已exit0，11/11成功、10,849,860B；复用275已接受的3612 Corn/World行与172报告表。273旧47原件读取/解析均0，278原件读取0；旧数量不重算。
- 实现：新 `tools/stage282_wasde_incremental_projection.py` 复用275纯`consume_csv/project_report`，不运行旧CLI。11个新CSV各一次流，原件SHA继承281、不额外integrity重hash；旧子集/report来源及全部原字段不变。一个极小合并守恒fixture RED→GREEN，验证旧字面来源不变、V2 false和缺口原因/无release日期；未重跑275量测试、旧suite或真实原件rehearsal。
- 唯一actual：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage282_wasde_incremental_projection.py --execute`；session51054，exit0，0.332559秒。

| 项目 | 新增 | 合并结果 |
| --- | ---: | ---: |
| CSV完整提取流 | 11 | 不重开旧47原件 |
| 新源记录 | 55462 | 只统计本次增量 |
| Corn/World原字段行 | 231 | 3843 |
| 报告数 | 11 | 183（WasdeNumber实际唯一） |
| 满足固定quantity及版本条件 | 9 | 172 |
| unknown报告 | 2个V2 | 11（另9个2010原unknown原样保留） |

2026-05-V2（Wasde671，release2026-05-13）和2026-06-V2（Wasde672，release2026-06-11）raw ratio保留，但`feature_eligible=False`、`correction_known_at=unknown`。candidate边界分别为2026-05-15T04:00:00+00:00与2026-06-13T04:00:00+00:00；这不解除V2未知，也不证明历史首见。

剩余来源缺口分别保存，release_date全部null，不carry/补抓：

- 273旧4失败：2023-01、2024-11、2024-12、2025-01。
- 278新增3失败：2025-02、2025-03、2025-04。
- 6未试CDN：2025-05、06、07、08、09、11。
- 2025-10目录未列单列；归档名义跨度内2013-10、2019-01未观测报告单列，不猜原因或捏造公告日。

小合并表在 `outputs/stage282_wasde_incremental_projection/actual_run1/report_projection.csv.gz`，20,180B，SHA `afe57bc59da6464860fb17a77c12b44ee593f6dc5d7608f186b22cfcba717699`。沿275的release_date/release_month、S/U/q、feature_eligible、candidate_available_at_utc、原ReleaseDate/Time literals及S_source/U_source/sources列；增加`projection_origin_stage`与`acquisition_stage`。已直接向285实施方交25列schema及绑定，未做offset join。

同目录manifest SHA `5c7d3674be3fe66a01b9cfa1f60918a766693dec3eef045473476dcb4e9e74b5`；receipt SHA `807a11258f18633e5d572a931a27ed8c74e6c0f2783ef7bce228c335c827d8c5`；source_inventory SHA `8be0d8be7e831138ec509a67ffd9b6ff2db7afc69547b2df98640a5f42af2173`。作者工具SHA `164d05f004dfb7dae644253099e8b8aa223245e32ced6737c95e3967301ba4c9`；`implementation/execution_receipt.json`记录两个实际session/exit及一次运行，SHA `1a49f0a6ae5560637f10cb8e5d5d5bedca049535f42e808568a5c6638d2fea2d`。

新增/修改/删除策略参数及回测结果均无，权益/收益/回撤/Sharpe/滑点/交易次数/胜率/费用N/A。0network/SQL/native/labels/fit/cash，累计439fit/238cash。过拟合判断：新增按成绩救参否，历史选题适应性风险仍是；继续价值为交接固定来源表和一次独审，不据此宣称PIT/alpha。独审由root安排，本作者到此结束，不继续金融或检查。
