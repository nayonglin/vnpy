# 全市场EIA外生信息 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. 用户已授权自主研究、多agent与当前checkout执行；不新分支/工作树、不commit/push，研究文档保存本线，不等待重复设计批准。

**Goal:** 检验新公布库存创新能否提升全市场long-only净收益与回撤；源导入不是目标终点。

**Architecture:** 060独立导入官方发布小表并输出因果report/u对应，061固定6次同容量拟合，062复用已接受现金核一次12账户，063独立审查保存的结果。首次这里只授权060来源实现/一次批量导入，其他actual须在真实输入和源审查完成后由root签发，避免缺数据时空跑。

**Tech Stack:** .py311/bin/python；标准库、numpy/pandas/scikit-learn本机现有版本；不安装依赖或下载分钟。

**Spec:** `stages/20261018_1456_stage057_eia_inventory_release_signal_proposal.md`；机器合同 `outputs/stage059_eia_full_market_protocol/protocol.json`。

## Global Constraints

- 完整399252母体、全部family有事件内交易资格，四油品仅诊断；不以未来退出/可闭合筛训练外机会。
- source Table1库存上半表为million barrels，×1000统一thousand；不混入下半表thousand barrels/day流量。
- 真实release date从archive release列，不由URL目录日期猜；2022延迟/同日多report必须支持。
- 两旧期CSV真实GET200已取得；HTML初次timeout与沙箱DNS失败保留，不伪称所有历史齐全。
- 固定s、52期、过去sham、10槽Ridge1、两个cutoff、6fit/12cash；不救参。

## Review Focus

1. 2020-01-03发布的统计周为2019-12-27；不可按周结束提前可用。
2. URL日期与实际release列不同，或同日两report时，仍按实际发布序列/保守时钟决定。
3. 上下表重复相似标签/不同量纲，只取库存三精确行，核current−previous与Difference一致。
4. 完整calendar缺一文件时保留ordinal和unknown；不要将52个非空report压缩成52周。
5. 全family资格；past sham只能过去，日bar夜盘open不允许穿越发布日期。

## Task 060 来源导入与事件对应

Files: create `tools/stage060_eia_report_import.py` and `tools/test_stage060_eia_report_import.py`; outputs只写`outputs/stage060_eia_report_import/`，阶段记录唯一stage060；不改059/LINE/registry。

Interfaces: `parse_archive_html(html: str) -> list[dict]`保留report_id/issue_url/release_date/data_ending_expected；`parse_table1(content: bytes, report: dict) -> list[dict]`输出3stock/current/prior_inline/delta/nativeunit/normalizedunit与srcbinding；`make_report_signals(calendar_reports, normalized_values, china_dates) -> DataFrame`输出全部calendar report的可用时刻、s、past_sham、missing、chosen_u、superseded。

- [ ] 先写5项有意义行为测试：跨年发布日期、目录日期不是发布日期、上下表单位/重复标签、缺期ordinal及past-only sham、夜盘因果时钟与同u多report。先RED后实现，留终态；不跑旧suite。
- [ ] 只读已有058两CSV作real结构例；原始stock单位按官方Table1表头百万桶，不从csv magnitude凭空猜单位。可一次读取两旧期PDF表头确认，不展开PDF工程。
- [ ] 获取archive HTML最多3种已知官方route（可换现有curl transport），提取完整官方calendar并将目标CSV定位为已观察issue目录的csv/table1.csv；不要生成所有日期盲扫。若无法取得calendar报告准确原因，保留已知两期，严禁猜节假日或首发时刻。
- [ ] 有calendar后一次批量<=900、并发4、每请求20秒、无自动重试；058已取两CSV可复制引用为缓存，缺期保留而不反复重抓。保存raw响应在excluded_raw_sources且排除Git，保存完整进度/失败/实际terminal。
- [ ] 输出规范stock表、report calendar/sourcebindings、全部report事件scalar/past_sham及mapping、coverage/missing统计、artifact manifest/终态；无需本轮原生DB/新标签/fit/cash。

## Task 061/062 固定学习和现金（后续授权）

- [ ] 读060真实产物后只用059的3个common NPZ列及049完整经济标签，061生成全部主域预测、训练ID/成熟权重/scaler、系数与正规方程核验材料。所有缺失与非事件留行。
- [ ] 模型/现金源码新行为测试并作一次接口预检后，root分别授权唯一6fit和唯一12cash；旧042纯核可复用但不可调用其55候选builder，也不复用053模型/score。
- [ ] 保存完整fill/daily/budget/positions/closed/open/CI/sharedindices、年度/家族归因和缺价情景，不把局部油品收益写成全市场稳定优势。

## Task 063 独立审查与结案

- [ ] 独立agent不重拟合、不再SQL/策略重放，核全部split/scaler/系数/预测/资金账本/成本/统计与未知；结果和判断中文记录。root接受或否决，必要资产本地一次登记，不提交推送或改正式版。

## 反思

本计划收益前冻结，新增按结果救参：否；多轮历史择题偏差仍在。继续价值：是，新实物观测有独立经济含义且能用很小公开表检验；不能预认延迟之后仍有edge。完整目标未完成。
