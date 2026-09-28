# Stage001逐合约换月调整趋势质量标签实施计划

> 按本线TDD执行；每项先RED、确认预期失败，再写最小实现。用户已授权后续研究操作默认执行，生产/CTP/订单继续禁止。

**目标：** 在不发生任何跨合约价格比较的条件下，为全部到期安全20日路径生成方向中性的趋势捕获质量标签，并证明标签与冻结特征身份完整对应且组内非退化。

**架构：** 纯核心模块负责日线规范化、同合约leg收益、路径聚合和qid relevance；Stage001 runner负责冻结输入身份、上游复验、硬门、原子bundle和verify-only。Stage001没有模型或策略效果代码。

**技术栈：** Python 3.11、pandas、numpy、pytest；解释器固定`.py311/bin/python`。

## Task 1：同合约leg收益

**文件：**

- 新增：`tools/roll_adjusted_trend_quality.py`
- 新增测试：`tests/test_roll_adjusted_trend_quality.py`

- [x] RED：跨换月的两个leg各自只比较自己的合约端点，不产生旧/新合约跳空收益。
- [x] RED：重复bar、缺失端点、非正或非有限close必须明确失败。
- [x] RED：日期、leg身份、`path_valid/leg_valid`或端点存在标记不合法必须失败。
- [x] GREEN：实现纯同合约log-return构造和逻辑读取审计。

## Task 2：路径质量与qid relevance

**文件：**

- 修改：`tools/roll_adjusted_trend_quality.py`
- 修改测试：`tests/test_roll_adjusted_trend_quality.py`

- [x] RED：正负镜像路径得到相同绝对幅度、趋势效率、方向化回撤和主标签。
- [x] RED：主标签精确等于绝对累计收益加负的方向化最大回撤。
- [x] RED：leg数不等、index不连续、qid太窄或主标签退化必须失败。
- [x] RED：并列主标签得到相同relevance，不以产品代码打破并列。
- [x] GREEN：实现路径聚合、逐值审计字段和五级qid relevance。

## Task 3：Stage001 runner

**文件：**

- 新增：`tools/stage001_roll_adjusted_trend_quality_labels.py`
- 新增测试：`tests/test_stage001_roll_adjusted_trend_quality_labels.py`

**输出：**

- `leg_returns.csv.gz`
- `path_labels.csv.gz`
- `qid_diagnostics.csv.gz`
- `summary.json`
- `input_identities.json`
- `upstream_verification.json`
- `report.md`
- `artifact_manifest.json`

- [x] RED：合成fixture能生成bundle并通过`verify-only`。
- [x] RED：路径/特征身份不覆盖、close缺失、公式不变量或qid非退化失败时仍fail-close并输出可复验决策。
- [x] RED：summary明确记录模型/回测/holdout/CTP/订单/生产计数均0。
- [x] GREEN：实现输入身份、上游验证、评估、原子发布和离线复验。

## Task 4：冻结与唯一执行

- [x] 运行本线测试、全部`futures_trend_xgboost_pit_*`回归、`py_compile`和`git diff --check`；当前`342 passed`。
- [ ] 冻结核心、runner、测试、计划、预注册及全部输入SHA。
- [ ] 生成绑定SHA与唯一nonce的Stage001 authorization receipt，执行唯一`--run`，随后只做`--verify-only`。
- [ ] 中文记录结果并更新本线`LINE.md`与`research/registry.md`；Stage001无回测结果，不拉独立回测reviewer。
- [ ] 仅当全部硬门通过，才允许另立XGBoost OOS合同预注册。
