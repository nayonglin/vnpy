# Stage008 正确 OI 字段合同下的既有分钟重新资格审查结果

- line_id：`futures_trend_triple_screen`
- 当前模式：零网络、零账户、零策略变更的离线数据重新资格审查；`production_qualified=false`。
- 记录时间：2026-10-17 23:56 CST，读取时钟后记录；使用 root 指定的固定阶段文件名。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`。
- 阶段性质：按已冻结 Stage008 合同核验 Stage007 已取得的同一批分钟，不修改或覆盖原拒绝证据。
- 是否重要突破：否；纠正验收字段语义，并为一个精确目标 session 建立可复验的数据资格。
- 是否触发A/B：本阶段未新增金融 A/B；策略、模型、费用、正式日线 OI 口径均不变。

## 外部调研与判断

- 参考资料：沿用 Stage007 的 [官方历史回放说明](https://doc.shinnytech.com/tqsdk/latest/usage/backtest.html)、[官方快速入门](https://doc.shinnytech.com/tqsdk/latest/quickstart.html)和官方 GitHub 源码调研；本阶段只读取既有本机证据，不再访问提供商。
- 字段根因依据：`examples/portfolio_backtesting/import_tqsdk_all_futures_daily_to_db.py:115` 为 `open_interest=float(getattr(row, "open_oi", 0.0) or 0.0)`。该导入器 SHA256 为 `0fd37e73b40a7c104eacc9acf9b2e456559cf1ebdcef0c8ce9acc2fd578255cb`。
- 我的判断：本目标已知导入源的 DB `open_interest` 对应日线 openOI，应与首分钟 openOI 核对；它没有提供独立 closeOI。CSV 的首 openOI、尾 closeOI 两项仍分别校验，不能删除 closeOI 检查，也不能把 DB closeOI 编造成“匹配”。该结论只限本目标及已证实导入源，不能泛化全市场数据库。

## 本次变更

- 新增脚本：`tools/stage008_oi_requalification.py`、`tools/test_stage008_oi_requalification.py`。
- 修改脚本：无。Stage007 工具、测试、raw、完成证据、quality、receipt 保持原字节。
- 删除脚本：无。
- 新增参数：独立 `--audit` 入口；固定目标 `rb2010.SHFE × 2020-08-12`，已有输出时拒绝覆盖。复用原比较容差 `rtol=1e-12, atol=1e-8`。
- 修改参数：只在本阶段新资格合同中把 DB `open_interest` 对应到首分钟 `open_oi`；未改旧质量合同、正式代码或策略参数。
- 删除参数：无；DB closeOI 标为 `N/A_not_independently_available`。

## 回测/归因参数

- 数据区间：仅目标交易日 2020-08-12，原 helper 网格为物理 2020-08-11 21:00—2020-08-12 14:59，共 345 分钟。
- 账户规模：N/A；本阶段 TqApi 实例 0、TqSim 实例 0、金融策略回放 0。
- 成本口径：N/A；不读权益或 PnL，不计算收益、费用和滑点。
- 样本过滤：不新增或删除目标分钟；严格读取 Stage007 同 SHA 345 行，要求唯一精确合约网格、合法 OHLC/量仓以及逐行后继完成证据。
- 策略/归因口径：CSV 核 OHLCV、首 openOI、尾 closeOI 七字段；DB 以只读 SQLite 查询精确合约/interval=d/目标日唯一 bar，核 OHLCV 五字段和 `open_interest → 首 openOI`，共 13 项。
- 指纹门：核 Stage007 原 parent、worker、quality、raw、完成证据、preflight 及全部原输入 SHA；再记录本阶段代码、协议、原 helper、导入器、CSV、DB 指纹，运行前后不变。
- 唯一实际命令：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage008_oi_requalification.py --audit`。仅运行一次，退出码 0，审查主体用时 0.285 秒。

## 结果

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。
- 其他关键指标：345/345 分钟唯一且精确覆盖目标网格，合法性通过；345/345 后继完成证据通过；13/13 字段检查通过，全部绝对差为 0。

| 聚合字段 | 完成分钟值 | CSV 对照 | DB 对照 |
| --- | ---: | --- | --- |
| open | 3,795 | 匹配 | open_price 匹配 |
| high | 3,809 | 匹配 | high_price 匹配 |
| low | 3,780 | 匹配 | low_price 匹配 |
| close | 3,805 | 匹配 | close_price 匹配 |
| volume | 740,132 | 匹配 | volume 匹配 |
| open_oi | 1,064,817 | 匹配 | open_interest 匹配 |
| close_oi | 1,053,986 | 匹配 | N/A，未提供独立 closeOI |

- 目标末分钟 `2020-08-12 14:59` 的观察后继为 `2020-08-12 21:00`；未把回放结束时的形成中 bar 直接计入。
- 新增网络 0、提供商回放 0、金融策略回放 0、TqApi/TqSim 0、下单/撤单 0、模型训练 0、原数据写入 0、缓存/overlay 写入 0、fallback 启用 0。
- Stage007 原 `completed_quality_rejected`、exit 1、`quality.accepted=false` 及 `close_oi` 误映射拒绝保持原样；本阶段是独立的新合同资格结论，不回填旧合同成功。
- 3 个 focused 语义测试 red→green 通过：DB=openOI 而非 closeOI 的反例；DB 价格、量、openOI 任一错误都拒绝；缺少末分钟后继或后继不前进都拒绝。
- 独立审查完成，P0/P1 均为 0，可接受这精确 345 行作为研究补数候选；未扩大为全市场或全部候选路径的数据资格。

## 输出文件

目录：`outputs/stage008_oi_requalification/`。

- report：本阶段记录。
- summary：`requalification.json`；自动生成时状态为 `target_requalified_pending_independent_review`，其后的独立通过由单独 review receipt 证明，原 JSON 不覆盖。
- orders：N/A。
- daily：N/A；未产生账户日权益。
- quality：`field_checks.csv`、`input_manifest.json`、`attempt_started.json`。
- 原始数据只引用不重写：`outputs/stage007_tqsdk_stream_probe/network_attempt1/raw_completed_minutes.csv`，SHA256 `0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac`。
- 原完成证据 SHA256：`3eecacbf83069daac6e0508b5ebdb79e6db50ba60b89b1486d76ce2979f8aff2`。
- 原拒绝 quality SHA256：`9bf02a770b12c7fe65d2efb105e3bfc4f29227d2961352eb0a614a6d5eb6625e`。
- 独立审查目录：`outputs/stage008_independent_review/`，review receipt SHA256 `aab0b7062ff32e67d4fdf2f3132b00188c5779cf59c1462144f002a7b25ddaa6`。
- 小型产物指纹见 `requalification.json` 的 `artifact_sha256`；原分钟只保留本机，不进 Git。

## 结论

- 本阶段结论：在可证实的 OI 导入语义下，既有这 345 行目标完成分钟通过重新资格及独立审查，可作为后续研究补数候选。没有原行情改值或重新获取数据。
- 是否进入下一步：是，制定一次性精确批量需求计划；尚未批准合并 overlay、source fallback 或 C0_attempt3。
- 下一步：把 Stage005 初始信号、换月 OPEN、普通 CLOSE 需求分别列示，先确认真实完成分钟与原日线字段语义，再讨论可运行的共同数据合同。正式策略继续使用原 DB 的既有 OI 口径；若研究同日 closeOI 信号，应另开预声明版本。

## 过拟合反思

- 运行前判断：否，字段映射来自已冻结的导入源码与目标值关系，不依赖策略收益。
- 运行后判断：否，没有改变原价格、策略或容差，也没有删掉不利样本；保留旧拒绝并单列新合同。
- 原因：修正的是数据字段解释，且仍同时核 CSV 七字段、DB 可用字段和完成证据；不把局部证据提升为通用 alpha 或全市场保证。

## 继续价值反思

- 运行前判断：是，可避免把正确分钟因错误 OI 对照误判不可用。
- 运行后判断：是，精确数据候选已获独立证据；价值在后续一次性真实需求覆盖，非再次取同一窗口。
- 原因：无须新网络或账户回放即可解决已发现的验收语义问题，并保留原策略基线与失败审计链。

## 合入建议

- 是否更新本线 `LINE.md`：由 root 汇总后统一更新，本任务未改。
- 是否更新 `research/registry.md`：由 root 决定，本任务未改。
- 是否追加根目录 `memory.md/back_log.md`：否，尚无正式候选晋级。
- 由 root 统一精确登记小证据与代码；本任务不登记资产、不合并行情、不部署、不启动金融账户。
