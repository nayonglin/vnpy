# Stage167 会员集中度54维公平对照与完整域K选择实现

时间：2026-10-19 02:27 CST；line_id `futures_full_market_long_signal_ai`。先读registry/LINE、Stage164设计及root Stage166冻结协议。仅新增本stage、`tools/stage167_member_concentration_fit.py`、`tools/test_stage167_member_concentration_fit.py`；不改LINE、registry、166、旧源码/数据或正式物料。不是重要突破；**当前只实现/有限单测，0真实研究训练/现金/SQL/网络/新标签/原会员raw重处理**，累计仍397 fit / 210 cash；金融指标均N/A。

166协议16409B，SHA256 `ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a`，代码硬绑定。165来源接受是固定lag归档研究口径；不是首发PIT、alpha或可加注资格。实现沿164唯一问题：固定学习器加入q，在两臂共同、不修改的原155 K执行环境下是否增量有效；不复活159失败K、NFC、OI或FX包。

## 训练与全域约定

两臂 `CONTROL54` / `CONCENTRATION54` 共用原130成熟训练身份、family-held SHA256分组、family-u interval-union权重、原COMMON26中心/尺度及26missing、原stress first-exit目标。新增共同q缺失二元格及最后一格：CONTROL的**最终设计值恒0**；CONCENTRATION仅由本fold成熟训练有限q的正权加权均值/方差标准化，缺失标准值填0但保留共同missing。没有按q可得性或K后来成交/闭合删训练行；没有clip、变换/符号/阈值/模型/参数搜索。

六fold（2020/2023 cutoff × main/held0/held1）先全部计算来源支持及q统计，任一无有限q或非正/非有限方差，先写preflight并全局no-go、0fit/0cash，不先跑其余fold。全通过才两臂各6次Ridge：alpha1、intercept、cholesky不变。每次attempt在fit前记，completed在真实fit返回后立即记；后续正规方程/输出失败不会抹掉已完成fit数。实际训练不由本agent启动。

读取仅166中13项fit必需角色：execution_protocol、voluntary_protocol、dataset_manifest/actions/common/mothers/dataset_terminal、member_manifest/member_projection/member_review_receipt/source_acceptance、calendar/market_protocol。大129数据及已接受162投影继承原SHA、核尺寸与读前后stat、完整身份对齐，避免为hash另扫334MB动作表；只消费一次真实数据，不读旧模型/预测、raw或native缓存。source_bundle绑定本实现/测试及130/071/156三个实际代码依赖。

每臂main前向966740 child、161014 parent；两个held联合也各966740 child、161014 parent，总前向分数3866960。所有原母/动作、未就绪/无观察/缺q保留。child分cell流式写，按原action sequence bitset核每arm/main及heldunion完整性，不构造旧正分/赢家子集。每scope独立把输入scope临时alias main调用156纯选择，再恢复原scope/arm：D<K在argmax前，原正分/同分/ordinary-F优先不变，绝不把两个held scope混选。

实际前root指出母域为product-major，按cutoff拼接会打乱每arm原母顺序。现只在输出choices_main/holdout前稳定sort `arm,sequence_index`（heldunion不先按scope排），恢复原全父顺序；选择和分数不变。初版实现/测试freeze `765eb147…de302bf` / `bfa138d2…faf5f0e` 已撤销、未actual。

## 输出接口（已与168/169协调，当前尚未生成真实输出）

manifest schema=`stage167_member_concentration_fit_v1`，成功status=completed、cash_eligible、protocol及protocol_sha256、12次actual_model_fit_calls/attempted/completed、terminal binding、source_bundle、13项input_bindings及继承身份/stat证据。新输出各hash一次，已有引用不重散列大源。

- 每六fold共享 `folds/<scope>/<cutoff>/training_identity_weights.csv.gz`、`weight_groups.csv.gz`、`scaler.json`，保留成熟身份/目标、q原值/missing、union组/区间/权重、COMMON统计与q有限权重/均值/方差/尺度；两臂不各造另一训练mask。
- 每臂fold一个portable_model.json（coef54/intercept/parameters/feature_names/scaler binding）和normal_equations.npz（lhs55×55、rhs55、coef+intercept55、weight_sum），fit_records共12条。无须加载或重存旧joblib。
- 顶级binding `choices_main` / `choices_holdout` 各322028行；原131兼容身份、chosen/proposed action、epoch/anchor、score、selected/state、u/cutoff/scope/arm/policy均保留，每arm161014原母序。
- `child_scores` 含原130完整前向score字段、scope/arm及member_q_raw/missing/design；`preflight`给六fold收益前来源支持；`fit_records`保存共享训练/缩放与12模型方程引用。
- `boundaries` schema=`stage167_voluntary_epoch_boundaries_v1`，含166 SHA、原155 policy_version、not_certified=true、完整calendar binding、sample_end和所有forward epoch的原156 K状态。样本外K不夹成最后源日；这里只有自愿K，原/有效生命周期由168现金侧补 trace。
- `held_diagnostic` / `held_daily` 纯复用130原target诊断，临时A/B明确映为CONTROL54/CONCENTRATION54，顶层 `stage167_original_target_held_diagnostic_v1`、target明确不是K截断收益。两held组及年份、负值、差异unknown和共同未决同action增量0保留；已知部分均值非负只是nominal必要条件，未知无界不认证泛化。
- started/terminal、fit_attempts/fit_completed检查点、summary/manifest保存实际预算与计数。失败保留、不自动retry；preflight no-go不启动模型或现金。

## 有限验证与最终冻结

使用TDD：初始六fixture因实现缺失RED，随后GREEN；root要求的跨cutoff顺序fixture先RED后GREEN。最终命令：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage167_member_concentration_fit.py -v`，**7/7通过，0.761秒**。只用合成数据，每次测试包含两个2样本Ridge数值fixture；没有加载真实训练集，不计真实研究fit。未跑旧suite或金融。

七项保护：有限q加权统计与CONTROL最终恒0；任一坏fold全局no-go；原action/独立mother身份及真零/缺失对齐；完整child先K再重选与held/noobs父保留；同分与普通F优先；手算Ridge2/3系数及正规方程/完成checkpoint；product-major跨cutoff恢复原父序。

最终锁定实现27521B，SHA256 `05acd031f0132bfb43368c779f5fd44470415d0eb5d0428c0ca2007a53e775d3`；测试7625B，SHA `8ca88b06de1dfc7d9ef69065b424247e6573401635b15ec3682bfe92b7af34bc`。root/169已静态实读主体，未见设计阻断；尚不是实际新模型/输出验收。源码/测试锁定，后续仅本stage可补root实际事实。

root签 `stage166_exact_root_authorization_v1`（authorized_by=root、stage=fit、exact_source_authorized、166 SHA、绝对output、exact source_bundle、13项input_bindings）后唯一CLI：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage167_member_concentration_fit.py --protocol <166path> --protocol-sha256 ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a --authorization <rootauth> --authorization-sha256 <hash> --output research/lines/futures_full_market_long_signal_ai/outputs/stage167_member_concentration_fit/actual_run1`。本agent未执行。

开始/结束新增收益后救参过拟合：**否，本轮按166结果前合同实现，顺序修正不看收益**；长期同史择题与弱PIT风险仍是。继续价值：**是，仅这一次公平固定信息对照**，真正金融支持等root唯一12fit/最多8cash及169独审；若无支持不改K、q表达/方向、模型、止损、风险或品种年份救参，不加注，不宣称原全市场目标完成。

## 02:31 root唯一actual补记（尚未独审accepted）

root以最终 `05acd031…e775d3` / `8ca88b06…af34bc` 字节及exact-source授权执行唯一actual，终态exit0、**12 attempt / 12 complete**，耗时 **173.828833541秒**；0新cash/SQL/download、无自动retry。累计在本次fit完成时为 **409 fit / 210 cash**。本agent仅读同目录小型preflight/terminal/summary/held_diagnostic，没有大CSV、raw、新测试或模型重跑。168另行实际现金及169独审结果不在本补记范围内，不提前写accepted。

`outputs/stage167_member_concentration_fit/actual_run1/preflight.json` 显示六fold全局ready、failures为空，先于第一fit授权12次；以下为原成熟训练域支持：

| scope | cutoff | 原成熟训练动作 | 有限q动作 | q加权方差 |
| --- | --- | ---: | ---: | ---: |
| main | 2020-01-01 | 247795 | 46155 | 0.0023590624295675533 |
| main | 2023-01-01 | 445475 | 81320 | 0.0024305031919726276 |
| holdout_0 | 2020-01-01 | 171712 | 27692 | 0.0019073576990254484 |
| holdout_0 | 2023-01-01 | 297404 | 47417 | 0.0018462811559677224 |
| holdout_1 | 2020-01-01 | 76083 | 18463 | 0.002661849428666631 |
| holdout_1 | 2023-01-01 | 148071 | 33903 | 0.0029870636212588468 |

`summary.json` 报告完整3866960前向分数；每arm main/heldunion均161014父，原完整域没有按q可得/原B赢家缩小。main最终选择CONTROL54 **4901**（2020段2953＋2023段1948）、CONCENTRATION54 **4894**（2947＋1947）；这是策略选择数，不是实际成交或现金收益。

`held_diagnostic.json` 的原first-exit目标、family-u后等u增量：holdout_0为 **+0.00007557592272947191 R**，nominal_pass=true；holdout_1为 **−0.00008459416254548117 R**，nominal_pass=false。两组差异动作unknown均0，但同一共同选择动作未决分别35/41，按预定规则只令同动作的增量0、保留原未决披露；不能解释为原交易全已确认。两held必要门未同时通过，**不得签泛化**。这些是旧目标诊断，不是K截断收益或168账户结果，`generalization_fully_qualified=false` 保持。

小文件引用均在 `outputs/stage167_member_concentration_fit/actual_run1/`；root提供并核定新manifest32254 B、SHA256 `eca554f90cda62a887b0d59952f7e316cb0a9e2d98a860cb7062158653c465db`。当前只记录唯一fit执行及其原目标诊断，独立169完整模型/分数/选择审查未accepted；不增加任何模型、K或风险救参。
