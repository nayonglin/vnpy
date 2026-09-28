# Stage001方向代理无标签资格实施计划

> 按本线TDD执行。用户已授权后续研究操作默认执行；生产、CTP和订单仍禁止。

**目标：** 对全部非固定fu的日级评分行，严格复刻当前C9/15w的query-date换月延续市场条件，并证明方向代理、AM41、数据身份和研究成本元数据足以支持下一阶段标签预注册。

**架构：** 纯核心模块负责原始bar规范化、AM41切片、正式/手工双实现方向判定和成本来源映射；Stage001 runner负责冻结身份、硬门、原子bundle与verify-only。Stage001没有未来标签、模型或回测代码。

**技术栈：** Python 3.11、pandas、numpy、pytest；解释器固定`.py311/bin/python`。

## Task 1：AM41与方向代理核心

**文件：**

- 新增：`tools/directional_continuation_proxy.py`
- 新增测试：`tests/test_directional_continuation_proxy.py`

- [ ] RED：AM只保留截至query date最后41根真实bar，不使用未来bar或平填bar；流式源中更晚日期的非法OHLC也不得在当前query前转成数值。
- [ ] RED：不足41根、query bar缺失、重复日期、非法OHLC分别产生明确结果或失败。
- [ ] RED：构造long、short、neutral样例，验证多空对称方向、MA5 extreme、short slope、wick过滤与双真保护。
- [ ] RED：手工公式逐项与注入最终设置的`QmtRollPortfolioStrategyStage847C9StopRetry`实例方法oracle一致。
- [ ] RED：正式oracle独立调用`_generate_signal`产生MA对齐状态，手工公式被替换为异常时oracle仍可运行。
- [ ] GREEN：实现无未来值的纯方向核心和逐项审计字段。

## Task 2：成本来源核心

**文件：**

- 修改：`tools/directional_continuation_proxy.py`
- 修改测试：`tests/test_directional_continuation_proxy.py`

- [ ] RED：17个显式产品使用当前qmt universe值，其他产品使用元数据fallback。
- [ ] RED：缺失/非正size、tick、slippage或未知来源必须失败；`jm.DCE`保留显式1.0 slippage而非0.5 tick。
- [ ] GREEN：输出`research_code_defined_cost_proxy`及来源类型，不输出“真实费用”字段。

## Task 3：Stage001 runner与可复验bundle

**文件：**

- 新增：`tools/stage001_direction_proxy_qualification.py`
- 新增测试：`tests/test_stage001_direction_proxy_qualification.py`

**输出：**

- `direction_proxy_audit.csv.gz`
- `qid_direction_diagnostics.csv.gz`
- `cost_metadata.csv`
- `source_contract_audit.csv.gz`
- `summary.json`
- `input_identities.json`
- `upstream_verification.json`
- `report.md`
- `artifact_manifest.json`
- 固定外部防重放事件：`artifacts/stage001_execution_event.json`，必须在首次代理分布访问前原子创建，不属于可删除重建的结果bundle。
- 固定核心进入claim：`artifacts/stage001_execution_claim.json`，必须在正式核心读取任何代理分布前以`O_EXCL`创建，相同lease的顺序或并发重入均拒绝。

- [ ] RED：合成fixture能生成bundle并通过`--verify-only`。
- [ ] RED：身份漂移、future OHLC数值暴露、post-query bar、正式设置漂移、方向公式不一致、覆盖门失败和成本缺口均fail-close，且不可观测行不补0。
- [ ] RED：正式入口拒绝调用方注入路径，fixture入口限制在`fixture_root`；授权绑定漂移、回执重放、并发消费、相同lease顺序/并发重入和runner异常都有独立失败测试。
- [ ] RED：summary明确记录未来收益/标签、fit/predict、回测、holdout、CTP、订单和生产写入计数均0。
- [ ] GREEN：实现全部直接输入before/after身份，并把授权绑定SHA并入expected map；实现source manifest文件验证、精确样本切分、唯一评估、`O_EXCL + fsync`耐久event/claim、原子发布和离线复验。

## Task 4：预审、冻结与唯一执行

- [ ] 独立reviewer先审Stage000语义、计数、失败门和措辞；P0/P1清零后才允许执行。
- [ ] 运行本线测试、相关XGBoost PIT回归、`py_compile`和`git diff --check`。
- [ ] 冻结核心、runner、测试、计划、预注册及全部输入SHA。
- [ ] 生成绑定SHA与唯一nonce的Stage001 authorization receipt；runner在读取代理分布前以`O_EXCL`消费nonce并创建单次核心claim，对文件与父目录执行`fsync`，固定event、claim或输出已存在即拒绝重放；执行唯一`--run`后只做`--verify-only`。
- [ ] 中文记录结果并更新本线`LINE.md`与`research/registry.md`。Stage001无回测结果，不触发强制回测review；仍做独立post-review核验审计边界。
- [ ] 仅当全部硬门通过，才允许另写方向一致净效用标签合同；通过不代表XGBoost或收益目标成立。
