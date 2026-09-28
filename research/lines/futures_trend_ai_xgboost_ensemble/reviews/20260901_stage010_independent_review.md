**审查结论**

`VERDICT: FAIL-CLOSED`，问题计数：**P0=0 / P1=1 / P2=3 / P3=3**。

Stage010 的审计包不能 clean pass，但其核心决策正确：`account_label_identifiable=false`，必须 fail-stop，**不允许扩展全rank标签、训练XGBoost或接入正式版**。

**主要问题**

- **[P1] “完整输入身份=True”仍是过度声明。**  
  身份合同覆盖了分钟K、主力映射、合约元数据和 `sys.path`，但遗漏了解释器启动时实际自动加载的根目录 [sitecustomize.py](/Users/bytedance/Desktop/person/vnpy/sitecustomize.py:27) 以及 `.py311/.../*.pth`。收集清单只覆盖了列出的树和分发元数据，[没有覆盖这些启动钩子](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage010_account_marginal_slot_probe.py:315)。同解释器、同cwd验证会自动导入该文件；Python官方也说明 `.pth` 可执行代码且随后自动导入 `sitecustomize`。[报告中的完整身份PASS](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage010_account_marginal_slot_probe/attempt_20260901T173902+0800_39286/report.md:5)应降为FAIL。[Python文档](https://docs.python.org/3/library/site.html)

- **[P2] C11在目标期先天不可交易，探针识别力不足。**  
  脚本按名次直接选 `lc.GFEX`，没有事前主力映射/上市资格门，[选择逻辑见此](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage010_account_marginal_slot_probe.py:157)。2022年5月19个交易日中，`rb`和`SA`均有主力映射，`lc`为0天，[映射证据](/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv:257544)。因此C11必然无法产生边际标签。

- **[P2] 没有保存候选信号及阻断原因。**  
  目标期11笔成交仅涉及 `au/FG/fu/jm/MA`，[没有rb/lc/SA成交](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage010_account_marginal_slot_probe/attempt_20260901T173902+0800_39286/arms/A1/trades.csv:435)。现有产物无法区分“没有信号”“被保证金/持仓上限阻断”或“信号未成交”。

- **[P2] Stage009不是当前m0005的完整历史排名。**  
  Stage009截至`2026-07-31`，[审计记录](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage009_formal_full_ranking_recovery/audit.json:11)；m0005新增`2026-08-31`月池。它足以支持本次2022-04探针，但不足以支持“当前线上全月份rank10..18扩展”。

- **[P3]** 机器“决策日前路径”门只比较曲线，未比较交易和事件路径；本次我独立核验交易也一致，但门本身偏弱。[代码](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage010_account_marginal_slot_probe.py:544)
- **[P3]** C文件还重写了固定`fu`的分数和`score_type`，所以文件层面不只是第10行变化；当前引擎只按成员资格放行，因此不影响本次行为。[代码](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage010_account_marginal_slot_probe.py:181)
- **[P3]** 汇总里的`window_label`仍写到`2026-05-29`，实际`analysis_end=2022-05-31`。[汇总](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage010_account_marginal_slot_probe/attempt_20260901T173902+0800_39286/summary.csv:2)

**确认通过的事实**

- m0005确为当前active material release；生产HEAD为`d492ee07...`且与`origin/master`一致、工作区干净，257项release checksum通过。需注意`CURRENT.json`仍标明`production_qualification_pass=false`，这里只确认正式物料身份，不代表完整生产资格。
- m0004为623行、m0005为634行；前623行逐值一致，只追加`2026-08-31`的11行。`2022-04-29`历史月完全不变。
- Stage009该月18品种排序与m0005前10成员、顺序、分数零误差；rank10=`rb`、rank11=`lc`、rank18=`SA`。
- 四臂行为层只替换目标月第10席位；其他月份、Top9和固定`fu`成员不变。
- 四个独立PID、四套独立`TMPDIR/MPLCONFIGDIR`；单臂56至76秒。
- A1/A2及C11/C18的1069日曲线、444笔交易、汇总全部一致；决策日前曲线和交易也一致。
- 标签独立重算均为：基准权益`4,813,578.80`、期末`4,075,878.80`、收益`-15.3254%`、最大回撤`-15.3254%`、净亏损`737,700`、滑点`19,260`、交易`11`笔。

因此，`account_label_identifiable=false`计算正确。它表示**本月没有产生可比较信息**，绝不表示三个候选等价。XGBoost LTR需要同一query内有可比较的relevance label，相同标签不会形成有效排序对。[XGBoost官方文档](https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html)

下一步只允许只读资格审计：先冻结可交易候选月份、补齐m0005完整18名、保存候选信号及阻断原因、把`.pth/sitecustomize`纳入身份合同，再另立预注册探针。不得直接扩展回测或事后挑有差异月份。

过拟合判断：本次只读审查不是过拟合；依据本月零差异挑月份重跑会构成过拟合。继续价值：原Stage010形状无直接扩展价值，事前资格审计仍有价值。本次未修改文件、未运行新策略回测。
