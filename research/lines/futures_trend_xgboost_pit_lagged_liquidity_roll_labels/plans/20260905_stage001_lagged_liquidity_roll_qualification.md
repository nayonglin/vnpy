# Stage001滞后流动性动态换约资格实施计划

> 按本线TDD执行；每项先RED、确认预期失败，再写最小实现。用户已授权内联执行。

**目标：** 在不读取close的前提下，验证严格滞后一日、容量约束且到期月份单向推进的实际合约映射能否形成完整可交易的20日动态标签路径。

**架构：** 新核心先为所有`(execution_date, product)`构造产品级日映射，再把冻结窗口展开为20个leg并按键连接；复用冻结的endpoint质量与一手容量纯函数。Stage001 runner负责输入身份、全量门禁、原子发布和离线验证。

**技术栈：** Python 3.11、pandas、numpy、pytest；解释器固定`.py311/bin/python`。

## Task 1：产品级滞后日映射核心

**文件：**

- 新增：`tools/lagged_liquidity_roll.py`
- 新增测试：`tests/test_lagged_liquidity_roll.py`

**接口：**

- `build_lagged_contract_map(execution_dates, products, catalog, liquidity, global_dates, minimum_volume=100, minimum_open_interest=100) -> tuple[mapping, candidates]`

- [x] RED：selection date精确等于execution date前一全市场交易日。
- [x] RED：execution date当日的流动性尖峰不能影响选择。
- [x] RED：99失败、100通过，到期日必须覆盖return date。
- [x] RED：排序按OI、成交量、到期日、合约名稳定执行。
- [x] RED：产品映射不得向更早到期日回滚；没有同到期或远月合格合约时明确缺失。
- [x] GREEN：实现按产品和执行日的向量化候选生成与小规模有序状态机。

## Task 2：20日动态路径与执行事件

**文件：**

- 修改：`tools/lagged_liquidity_roll.py`
- 修改测试：`tests/test_lagged_liquidity_roll.py`

**接口：**

- `build_dynamic_legs(windows, daily_mapping, global_dates, holding_period=20) -> DataFrame`
- 复用`roll_label_tradeability.audit_leg_endpoints`、`build_execution_events`、`assess_event_capacity`。

- [x] RED：每条窗口精确20个leg，并按`previous_date`连接日映射。
- [x] RED：合约变化生成同日roll_close与roll_open，不变持有不生成交易事件。
- [x] RED：缺失映射、到期不足、非严格滞后、端点缺失或事件容量不足均可归因失败。
- [x] GREEN：实现路径连接、roll标志和路径级汇总。

## Task 3：Stage001 runner与发布

**文件：**

- 新增：`tools/stage001_lagged_liquidity_roll.py`
- 新增测试：`tests/test_stage001_lagged_liquidity_roll.py`

**输出：**

- `daily_contract_candidates.csv.gz`
- `daily_contract_mapping.csv.gz`
- `dynamic_legs.csv.gz`
- `leg_endpoint_audit.csv.gz`
- `execution_events.csv.gz`
- `path_qualification.csv.gz`
- `summary.json`、`input_identities.json`、`upstream_verification.json`、`report.md`、`artifact_manifest.json`

- [x] RED：合成fixture完整通过并可`verify-only`；close列写入不可解析哨兵，runner仍成功。
- [x] RED：同日/未来selection、qid宽度不足、映射缺失、到期回退、端点质量或执行容量任一失败时决策失败。
- [x] GREEN：实现输入manifest验证、输入前后身份、原子发布和失败bundle。

## Task 4：冻结与唯一执行

- [x] 运行本线测试、全部XGBoost PIT数据线回归与`py_compile`。
- [ ] 冻结输入、核心、runner、测试、计划、预注册和依赖SHA。
- [ ] 生成一次性authorization receipt，执行唯一`--run`，随后只做`--verify-only`。
- [ ] 中文记录结果并更新LINE/registry；无回测则不拉独立回测reviewer。
- [ ] 仅当全部硬门通过，才允许另立label value生成预注册线。
