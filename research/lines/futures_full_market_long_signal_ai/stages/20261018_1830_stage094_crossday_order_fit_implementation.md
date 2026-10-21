# Stage094：当前跨日NARROW目标的固定181项ORDER/BAG实现

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 18:30 CST。
- 阶段性质：092冻结合同的模型实现/预审交接；当前094 actual0；重要突破否、正式A/B/晋级否。
- 沿当前checkout，仅新增094源码、4个必要新测试、本文及小实施收据。093 source冻结且其唯一prepare完成；090/086/071/024/070和LINE/registry/其他线/正式生产不改。
- 协议SHA `580c59d77964b27372570b2d48e197ce7a75f5edd77dac0a9aa5e42548d3a736`。完整目标继续为全市场高质量做多、窄损生存、更高成本后收益且更低DD，当前实现并非成果证明。

## 固定桥接与纯定义复用

只引用accepted071的成熟训练/权重/有限统计/共同背景标准化，086的纯fold选择和closed-only held诊断，024的pure `make_mapping/canonical_bag`；不调用旧024 fit、DAY目标、旧日期权重、mask或report，不修改或monkeypatch旧定义。

共同线性背景53列为当前26标准化值、同26missing和共享sequence_missing；S11直接使用前11列同一训练统计。RFF输入仍91=S11+原20×4，W_base91×128、b128仅调用旧固定seed20261018映射，`sqrt(2/128)*cos(z@(W/sqrt91)+b)`。ORDER/BAG共同181项头加intercept，alpha1/cholesky/单线程。这是旧139增加42共享项的新桥接，不称旧容量未变，也不加COMMON臂。

序列四通道尺度只取本fold当前成熟训练、可观察tensor的原量化值，每事件权重分给20位置，所有位置pooled；缺tensor行不参与通道统计但不删训练/预测行。common统计仍接受071原定义。缺tensor时标准化80维直接为0，两臂RFF完全相同；绝不把raw0再标准化成假历史。全missing mean0/std1，有值但数学常量则原值mean/var0/std1。

必要合成检查发现一次数值根因：w/20重复权重求常量7的均值时出现约3e-15舍入差，导致数学常量误生极小正方差。已用原量化通道值**exact相等**识别常量，固定var0/std1；不引入近零epsilon、不修旧071 common、不扩成旧数值审计。非常量仍用同pooled w/20统计。非恒定均值测试使用正常浮点断言容差，未改变科学门或actual数据。

## 母体、模型与存储

093 completed manifest/terminal/完整alignment先精确绑定，原ID序与legacy_tensor_index/missing逐项核对；tensor只在094 actual获准后按092旧SHA加载一次，不重建、不SQL、不读旧DAY标签。旧21bar tensor资格不变成当前20ready动作门。

2cutoff×main/holdout0/holdout1×ORDER/BAG=12 planned actual fit；当前自身NARROW闭合成熟、u与known严格早于cutoff，held训练排除该组后重算当前权重/scaler，预测只对应held组。完整母体399252；每arm main161014、held并集161014，总644056前向scores。动作只ready20且finite score>0，未知/未成熟/取消不填0。

不保存181列或其他巨大重复头缓存。每fold只保存训练身份/当前标签区间及权重、prediction identity、train-only scaler；一次全局W/b、12个joblib/portable模型及182×182正规方程、全部前向预测、年度/family/状态/缺失指标与held closed-only u等权诊断，头由bound X和小资产重建。manifest每个新资产显式role、reproducibility_required、raw_ohlc=false。

actual目录预期`outputs/stage094_crossday_order_fit/experiment/`，尚不存在。manifest schema=`stage094_crossday_order_fit_v1`，binding keys=`predictions`、`predictions_main`、`predictions_holdout`、`held_diagnostic`、`held_daily`、`held_linkage`、`rff_mapping`、`terminal`。pred列沿086 ID7+policy NARROW/arm ORDER或BAG/scope/cutoff/history_ready20/selected/score及sequence_missing；095只消费main，不拼held入现金。

held统计严格复用086已接受closed且known<=end、ready20共同域，按`(I_ORDERpos-I_BAGpos)*net_R_stress`每u已知机会平均再u等权；未知/取消不补0，全部label状态和动作差异保留。诊断报告schema=`stage094_held_closed_diagnostic_v1`，groups保留nominal_pass/status/known_u_equal_mean_increment_R/unknown_differential_selected_events/prediction_u_equal_MSE_difference，contrast明确ORDER_minus_BAG。MSE和closed-only指标不是现金收益。

## 新TDD与精确授权交接

4项新行为先RED模块缺失，再实现；初次GREEN前暴露上述常量通道问题，根因诊断与修复后最终命令：

```text
.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p 'test_stage094_crossday_order_fit.py'
```

最后真实输出`Ran 4 tests ... OK`、exit0。覆盖当前fold可观察训练pooled统计与未来tensor毒值隔离、181共享背景/缺tensor标准化0/RFF相同、全missing/常量语义、2个小fixture Ridge/portable181/完整未知预测与不落盘头缓存。未重复071成熟、070报价或旧suite。作者必要运行累计6次小fixture fit，**研究actual fit0**；AST与CLI --help通过，无真实数据载入。

新CLI仍四参数`--output --protocol-sha256 --authorization --authorization-sha256`。auth schema=`stage092_exact_root_authorization_v1`、stage=fit、root与精确source_bundle/协议SHA/freshout/input_bindings必须匹配。input_roles恰8个：common_npz/common_identity/narrow_labels/narrow_manifest、prepare_manifest/alignment/prepare_terminal、tensor；前四与tensor沿092精确binding，准备三项必须来自同一093 completed manifest。source_bundle六个文件的最终binding在小implementation_receipt中。

root在096一次源码预审后再签actual；失败保留attempt/completed计数与terminal，不自动修复重启。实现完成与093接线完成都不授权模型actual，更不授权095现金。

## 调研判断与反思

沿090/092已核[Deep Sets原论文](https://arxiv.org/abs/1703.06114)及[作者仓库](https://github.com/manzilzaheer/DeepSets)的有限判断：位置与集合约束可有不同信息，但固定RFF几何偏好仍在，ORDER胜BAG不证明模型无关优势或优于现有COMMON，更不保证收益/DD。未借实现增加新特征、模型、seed、窗口、目标、stop或风险；旧DAY失败与停止门保留。

新增/修改/删除策略参数0，明确新增共同181桥接但收益前冻结；新增/修改/删除金融结果0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全N/A。094实际SQL/tensor载入/fit/cash/labels/download/大库hash均0，累计345researchfit/78cash不因fixture改变。

开始与结束是否新增收益择参过拟合：**否，严格实现单次收益前合同且0actual；历史曝光、旧失败先验与表示选择风险仍有。** 继续价值：**有，限已冻结的ORDER−BAG当前目标迁移检验及独立复核**。若未来固定包失败，不扫表示/容量/目标救援，不把工程完成称作全市场高质量long或窄损加注资格，完整goal仍active。
