# Stage001 独立19品种日K追加数据准入

- 时间：2026-10-29 19:57 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate。
- 状态：`PASS_BOUNDED_DATA_ONLY`，金融回放0，CTP/order/cancel=0/0/0。非重要突破。
- 新工作区 `/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian`；本数据仅本线使用，未读取或修改正在进行的44品种快照。

## 固定来源与追加

以另一工作区Stage032截至2026-10-28的已批准原19快照为冻结历史，复制本线独立SQLite等文件。10/29仅采用预声明Tq真实daily serial的OHLC、单边volume和同日close_oi。原始serial、fresh continuous table和日历完整保存于本线 `outputs/data_stage001_20261029/raw/`，凭证只内存，不写文件。

- 独立数据目录：`outputs/data_stage001_20261029/data_approved/`。
- 原批准physical行392169→392197，新增10/29真实正量日K28条。
- SQLite全历史行1345729→1345757，原整库所有字段逐行EXCEPT无缺失，新增28条逐字段与raw精确一致，integrity_check=ok。
- 新主力mapping19条，10/28观察与冻结主力映射19/19一致；10/29没有新增合约元数据。
- 最近28日K尾合约、原A末4持仓和空pending清单共同组成请求28合约；必需主力及持仓键19个，缺失0。新28条全为正量有效OHLC且physical epoch唯一并符合生命周期。
- 冻结10/28原始28合约OHLC/volume/close_oi与本次同源观察没有差异；即使有差异也不覆盖原值。
- metadata和physical_epochs原字节保持；原physical/mapping CSV字节前缀和全部字段保持。
- 批准数据不包含10/30形成中日K；批准截止10/29，下一交易日10/30仅作为日历知识，10/29仍非完整周。

## 验收与哈希

`tools/stage001_data_prepare.py`使用冻结Stage032准入辅助；另一份`tools/stage001_data_verify.py`只读重算旧CSV/DB保全、原始数值、epoch、日历和78个直接绑定文件SHA，全部通过。

- daily.sqlite SHA256 `c0dfd9a238901a4630cf23dbb6beffb5d689b1b6366e5f76d6d228a59c6472f3`
- mapping.csv SHA256 `bc8e436b9a07ce5f3488fc03d753a5428dce5eda5610436c439882678126b91c`
- physical_epoch_daily.csv SHA256 `5caff2449302d3a600a9bdb73c99288cd8fd92be22fc2c2238058e931021c014`
- receipt.json SHA256 `6a67452119f715556a113c2bb25c92400038ecb99b3a802ed60024f02fce6a22`
- source_manifest.json SHA256 `128f292400711da985770ec2ab3b3ea16c2fae128ffa0db8dfc8b0fe43fbe814`

本manifest直接绑定独立数据/raw和原快照/工具/旧A持仓输入78文件；更早2600余来源通过冻结原source_manifest哈希继承，本次不声称重新独立仲裁所有原始历史行情来源。

初版验证器错误要求继承的全部mapping只有19池，因此失败；原批准历史本来含91池历史mapping，实际金融宇宙仍原19且新追加仅19。已将检查修正为“历史mapping逐行及全集保持、新追加原19完全一致”，保留 `stage001_data_acceptance_initial_validator_rejected.json`。数据及金融规则均未改、无重取数据。

## 边界和后续

这只证明冻结数据一致性和本次日K追加符合合同，不证明交易所终值、全段PIT、未知生命周期、盘口容量、真实历史券商保证金或策略正确。2014及2019自然历史仅供预热，账户仍需2020独立15万/0持仓启动。每臂仍须检查所有实际持仓/成交日、周源日、物理epoch及财务账本，不能仅以本数据准备成功代表新路径必然完整。

新增参数：数据截止10/29、只追加本日。修改/删除旧行情和旧回测：0。新增回测：0。运行前后没有策略调参过拟合；价值在补齐真实最新完成日和维持可复验历史。下一步由主agent运行固定A/C并安排独立全面审查，NO_PROMOTION。
