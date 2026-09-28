# Stage001打分日固定实际合约资格实施计划

> 按本线TDD执行；每项先RED、确认预期失败，再写最小实现。用户已授权内联执行。

**目标：** 在不读取close的前提下，验证query-date选择的单一实际合约能否形成完整、可成交的20日固定合约标签路径。

**架构：** 新核心只负责因果合约选择和固定leg构造；复用上一线冻结的endpoint质量与一手容量纯函数。Stage001 runner负责输入身份、全量门禁、原子发布和离线验证。

**技术栈：** Python 3.11、pandas、numpy、pytest；解释器固定`.py311/bin/python`。

## Task 1：query-date合约选择核心

**文件：**

- 新增：`tools/query_date_fixed_contract.py`
- 新增测试：`tests/test_query_date_fixed_contract.py`

**接口：**

- `select_query_date_contracts(windows, catalog, liquidity, global_dates, history_window=20, required_capacity_days=18, minimum_volume=100, minimum_open_interest=100) -> tuple[selected, candidates, rejected]`

- [x] RED：到期早于label end的高OI合约必须被排除。
- [x] RED：历史`17/20`容量日失败，`18/20`通过；缺失全市场交易日按失败计数。
- [x] RED：query date之后的超高OI/成交量行完全不影响选择。
- [x] RED：多个合格合约按OI、成交量、到期日、合约名稳定排序。
- [x] GREEN：实现最小向量化选择与明确失败原因。

## Task 2：固定20日路径与资格审计

**文件：**

- 修改：`tools/query_date_fixed_contract.py`
- 修改测试：`tests/test_query_date_fixed_contract.py`

**接口：**

- `build_fixed_contract_legs(selected, global_dates, holding_period=20) -> DataFrame`
- 复用`roll_label_tradeability.audit_leg_endpoints`、`build_execution_events`、`assess_event_capacity`。

- [x] RED：20个leg全部使用同一合约，首尾日期精确匹配entry/label end。
- [x] RED：每条路径只生成entry/exit两个事件，roll事件为0。
- [x] RED：任何未来端点非正volume/OI使路径失败，任何entry/exit低于100/100使容量失败。
- [x] GREEN：实现固定路径与路径级汇总。

## Task 3：Stage001 runner与发布

**文件：**

- 新增：`tools/stage001_query_date_fixed_contract.py`
- 新增测试：`tests/test_stage001_query_date_fixed_contract.py`

**输出：**

- `contract_candidates.csv.gz`
- `selected_contracts.csv.gz`
- `selection_rejections.csv.gz`
- `fixed_contract_legs.csv.gz`
- `leg_endpoint_audit.csv.gz`
- `execution_events.csv.gz`
- `path_qualification.csv.gz`
- `summary.json`、`input_identities.json`、`upstream_verification.json`、`report.md`、`artifact_manifest.json`

- [x] RED：合成fixture完整通过并可`verify-only`；close列写入不可解析哨兵，runner仍成功。
- [x] RED：qid候选少于30、未来选择、到期不足、端点质量或容量任一失败时决策失败。
- [x] GREEN：实现filename/path两类manifest验证、输入前后身份、原子发布和失败bundle。
- [x] 运行新线`8 passed`、全部XGBoost PIT数据线回归`97 passed`与`py_compile`。

## Task 4：冻结与唯一执行

- [ ] 冻结输入、核心、runner、测试、计划、预注册和依赖SHA。
- [ ] 生成一次性authorization receipt，执行唯一`--run`，随后只做`--verify-only`。
- [ ] 中文记录结果并更新LINE/registry；无回测则不拉独立回测reviewer。
- [ ] 仅当全部硬门通过，才允许另立label value生成预注册线。
