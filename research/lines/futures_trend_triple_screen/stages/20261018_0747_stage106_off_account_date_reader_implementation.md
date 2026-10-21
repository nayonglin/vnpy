# Stage106实施：封存账户审计的严格日期reader

- line_id：`futures_trend_triple_screen`；时间：2026-10-18 07:47:54 +0800。
- 合同：`20261018_0742_stage106_A_mother_date_reader_contract.md`，含root实施前唯一raw_exports边界澄清；SHA `d7e00776a317c6b350cbec24b007be4429b06150d42561eef0690de2d78064d9`。
- 性质：修复独立审计reader，非alpha、非重要策略突破。新增/修改/删除策略参数0、金融结果0。

## 范围与判断

095真实审计已通过完整现金、库存、成本、1641日指标等前序，因raw usage.signal_date是naive午夜Timestamp而CSV日期是严格ISO字符串，母单候选假匹配0。105首笔实证有唯一opened plan，不是实际交易缺plan；旧095源/失败、105终态与证据、104真实completion及账户raw/seal/summary/context/readiness原字节保留。

实施前静态核对同一日期字段还用于095后置roll lineage；仅在a_mothers局部转换会遗漏该join。root因此明确采用唯一返回边界：私有导入冻结095，保存原raw_exports，完整调用它核raw↔导出和实际TradeData身份后，只copy返回usage并严格规范signal_date。其余trades/clock/hashes/identity仍是原对象，payload、原usage、实际时钟和所有数值不修改。095原audit/merge/a_mothers/retry/roll/现金/成本/gross算术全文不替换；A/B同一日级字段语义共享此reader。

仅允许严格`YYYY-MM-DD`且真实合法日的字符串，或naive且精确等于normalize的pd.Timestamp。非午夜、带时区、NaT/None/非法字符串类型拒绝，不截断或宽松解析。候选/换月CSV日期在原SHA核验后另核严格ISO；不改plan匹配或数据资格。

开始和结束过拟合判断均否：只修日标签可比性，没有看收益调参数或放宽真实plan条件。继续有价值：现金前序不能因reader假拒绝作废，母链仍必须完整核对，但不需要重跑策略。此次仅读本线原代码与105实证，按root有限修复要求没有新增外部alpha研究或网络请求。

## RED→GREEN（仅一项）

具名入口：

```sh
.py311/bin/python -m unittest test_stage106_independent_off_account_review.DateReaderTests.test_raw_usage_day_reader_preserves_both_joins_and_rejects_unsafe_days -v
```

工作目录为本线tools。真实RED exit1、1test/0.002s，旧透传usage行为在首笔Timestamp与CSV候选join得到0，预期1。只实施日期copy/严格校验后GREEN exit0、1test/0.023s，覆盖同日候选与后置旧合约close两join、合法naive午夜/ISO、非午夜/aware/非法日拒绝及原usage/四其他对象不变；后者是tiny identity fixture，不构成新行情或金融数据签发。source/test py_compile真实exit0。未跑旧suite，未运行完整--audit或金融/模型/provider/网络。

## CLI、输出与绑定

新源：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage106_independent_off_account_review.py`，SHA `6688020ff61a6b14ae2cc0ce158c7f54cf2692d1696b53a525596c76ec4f4b49`，6194 bytes。
测试：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/test_stage106_independent_off_account_review.py`，SHA `e793ab33d71efff6df757d1e5f43965f9c393c0ab9ee4bfcd794e50f2b0780eb`，2480 bytes。

```sh
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage106_independent_off_account_review.py --audit --arm A_OFF --completion-evidence /Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/outputs/stage104_A_OFF_actual_completion/root_actual_completion.json --completion-evidence-sha256 fd6272aeeb94b8546008224d54479aeab5e5e11d2cf5e73439c110b097f17944
```

本命令尚未执行，须107一次独立定向复核接受及root明确后才执行同一封存账户的只读审计，不增加金融attempt计数。新唯一audit root为`outputs/stage106_off_financial_audit/ARM/RUN_ID/`；原095会计算法收据为account_checks.json，再新增reader_account_checks.json绑定原数学收据、106源、原095源、105实际失败/部分审计收据、104原completion及root106合同。失败保留reader_failure_lineage.json，不覆盖任何旧失败。

本实施仅作者资格，不能自称106代码独立接受；107将复核该窄边界。071/087资格仍只继承外部审查，不由其原作者本次重签。原A0受限fixed-pairwise反事实、原全局A1失败N/A、母胜率未完整核、PIT/OOS/成本压力/多周期/分钟峰值限制均保留。期末权益、收益、DD、Sharpe、滑点、交易数没有新增，胜率N/A；original_goal_achieved=false、production_qualified=false。

105部分收据：`outputs/stage105_A_OFF_independent_financial_review/review_receipt.json` SHA `8ecee989eb9a4acbe751e7abd7fefed14ff327c42ad141ee842445e900274f6a`；唯一105中文记录`20261018_0744_stage105_A_OFF_partial_independent_audit.md` SHA `fd999439d6da8cd352ea61f88e11f103cdcd2fda80163c748fd71964c3dd8048`。其现金/成本/完整指标前序通过与mother reader P1边界明确，没有改写旧失败为成功。
