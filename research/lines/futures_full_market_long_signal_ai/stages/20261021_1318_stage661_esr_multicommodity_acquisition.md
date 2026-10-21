# Stage661 官方多商品出口数量源单轮采集与规范化

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：day，有限数据准备任务；完整研究目标保持 active。
- 记录时间：2026-10-21 13:18 CST；唯一实际采集 13:17—13:18，26.306715 秒。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`，未创建分支或工作树。
- 阶段性质：冻结 Stage660 合同后的数据采集，不是回测、训练、策略晋级或历史发布时间认证。
- 是否重要突破：否；新增可复验的五类外生数量原始资料，尚无收益证据。
- 是否触发 A/B：否；本阶段禁止标签、模型和策略读取或修改。

## 外部调研与判断

- 继承 Stage658 的官方发布时钟与合并报告证据、Stage659 的独立语义审查、Stage660 的确切公共查询合同。原 Stage649 公共客户端及 44 项官方 commodity metadata 是商品 ID、代码、名称和单位的来源。
- 只请求官方客户端已有的公共 `WeeklyHistorialReportData` 历史路线，固定 `WeekEndingDate=10/16/2026`，商品 ID 为 `7/14/15/16/27`。未请求其他端点、无凭证、未绕过认证。
- 判断：多个有经济差异的商品源比 Corn-only 更适合以后检验跨商品信息，但这些均是美国对全部目的地的出口记录，不是中国进口需求、全球总需求或独立重复实验。历史 period end 不能当作 release time；当前修订数据库不能当作首次发布版本。

## 本次变更

- 新增：本阶段输出目录内 `collect_and_normalize.py`、`test_normalize.py`、source-ready、唯一 actual 标记、原响应、17 列 CSV、逐商品 summary/receipt 和最终 manifest。
- 修改/删除：无；没有改原 Corn、策略、模型、标签、正式配置或其他研究线。
- 新增参数：五个固定商品 ID；每个响应最多 4 MiB；单次总期限 20 秒；自动重试 0；重定向 0；实际查询最多 5。
- 修改/删除参数：无。
- 两个合成格式 fixture：先 RED 2（缺实现），后 GREEN 2，运行 0.026 秒。检查精确 Decimal、负值/null、同周跨 MY 双行、原顺序和棉花不转换单位；不读取历史 payload。按本次授权没有扩跑旧测试集。

## 采集结果

唯一 `.py311/bin/python -B …/collect_and_normalize.py --actual` 的 session 为 `60143`，持同一 session 到 exit 0；未重启。实际 5 次固定 URL GET，5 个 HTTP 200，0 重定向、0 重试、0 失败。每个原响应先保存再解析。

| 商品 | ID / 代码 | 新增原行 | 独立 period end | 历史范围 | 单位 | netSales 负值 | nextYearNetSales 负值 |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| ALL WHEAT | 7 / 107 | 1,951 | 1,919 | 1990-01-04—2026-10-08 | metric_tonnes | 75 | 48 |
| SOYBEANS | 14 / 801 | 1,951 | 1,919 | 同上 | metric_tonnes | 116 | 33 |
| SOYBEAN CAKE AND MEAL | 15 / 901 | 1,951 | 1,919 | 同上 | metric_tonnes | 82 | 87 |
| SOYBEAN OIL | 16 / 902 | 1,951 | 1,919 | 同上 | metric_tonnes | 227 | 63 |
| ALL UPLAND COTTON | 27 / 1404 | 1,951 | 1,919 | 同上 | running_bales | 158 | 49 |

- 新增合计 **9,755 行**。五表各 38 个 MY 定义、`Standard=1882 / MY Ending=37 / MY Starting=32`；每表保留同周不同营销年度记录，未合并周、删除重复或排序改写。
- ALL WHEAT、ALL UPLAND COTTON 使用官方汇总，不再加入其组件，避免重复相加。棉花 running bales 原单位保留，没有转换吨或擅定包重。
- 六个数量原字段的 null 均为 0。原符号完整保留，尤其豆油 `weeklyExport` 有 3 个负值、`outstandingSales` 有 2 个负值；未因看似异常而截断、归零或删除。
- 严格保留原 12 字段及原行顺序，派生 `source_row/period_end_date/unit/numeric_state/publication_clock_state`，共 17 列。精确 Decimal；null 的 CSV 字面为空，raw 仍保留 null。`publication_clock_state=historical_release_time_unknown`。
- 原 Corn 只继承绑定，不重新 GET、不读取其 raw/normalized payload。此次 0 标签/模型读取、0 SQL、0 分钟、0 feature join、0 fit、0 cash。
- 累计仍为 **563 fit /294 完成 cash +1 旧 partial**。98 个历史品种/95 个家族的全市场目标未缩小，也没有声称五源已覆盖整个市场。

## 回测指标

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部 **N/A**：本阶段没有跑回测，没有读取收益标签，不能从采集成功推导策略有效。

## 输出与限制

- 主 manifest：`outputs/stage661_esr_multicommodity_acquisition/manifest.json`，11,169 字节，SHA256 `b39bbef836a66034c540cc3dc9da3b650915b94c8203c3885ac3b3c37ff834f1`。
- 小汇总：同目录 `handoff_summary.json`；原响应、规范化 gzip CSV、逐商品 summary、receipt、code、contract 和 metadata 的绑定均在 manifest。
- 独立验收：等待 Stage662 按 root 授权单次解析 raw/normalized/metadata，逐字段独立复核；作者不以自身检查替代独审。
- 已知轻微命名问题：manifest 顶层 `source_ready` 最终是布尔值，覆盖了早先同名 binding；`source_ready.json` 及 `actual_started.json` 内的确切绑定完整保留。无数据/GET影响，不为此重写代码或重跑采集。
- source-ready 只表示源已采到并规范化，不代表 strict PIT、训练、跨族泛化、alpha、正式资格或目标完成。朴素 period-end+7 时钟已被上游证据否定；本次不构造新的伪发布时间。

## 过拟合与继续价值反思

- 运行前：本次不通过拟合/收益选择数据，所以不新增结果驱动调参；历史累计自适应风险仍高，不能因换源就消除。
- 运行后：判断不变。所有五个预先固定查询全部保留，没有按表现挑商品、年份或符号；没有训练或窥视 Y。
- 继续价值：有。新增五类真实数量源，且保留不同单位、修订、时钟与 MY 限制，能支持下一步先验经济映射和时钟可用性研究。尚不足以授权训练、高杠杆或极窄止损；不能用 Corn/SLV 旧失败方向扫参救分。

## 合入建议

- 本 agent 不改 `LINE.md` 或 `research/registry.md`；由 root 结合 Stage662 一次统一更新。
- 不追加根目录 `memory.md/back_log.md`，不提交或推送 Git，不修改正式版本和生产任务。
