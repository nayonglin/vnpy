# Stage373：最新成熟PURE52单次训练薄入口

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 04:41 CST；非重要突破。按收益前冻结372协议实现，本文不签发实际授权。
- 新增`tools/stage373_latest_mature_refit.py`、唯一合成fixture `test_stage373_latest_mature_refit.py`；只写本线373工具/输出/本文，不改130、359/360/370初态或LINE/registry。

## 实现与绑定

冻结协议7908B，SHA `d854a77e3935f290c554399718f51f8bb775849372d39e8ecd88b9cd72c85001`。新工具20873B，SHA `d8a1fb886fe79b95e6c4e33c3c3973f05da715ceafdd3ad7c8b5716ce8598080`；fixture4805B，SHA `2a1bfb055e624c59a2f1ae25c7b435bdc858211553e1638f7f46df693e30a604`。

入口`prepare(output)`只读小协议/源码/129完成元数据，生成source_bundle与**未授权**root模板。`run_actual(auth, output)`中的auth为授权JSON的`{path,bytes,sha256}`精确binding；必须root、exact_source、main/cutoff/candidate、372协议、全部源码与输入、fresh输出和1fit/0预测/0cash预算逐项匹配。CLI `execute`另要求`--authorization-sha256`。本阶段没有调用actual。

原130/071整文件SHA先核，AST只提取130 `union_intervals/training_weights/design`、071 `finite_stats`及COMMON字面量；未导入旧全runner链。alpha1/intercept/cholesky及threadpool1保持，仍原129 net_R_stress单位、原26＋26missing52。新成熟全集重算原区间权重、train-only加权finite scaler，保留原回退，不改目标/风险。

实际入口将只读accepted actions334909637B、common146877351B各一次，读入bytes同时核原SHA后交BytesIO；无预先大hash、mothers、旧cache/econ/SQL或新标签。核全1552456行次序、必要alias身份、原26列顺序/float64形状；不重做parent资格。日期不得超过accepted16快照，u和非空label_known严格<20日、eligible/closed_complete/finite门保持。old2023同门只计数，须等于445475；新增成熟0则0fit停止，不换窗口。

保存训练身份/权重、family-u区间组、scaler、portable52、充分正规方程、old/new/added及最大成熟日期、attempt/completed/terminal、源/输入/runtime manifest。没有保存normalizedX大副本或joblib，未构造历史pred/choices/held/cash。失败保留输出、不自动重试；正常完成仍T1=null，不冒充root375新版本冻结。

## 唯一fixture与prepare结果

先RED证明工具缺失；随后两次前置失败均0fit：372旧cutoff字段带解释文字的校验适配，以及原权重AST函数需要json命名空间。只修根因，最终同一个方法`Ran 1 test in 0.786s, OK`，**合计仅1次合成Ridge fit，真实fit0**。不跑旧suite；开发现场计数见[fixture收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage373_latest_mature_refit/fixture_development_receipt.json)。

fixture手算重叠区间/member权重，核成熟cutoff/blank/unknown/open/eligible/nonfinite排除；扰动全部非训练行的X/Y不改变train/scaler/权重/设计；all-missing与常数列用原fallback；无新增样本在fit前返回。唯一拟合与独立加权53维正规方程解一致，`Ridge.predict`被禁止，历史预测0。它验证合成合同，不声称真实大表已验收。

prepare1实际exit0；[prepare_receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage373_latest_mature_refit/prepare1/prepare_receipt.json)3431B/SHA `77a3f9e5d02f0da585a361bdbf603ded4db856a183d69f853d831d651365d99b`；[root模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage373_latest_mature_refit/prepare1/root_authorization_template.json)2988B/SHA `1096e8a224d0c616715bfe4743fa810323d35c25ba2ad753a51b5085a5ec97fb`，authorized_by=null/exact=false。源bundle与模板最后小hash核对一致，未读取两大实体。

## 判断与边界

外部判断沿371已核的[官方时间序列文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)及[维护者评价文档](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)：允许固定规则吸收后续成熟资料，但不能把训练历史恢复为未见测试。本阶段仅落实372，不重复检索或新选参数。

- 真实fit/预测/选择/cash/API/下载/SQL/Git/订单/生产均0，合成fit1另计。金融参数/回测结果新增、修改、删除0；权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A，无alpha/加注资格。
- 开始/结束过拟合：本轮没有按新收益调参，否；既有历史择题偏差及新增版本自由度，是。继续价值：按固定协议准备有限未来候选有；旧史择优/重复回放无。完整目标active未达成。
- 下一仅由374独立静审及同fixture核验；root另签精确授权后才允许一次actual。最终交付后作者停止改源，不改T0或原账户初态。
