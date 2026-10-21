# Stage454：Con4 可见性投影与六原 fold 源支持实现

- 时间：2026-10-20 22:04 CST；研究线 `futures_full_market_long_signal_ai`；非重要突破。
- 本阶段先读 `research/registry.md`，归属既有全市场 long-only 独立线；98 产品、95 家族不缩域，正式 C9 变更为 0。
- 范围：唯一工具、唯一测试、`outputs/stage454_Con4_visible_support/` 与本唯一阶段记录。没有改 LINE、registry、旧文件、Git 或生产。此记录时 actual 尚未运行，root 将在代码 SHA 固定后一次启动。

## 调研、判断与固定边界

重新查看 [CFTC Release Schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)、[Python ZoneInfo 官方文档](https://docs.python.org/3/library/zoneinfo.html) 和 [cot_reports 原作者代码](https://github.com/NDelventhal/cot_reports/blob/main/cot_reports/cot_reports.py)。结论：通常周二统计、周五发布不能代替 2010—2025 完整历史首发记录；下载器解决年包取得，不能证明历史可得时间；ZoneInfo 支持 NY 日历时钟和 DST，不能用 UTC 固定 24 小时计算 TTL。本次只执行 Stage453 已冻结的单一研究时钟，不增加来源、下载、滞后变体或 vintage 工程。

Stage453 原协议 SHA 为 `c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053`；root 在 actual 前补充的 `clock_implementation_clarifications.json` SHA 为 `9ce259c878659832da5d9b7e6936a5d724eafe1aba7449944d9092006945a5ff`，CLI 同时核定二者。

实现顺序为：原行永久资格 → NY 时钟事件流 → 原母身份投影 → 六原训练表身份与权重支持。普通行只在 asof+11 日 NY00 才 grant；延期期间不插普通 unknown。已知修订、质量、未对齐 guard、计划行优先隔离；真正未知批次按原 scheduled 次日 NY00 插 barrier，保留 consumed source-asof floor。只有更大的 asof 可安装新值，晚到旧报告不覆盖新报告，也不在 expiry 后复活。全局停发 reset 独立处理，取消跨入停发窗口的普通待入 grant；这种取消本身不会提前在原 due 抹掉更早仍有效的 episode。

活动隔离窗口为 NY 本地半开区间：2013-10-04—11-09、2018-12-28—2019-03-30、2023-02-03—03-22、2025-10-03—源尾。2013 恢复仍是预期恢复之后的研究假设，2019 终点只来自后续发布锚点，不宣称真实积压持续到该日。七个 ION 实际发布日期采用次日 NY00，后三条 source-asof 仍保留链接假设；03-17 先 reset 后安装 03-16 发布的 cohort。2019-03-26 七映射永久修订隔离，铜仅用已接受的 03-29 原发布锚点；未把其他更正公告扩成所有产品的 vintage 资格。

## 合成验证与发现

采用 test-driven-development：第一次运行 8 个案例全部因缺失实现而失败；实现后 8 个案例通过。随后在原停发案例中加入“停发前仍有效旧 episode”断言，发现待入行取消不该在更早原 due 插 unknown；该断言先红，修复后同一 8 案例全绿。没有读取 actual 数值来决定修复。

八个案例覆盖：普通延期与真实 0、跨 DST 的 167 小时周和半开 expiry、停发前待入 grant 取消与 2025 源尾、修订 barrier 与较旧同刻 grant、七个 ION 和 March17 同刻排序、有限 mask/未对齐 guard/确认周一例外、晚到旧报告单调 floor，以及原权重均值方差、发布组去重和父身份错配拒绝。最后一次输出为 `Ran 8 tests in 0.029s; OK`。

没有运行全仓库套件：root 明确要求只做 5—8 个真实时钟风险案例，并避免反复扩大检测。本任务不是收益回测；后续源支持产物仍必须由独立 Stage455 审查，不能以本 fixture 代替实际支持或训练资格。

## 固定输出和运行接口

`actual_run1/visible_mother_con4.npz`：`q_raw` 为 float64、原母顺序 shape 399252；unknown 和结构 N.A 保留 NaN；`sequence_index` 与 `source_episode_index` 为 int64，unknown 索引 -1。episode 索引固定是 448 原始 JSONL 行顺序 0—6679。

`source_episodes.jsonl` 保留全部 6680 行原来源身份，另含时钟状态、研究可得/expiry、隔离原因、修订原因和假设；`visible_mother_audit.csv.gz` 保留全部 399252 母身份及 unknown/N.A 原因。附带事件流方便 Stage455 检查未知状态而不重做原 ZIP。

`manifest.json` schema 为 `stage454_con4_visible_source_manifest_v1`；`sixfold_source_support` 各项含 scope/cutoff、原训练和 scaler 绑定、`q_statistics`、训练与预测支持及 passed，`all_support_passed` 只在完整六 fold 同时通过时为 true。统计含各年度、映射 family、source 年、availability group、episode/channel 与原权重集中度；不把 daily、child 或八渠道当独立发布。

actual 只读取 448 一次并顺手 SHA、原母表身份一次、六原训练 CSV 各一次且 usecols 排除 Y。原母/训练/COMMON scaler SHA 从已接受 452 继承，仅检查尺寸与前后 stat；不另全 hash 或读取 COMMON scaler 数值。六 fold 按原 sample_weight 在 finite q 子集计算均值和总体方差，训练和预测均要求至少两个映射 family、两个 source 年和两个 availability group；全原母域和 161014 前向母域保留。

```sh
.py311/bin/python -m unittest research/lines/futures_full_market_long_signal_ai/tools/test_stage454_con4_visible_support.py
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage454_con4_visible_support.py --actual --expected-code-sha256 06c9b4264c2e5fdbedbdbe292991ffd530cec6cf7f914f20c3198e57e887c38d
```

- code SHA：`06c9b4264c2e5fdbedbdbe292991ffd530cec6cf7f914f20c3198e57e887c38d`。
- tests SHA：`b95e6ca8564dbd83c83a661468740e083cfcb1121ac5179d80d76e725603307f`。
- fixture receipt：`outputs/stage454_Con4_visible_support/fixture_receipt.json`。

## 参数、结果与反思

新增：唯一源投影工具、8 个合成测试、fixture receipt。策略参数新增/修改/删除均 0；没有新模型、交互、flag、lag 或 source variant。回测结果新增/修改/删除均 0；期末权益、总收益、最大回撤、Sharpe、总滑点、胜率 N/A，总交易次数 0。

本 agent 本阶段实际 448、母库、训练 CSV、Y、价格、score、COMMON26、原 ZIP 读取均 0；fit、cash、SQL、API、下载、Git 和生产操作均 0。当前仅验证代码语义，实际支持数量尚未知，源资格、训练资格、收益资格、加注资格及 production 资格均未签发。

开始与结束判断：新增收益择参过拟合 **否**，实现完全受收益读取前的单一冻结时钟和 root 澄清约束；历史择题搜索带来的总体过拟合风险仍为 **是**。继续价值 **是，但仅限这一次源支持及独审**：可用有限成本拒绝不可靠时钟和非退化支持，不能从八个合成案例推出 alpha。TODO：root 以确切 SHA 一次运行；Stage455 独立检查全部源时钟、值映射、支持与异常；支持不通过即保留 unknown/停止，不改滞后、修订范围或映射救参。

## Root唯一实际执行补记

- 时间：2026-10-20 22:10 CST；root exec session69681已exit0，耗时12.714908秒，无重试。
- 原448数值一次、完整母身份一次、六原训练身份/权重各一次；Y/COMMON/score/价格/ZIP/fit/cash/API/SQL均0。
- 六fold源支持均通过；完整399252/98产品95家族保留，可见28697母行，763个去重availability group；不是28697独立样本。2026该来源为缺失。
- 455独立数值与时钟复核已启动，未完成前不授训练资格；本记录不把source完成当alpha。
- 无新增/修改/删除金融结果；累计460fit/250完成cash及1旧partial，期末权益/收益/回撤/Sharpe/滑点/胜率均N/A。
