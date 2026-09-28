# Stage000 全市场PIT数据源重建预注册

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 当前模式：day
- 记录时间：2026-09-04 11:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：数据源重建与无标签覆盖审计合同；不是模型、标签或策略回测。
- 是否重要突破：否。
- 是否触发A/B：否；本阶段不生成策略候选。
- 用户授权：2026-09-04明确回复“授权数据源重建”；授权范围仅为本Stage001线内数据重建与无标签覆盖审计。

## 外部调研与判断

- TqSdk `query_quotes` 官方文档说明 `expired=None` 同时包含已下市和未下市合约，旧脚本使用 `expired=True` 实际只查询已下市合约：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html>。
- TqSdk `TqBacktest` 官方文档说明回测起止日使用北京时间，K线在创建和结束时更新，可将目录与历史 serial 绑定到固定时点：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>。
- TqSdk `DataDownloader` 是专业版精确区间下载能力；仓库 Stage856 已记录当前账号被该权限阻断，因此本线不用权限失败接口作为交付前提：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html>。
- TqSdk 官方 GitHub `api.py` 是 `query_quotes/query_symbol_info/get_kline_serial` 的上游实现参考：<https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py>。
- 我的判断：旧源失败不是XGBoost或排序逻辑问题，而是“已到期合约快照 + 固定4月映射 + Stage173只续正式19品种”混合形成的尾部选择性缺口。应先用同一生产者、固定截止日、线内产物重建，不能降低模型门槛来掩盖数据缺失。

## 已知根因

1. `download_tqsdk_all_futures_daily_csv.py` 的 `query_quotes(ins_class="FUTURE", expired=True)` 只抓已下市合约；且已有文件直接跳过，不能增量延展。
2. `export_tqsdk_all_futures_main_contract_mapping.py` 将终点硬编码为 `2026-04-30`。
3. Stage173只为正式19品种续写同名“all_futures”映射，导致 `2026-05/06` 全市场映射实际降为19品种。
4. 上一研究线末段合格品种为 `17/5/4`，池外挑战者为 `0/0/0`；这是现有源身份下的有效失败，不允许在旧线上重跑或降门。

## 冻结输入身份

1. 正式排名身份列：`formal_full_ranking.csv`，SHA256=`b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0`；只读 `eval_date/product_vt_symbol/score_rank/score_type`。
2. 旧归档目录清单：`_symbols.csv` SHA256=`620f6af9aeddcb9c575c82f28c76dcde2beaabc36199a9d778d3c7912163ea2d`。
3. 旧归档状态：`_download_status.csv` SHA256=`710b28800f8134c25a786d62bc696cdbe858a7a7f75debe2fa92cb6261b8920f`；仅作法证，实际复用资格必须逐文件重算日期与SHA。
4. 旧归档摘要：`_download_summary.json` SHA256=`754b5bd227da5b410a5cc80ce977ca75c0f3e8b5b961659432f95ddc46fa032d`。
5. 旧共享映射：SHA256=`1fa32afab0bc9a490711aa66a716fa78fd52ebbb2c1680d77ce20eadcad617c2`；只作根因法证，不作为新映射输入。
6. 上一覆盖结果：`stage001_summary.json` SHA256=`7d1ea1bae0472243e6c9b9b6ad88a52b522a593dacbb840a84cc5b71a9632b93`；只作门槛和失败对照。
7. 冻结覆盖核心：`full_market_coverage.py` SHA256=`f5751bea61b736d89848b228eee03959465a0be82ee007614eb4e80ecf072194`。

## 实现与测试身份

- 纯数据合同：`tools/full_market_source_rebuild.py` SHA256=`ea177b374354ee6e29e106322e6f3ac266617d1097ce67ed3393bd86a0a82161`。
- Stage001 runner：`tools/stage001_full_market_source_rebuild.py` SHA256=`f2b40ed7c36041e9fcc79fbadae43beef8bdfc2f184d3ab27d531f32f10d91e9`。
- 核心测试：`tests/test_full_market_source_rebuild.py` SHA256=`434edc6e1879acc0c727602293c49bd2f226d38ea169bebd5954a770acf08e1c`。
- runner测试：`tests/test_stage001_full_market_source_rebuild.py` SHA256=`d876118667c50f0dce045fb38676f14e30daaf201159f854777a99cab0cfb8c5`。
- TDD证据：模块不存在时收集失败；归档扫描、执行入口和恢复函数缺失时分别失败；当前限定测试 `17 passed`，`py_compile`通过。

## 冻结数据重建合同

1. 数据起点固定 `2021-01-18`，截止日固定 `2026-06-30`；不根据覆盖结果改变。
2. 截止日目录：`TqApi(TqSim(), backtest=TqBacktest(cutoff, cutoff))` 下查询 `FUTURE`，`expired`不传，交易所只允许 `CZCE/DCE/GFEX/INE/SHFE`。
3. 主力映射：从截止日目录生成 `KQ.m@` 品种列表，用 `TqContCalendar` 精确请求整个固定区间；每个非空主力必须存在于截止日目录。
4. 日线复用：只有截止日已到期且旧归档文件存在、可解析、日期不重复、SHA已冻结的合约允许复用。
5. 日线增量：截止日仍存续的所有合约，以及主力映射必需但旧归档缺失的合约，必须用截止日单日回测 session 的日线 serial 获取完整历史，并写入本线 `raw_incremental/`。
6. 任一增量文件存在未来行、早于固定起点、重复交易日、身份不符或SHA漂移即失败；中断恢复必须重新验证文件内容，不能只看文件存在。
7. 合并日线使用具体合约 `open_oi`，不使用连续合约行情；同一合约日期值冲突即失败。
8. 产品元数据只有在该品种全部截止日目录合约的 `price_tick/volume_multiple` 不变时才发布；变化品种保守判为元数据不合格，不用当前值回填历史。
9. 所有新增文件只允许位于本研究线；共享映射、共享数据库、生产目录写入计数必须为0。

## 冻结54个月覆盖硬门

- 评估月：`2022-01-28..2026-06-30`共54个月；每月18名、rank连续、静态并集18个。
- 每个品种：至少252个主力映射日；最近252个映射日有效close至少241；最近60映射日close/volume/OI同时为正比例至少90%；评估日同日具体曲线合约至少2个。
- 一手门：固定资金 `150000`、保守保证金率 `15%`。
- 每月全市场合格商品期货至少30个。
- A-rank10至少36个月合格。
- 每个A-rank10合格月至少10个池外挑战者。
- 未来映射/日线使用、fallback、CFFEX合格、重复键、标签读取、fit/predict、策略回测、CTP、订单API、生产写入全部为0。

通过决策：`stage001_source_rebuild_coverage_pass_allow_new_model_preregistration_only`。

失败决策：`stage001_source_rebuild_coverage_fail_close_no_model`。任何硬门失败后，不得删除末段、退截止日、降低30/10/252/241/90%/2合约门，不得按产品或已知收益补洞。

## 预期输出

- `artifacts/stage001_full_market_source_rebuild/asof_contract_catalog.csv.gz`
- `artifacts/stage001_full_market_source_rebuild/pit_main_contract_mapping.csv.gz`
- `artifacts/stage001_full_market_source_rebuild/archive_inventory.csv.gz`
- `artifacts/stage001_full_market_source_rebuild/acquisition_plan.csv`
- `artifacts/stage001_full_market_source_rebuild/raw_incremental/`
- `artifacts/stage001_full_market_source_rebuild/normalised_daily_bars.csv.gz`
- `artifacts/stage001_full_market_source_rebuild/monthly_coverage.csv`
- `artifacts/stage001_full_market_source_rebuild/stage001_summary.json`
- `artifacts/stage001_full_market_source_rebuild/report.md`
- `artifacts/stage001_full_market_source_rebuild/artifact_manifest.json`

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：否；整个XGBoost目标仍是高过拟合风险。
- 原因：本阶段只恢复同源PIT目录、映射和日线，并执行事前冻结的数据门，不读取收益或标签。根据结果改截止日、品种或门槛则会转为明显过拟合。

## 继续价值反思

- 运行前判断：有，但仅限本次数据重建与原门复验。
- 原因：旧源的尾部缺口已定位到采集语义，修复成本可控且是判断全市场模型是否有数据资格的必要条件；若同源重建后仍失败，本线立即停止。
