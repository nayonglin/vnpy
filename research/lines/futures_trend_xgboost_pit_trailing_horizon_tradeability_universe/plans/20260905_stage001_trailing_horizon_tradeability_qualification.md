# Stage001历史镜像可成交宇宙资格实施计划

> 按本线TDD执行；每项先RED、确认预期失败，再写最小实现。用户已授权内联执行。

**目标：** 在不读取close的前提下，验证过去20日完整动态执行资格能否因果筛出未来20日仍可生成可交易标签的候选宇宙。

**架构：** 复用上一线冻结日映射和动态leg核心；新核心只构造历史镜像窗口、汇总历史可成交资格并绑定query-date future-leg1映射。Stage001 runner先形成因果宇宙，再独立审计入池路径的未来20日，负责输入身份、硬门、原子发布和离线验证。

**技术栈：** Python 3.11、pandas、numpy、pytest；解释器固定`.py311/bin/python`。

## Task 1：历史镜像窗口

**文件：**

- 新增：`tools/trailing_horizon_tradeability.py`
- 新增测试：`tests/test_trailing_horizon_tradeability.py`

**接口：**

- `build_trailing_windows(windows, global_dates, lookback=20) -> DataFrame`

- [x] RED：历史首个previous date为query date前第20个session，末端精确等于query date。
- [x] RED：历史路径所有selection/return都不晚于query date。
- [x] RED：日历历史不足必须明确失败，不得缩窗。
- [x] GREEN：实现纯日历历史窗口转换。

## Task 2：因果宇宙资格

**文件：**

- 修改：`tools/trailing_horizon_tradeability.py`
- 修改测试：`tests/test_trailing_horizon_tradeability.py`

**接口：**

- `build_universe_qualification(windows, historical_legs, historical_audit, historical_events, future_leg1_mapping, lookback=20) -> tuple[qualification, selected]`

- [x] RED：20个历史leg、端点和所有事件均通过时入池。
- [x] RED：历史映射缺失、端点非正、roll_close容量不足任一发生时拒绝。
- [x] RED：future leg1必须由query date信息选择；entry date同日或未来选择拒绝。
- [x] RED：入池资格最大观察日不得晚于query date。
- [x] GREEN：实现路径聚合、明确拒绝原因与稳定身份。

## Task 3：Stage001 runner与未来资格审计

**文件：**

- 新增：`tools/stage001_trailing_horizon_tradeability.py`
- 新增测试：`tests/test_stage001_trailing_horizon_tradeability.py`

**输出：**

- `daily_contract_candidates.csv.gz`、`daily_contract_mapping.csv.gz`
- `historical_legs.csv.gz`、`historical_leg_audit.csv.gz`、`historical_execution_events.csv.gz`
- `universe_qualification.csv.gz`、`selected_windows.csv.gz`
- `future_dynamic_legs.csv.gz`、`future_leg_audit.csv.gz`、`future_execution_events.csv.gz`、`future_path_qualification.csv.gz`
- `summary.json`、`input_identities.json`、`upstream_verification.json`、`report.md`、`artifact_manifest.json`

- [x] RED：合成fixture完整通过并可`verify-only`，不可解析close哨兵不被读取。
- [x] RED：历史不合格只影响因果入池；未来失败只能使未来资格门失败，不能改变selected windows。
- [x] RED：qid宽度不足、历史泄漏、未来映射/端点/事件容量失败均fail-close并发布可复验bundle。
- [x] GREEN：实现前后身份、manifest验证、两阶段审计和原子发布。

## Task 4：冻结与唯一执行

- [x] 运行本线测试、全部XGBoost PIT回归、`py_compile`和`git diff --check`。
- [ ] 冻结输入、核心、runner、测试、计划、预注册与依赖SHA。
- [ ] 生成一次性authorization receipt，执行唯一`--run`，随后只做`--verify-only`。
- [ ] 中文记录结果并更新LINE/registry；无回测则不拉独立回测reviewer。
- [ ] 仅当全部硬门通过，才允许另立label value生成预注册线。
