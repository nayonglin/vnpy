# Stage062：交易合约自身周线候选资金总览适配器

- 时间：2026-10-19 20:16 CST；研究线 `futures_trend_full_market_noai_one_lot`。
- 重要突破：否；只读展示入口，不产生金融证据，不改原策略/阈值。
- 新增：`tools/stage062_contract_weekly_overview.py` 及对应 test；未改旧模块、金融、LINE或旧输出，未执行Git写操作。

## 展示与来源合同

严格使用 `weekly_policy.source=exact_traded_contract_unadjusted_accepted_clean`，其余5/10/20/40、严格排列、40有效完成周、signal/open相位、所有开多含移仓、env_probe豁免、空头/平仓不新增门槛与既有固定合同一致。源证据三份为 `weekly_contract_features.csv` / `weekly_signal_audit.csv` / `weekly_execution_audit.csv`；实际授权对应 `stage059_weekly_signal_snapshot` / `stage059_weekly_open_snapshot`。

复用 Stage055/042 及 Stage032 AST 图表。为避免修改旧文件或污染旧模块 globals，通过独立 namespace 调用原 Stage055 纯显示函数，只替换来源政策/披露常量与当前生成器身份。测试确认原 Stage055 的主力周线 policy 不变，相同 C 数据生成的图形 JSON 与直接 Stage042 完全相同。新增比较表不改变曲线：仍只绘制当前 C。

显式要求原预算 A `--baseline`，以及上一主力周线 C `--previous-main`；两者目录及全部文件/快照 hash 严格核验，来源 SHA 必须等于新 C manifest/summary 的冻结引用。原 A commit 为 `87487e32d36a443942f612ac7eeef71ede9ea46a`；上一主力周 C commit 为 `12f9d3500305ad0da47e092c8c39177459d228ec`、已知 manifest `7e6f2647de1d99253ba2cbade3e0852158d50d3cbfde19e8da4afdba6f16fed4`。核 A/C 同参数/区间/本金/原native预算/数据；核上一主力周政策、同参数/区间/本金。页面同时列原 A vs 当前合约周 C，以及上一主力周 vs 当前合约周，明确描述性比较、不作为晋级结论。

标题/说明明确“交易合约自身、不用主力连续”，周K及周MA改为自身合同；其他周期原 canonical 上下文可能不同，不能混作门槛证据。保留预算复核、最多1手、无AI、无品种数上限、日线近似、残仓及全部源边界。

## 验证

- 先 RED：新入口缺失，合同测试明确失败；再实现至 GREEN。
- Stage062/063 合计 **10 tests PASS，1.841 秒**；包含同图逐字相同、旧模块常量不变、错误主力政策/previous身份/产物篡改拒绝、目录隔离，以及真实临时目录生成PNG/HTML/JSON/CSV并检查所有输出hash。
- 本线全部 **216 tests PASS，27.321 秒**；`git diff --check` 通过。全线测试导入既有TqSDK标准免责声明，没有行情/CTP连接。
- Stage062 SHA256：`1836ad6c7dbba330c25793b1e43e94e01b3976be76e0a26e1cbca7f1aa882521`。
- 调研沿用 Stage055 的 [Plotly官方导出](https://plotly.com/python/interactive-html-export/) / [GitHub文档](https://github.com/plotly/plotly.py/blob/main/doc/python/interactive-html-export.md)，判断继续复用离线原图最稳妥。

## 参数、结果与后续

- 新增金融参数：无；修改/删除金融参数及结果：无。只新增显示CLI `--previous-main`，不改变回测结果。
- 当前未生成新真实 overview，等待根任务唯一金融完成及 `025→045→063→020` reviewed parent 冻结；不以旧 A/主力 C 指标当作新合约周 C。
- 过拟合：本展示工作否，无收益选参；金融候选的同样本事后提出条件限制仍须保留。继续价值：是，允许精确比较语义改变后的结果，不构成晋级证据。
- 未跑金融、未下载、未生产/CTP/订单调用。新产物仍需逐点、JS及浏览器验证。

```bash
/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage062_contract_weekly_overview.py \
  --source NEW_COMPLETE_CONTRACT_WEEKLY_RUN \
  --parent NEW_REVIEWED_EXACT_WEEKLY_RECAP \
  --baseline research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261019_native_budget_one_lot_v1 \
  --previous-main research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261019_weekly_long_v1 \
  --output NEW_CONTRACT_WEEKLY_OVERVIEW
```

### 20:26 真实合约周线总览已生成、独立验证PASS

已按根任务明确授权生成 `outputs/overview_20261019_contract_weekly_long_v1`，parent为 `outputs/recap_20261019_contract_weekly_long_v1_reviewed`，命令退出0。source仍 `859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`；parent summary `01307eddd3923788c854589874daeed46f217ade83a9d4e5d73a8eadba9e0a93`；A/上一主力版本绑定不变。

完整机器报告 `20261019_2016_stage062_contract_weekly_actual_validation.json`：155项源/A/上一主力C/parent/output/代码哈希绑定PASS；2,862个日期及equity/高点/金额回撤/百分比回撤逐点重算PASS；三条完整Plotly曲线各2862点、最大DD点、两面板与共享x轴正确。CSV显示末位最大差2.33e-10元、2.31e-14个百分点，不改金融结果。HTML内嵌data/layout与figure.json逐值完全相同；两张比较表共24行全部来源值及差值准确；源边界及stage059证据披露完整。3段JavaScript经bundled Node `--check`通过；PNG尺寸2240×1200，已目视两面板清晰、期末120.51万元和2024-08-30最大回撤-17.65%标注正确。

| 输出 | 字节 | SHA256 |
| --- | ---: | --- |
| index.html | 5,132,570 | `4c07f9711b2ccabccb5ea511de442d8a630498fa6910b02a26fc4b69f8b79c3d` |
| equity_drawdown.png | 282,061 | `e1022a20c01c9b83b0f11aaf2e5b449accdb40cc51be7d58a8fcf6167ef5fb1d` |
| equity_drawdown.csv | 245,480 | `022b3daf458e109100624228f63efdfb37ded967201e81449abf95ad4d222e77` |
| figure.json | 281,231 | `9a928f048c17f9fca9c75b1f135f660a5e03bb1943b7d0a82ee479577024a67d` |
| summary.json | — | `66e0ff2e7278a0aefe5472967246d120c1dd956c8b7d05fd30e667d1dc6848d5` |

原预算A收益83.207063%/DD-18.346986%/Sharpe0.405520；上一主力周C为12.888273%/-24.758359%/0.086829；新合约周C为20.510281%/-17.650750%/0.161625。相较上一主力周版改善，但收益和Sharpe仍明显低于原A；只作冻结描述，不作晋级结论。

未改冻结源码/测试，无金融再跑、下载或生产访问；浏览器缩放/复位由根任务验收，本机器报告保留pending_root。展示无收益选参，持续价值是准确区分三个版本的合同与结果。
