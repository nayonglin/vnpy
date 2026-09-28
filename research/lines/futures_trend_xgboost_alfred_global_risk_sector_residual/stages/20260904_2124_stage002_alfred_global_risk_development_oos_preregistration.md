# Stage002 ALFRED全球风险板块残差development OOS预注册

- line_id：`futures_trend_xgboost_alfred_global_risk_sector_residual`
- 记录时间：2026-09-04 21:24 CST
- 阶段性质：本线首次且唯一标签访问、A/B/C训练和产品贡献路径development OOS预注册。
- 前置决策：`stage001_alfred_global_risk_contract_pass_allow_stage002_preregistration_only`。
- 是否重要突破：否；本文件写入时尚未读取标签或训练模型。
- 用户目标：提高全周期收益、降低最大回撤。
- 用户授权边界：用户已明确后续研究操作默认授权；执行前仍生成绑定本文件、实现、测试和输入SHA的单次receipt。生产、CTP和订单硬门不变。

## 研究问题与第一性判断

冻结的15项全球状态特征在同一月份、同一板块内完全相同，不能识别板块内品种。若让它们替代正式LR直接选Top10，会把同板块品种交给代码字典序，违背正式排序语义。因此：

1. A保留正式108特征LR，承担品种内排序；
2. B只检验15项全球状态是否独立含有标签信息，不作为晋级或Top10候选；
3. C以A的raw log-odds作为`base_margin`，只允许15项特征学习板块级非线性残差，是唯一晋级候选；
4. 最终效果只比较C相对A，要求未来贡献与路径回撤同时改善。

## 冻结输入与PIT

- 正式release：`m0005_20260901T165450+0800_1961d98ccb2b`；strategy：`ai_top10_plus_fu_official_live_v1`。
- Stage001 summary/manifest SHA256：`64c8b9903750e3600dfae0fabec74f6b611656a0b271321521984f0fb7154619` / `94161cb2e7a300c9a60e770f2a5cbc7426d26e734b461d7ded541a8a73eb447f`。
- Stage001 fold-plan/interaction-panel/feature-contract SHA256：`a14fbde27943e1c73eaa8c1e2ea14834e212616e82fe024ba193697369a25e6c` / `3837f272d24e573431b0be145d49b5b71b4384fc930e5ca05d28213be7a617ee` / `a13e5252f0cc7c4d8fc1d28ec288675d12f35b1a701a57f42be4cf7d99bfdfc7`。
- 正式108特征合同SHA256：`64909eeca4d84348c9adea29062430d8010b0e194ab87edd37169752facfb182`；Stage002必须逐名匹配，不只检查列数。
- 前序已审计Stage002实现只作为接口参考，SHA256 `782d76b8620db93a5a760ba9e838333e237439b2b99ae0b65989115f99a8a1c4`；不得读取或复用其失败结果作为本线输入。
- 使用Stage001冻结的50个fold；每折一个测试月、18品种，共900行development OOS预测。
- 训练月直接来自`copied_fold_plan.csv`；每个训练月正式60交易日label end必须`<= test_eval_date`。
- 正式108项历史特征只由已审计`causal_formal_features.build_causal_rolling_features`生成，该函数禁止任何`future_/target_/sample_weight_`列；先投影到Stage001冻结的1,386个`eval_date + product_vt_symbol`键，再允许构造标签。
- 每个冻结键的未来值只读取该键之后恰好60个全局交易日的`net_pnl`，禁止为其他日期或产品生成标签行；随后严格复现正式公式：横截面`rank(method='average', pct=True)`、`future_rank_centered_60d=rank_pct-0.5`、`target_future_top_half_60d=(centered>0)`、`sample_weight_future_rank_60d=abs(centered).clip(0.20,0.60)`。
- 标签生成行必须精确为1,386，冻结键缺失/额外键均为0；排序质量使用`future_rank_centered_60d`。这与正式标签语义一致，但避免正式整表函数先计算未授权日期的未来值。
- ALFRED交互面板按`eval_date + product_vt_symbol`一对一连接正式面板；连接前后必须保持1,386行、77月、18品种、15特征，缺失/重复/非有限值均为0。
- 全部`2022-03..2026-05`测试月只称development OOS；sealed holdout读取0。固定`fu.SHFE`不进入模型、预测或效果代理。

## 冻结A/B/C

### A：严格PIT正式LR

- 特征：正式108项。
- 每折`StandardScaler`只拟合训练行。
- `LogisticRegression(C=0.20, solver='lbfgs', max_iter=3000, random_state=42)`，使用正式样本权重。
- 输出`score_a`和raw `margin_a`。

### B：15特征standalone XGBoost诊断

- 输入只允许Stage001冻结的15项数值特征，不做scaler，不允许产品ID、月份、年份、sector字符串、正式108特征或新增字段。
- 不传`base_margin`；每折用同样训练标签与权重拟合两次，重复预测最大绝对差必须为0。
- B只报告加权logloss、月均Rank IC、split和分数离散性，不参与Top10效果门或晋级。

### C：正式LR base-margin上的15特征XGBoost板块残差

- 输入仍只允许同一15项特征；训练与测试分别以A的raw margin作为`base_margin`。
- 每折独立拟合两次，重复预测最大绝对差必须为0。
- `raw_correction = logit(score_c) - margin_a`；C是唯一晋级候选。

B/C参数完全相同并冻结：

```text
objective='binary:logistic'
eval_metric='logloss'
n_estimators=32
max_depth=1
learning_rate=0.03
min_child_weight=20
gamma=0.1
subsample=0.8
colsample_bytree=0.8
reg_alpha=1.0
reg_lambda=20.0
max_delta_step=1.0
tree_method='hist'
random_state=42
n_jobs=1
```

- 环境固定XGBoost `3.2.0`、scikit-learn `1.8.0`。
- 不扫描参数、不early-stop、不blend、不改LR、不做特征选择、不重跑第二个种子。

## 产品贡献路径代理

- 每个测试月按`score_a`和`score_c`降序、`product_vt_symbol`升序稳定选Top10；B不选Top10。
- 每个产品未来路径固定为eval-date之后恰好60个全局交易日的正式`net_pnl`；禁止当日和第61日。
- 每臂月度路径为10个产品逐日`net_pnl`之和；贡献为60日路径之和。
- 最大回撤从0起点计算，对`[0, cumulative_path]`取`min(equity - cummax(equity))`。
- `return_delta = C贡献 - A贡献`。
- `drawdown_improvement = C最大回撤 - A最大回撤`，正数表示C回撤较浅。
- 该结果只是产品贡献代理，不含固定fu、资金、整数手、相关性、保证金和真实执行；不得称期末权益、总收益或真实组合最大回撤。

## 技术硬门

1. receipt、预注册、实现、测试和全部输入SHA一致；Stage001 241文件manifest复验有效；最终输出不存在并原子发布。
   - receipt的每个绑定名必须对应代码内冻结的规范绝对路径；静态输入还必须命中代码内预期SHA，禁止receipt用“自报路径+自报SHA”替换输入。
   - receipt必须包含合法UUID authorization nonce；验证过程一次读取原始receipt字节，同时得到解析对象和SHA。一次性执行权必须在任何标签访问前用`O_CREAT|O_EXCL`原子marker抢占，并绑定同一次读取所得nonce与SHA；marker已存在时不得覆盖、不得读取标签。
   - 原子抢占必须通过两个独立进程同时竞争同一路径的测试，结果精确为一个成功、一个`exists`，不能只做顺序重复调用。
2. 50 folds、900预测行、每折18品种；正式LR特征108项、全球状态特征15项；LR/scaler fits=`50/50`，B/C各重复拟合两次，总XGBoost fits=`200`。
3. 标签生成1,386行且缺失/额外键0；PIT审计把缺失label-end视为违规，违规行/折必须=`0/0`；sealed holdout行0；固定fu模型行0；Stage001面板join缺失、重复和修改均为0。
4. A/B/C概率、A raw margin、C correction、标签代理和路径指标全部有限；每月A/B/C分数横截面标准差都大于0。
5. B/C重复预测最大绝对差都为0；B/C各自split nodes总数`>0`且有split的fold都必须为50。
6. C correction绝对值中位数`>1e-6`且`<=0.5`，最大值`<=2.0`，防止退化或覆盖LR先验。
7. 标签读取只允许正式1,386行面板；development OOS标签恰好900行；true engine、CTP、订单和生产写入均为0。
8. 独立重建50个OOS月的60日效果路径；900个产品月的路径和必须在`1e-8`内逐行等于模型标签`future_net_pnl_60d`，路径末日必须逐月等于fold-plan冻结`test_label_end`，缺失/和值错配/末日错配均为0。

## 执行前独立代码审查收紧

- 2026-09-04标签读取前独立review首次结论为`BLOCK`，指出整表标签生成、非原子marker、自报receipt路径和NaT/路径同源校验四类缺口。
- 本节以上约束是在任何Stage002 receipt、标签读取或模型fit之前加入；只减少执行自由度，不改变特征、模型参数、fold、标签公式或效果阈值。
- 修复必须通过新增失败测试和第二次独立只读复审后，才允许生成SHA receipt并消耗唯一运行权。

## 效果硬门

以下全部以C相对A计算，必须同时通过：

1. C加权logloss严格低于A，C月均Spearman Rank IC严格高于A。
2. A/C Top10不同月份至少8个，覆盖至少3个年份。
3. changed months的`return_delta`合计`>0`，`drawdown_improvement`合计`>0`。
4. 删除单个最佳return-delta月后，剩余return delta仍`>0`。
5. 删除单个最佳drawdown-improvement月后，剩余drawdown improvement仍`>0`。
6. changed months中`return_delta>0 && drawdown_improvement>0`比例`>=0.55`。
7. 每个发生变化的年份，年度return delta和年度drawdown improvement都必须严格`>0`。

通过：`stage002_alfred_global_risk_development_oos_pass_require_independent_review_before_true_engine`。

失败：`stage002_alfred_global_risk_development_oos_fail_close_no_true_engine`。

无论通过或失败，只要产生效果结果，必须先完成独立review；通过也只允许预注册Stage003真实引擎A/C，不允许直接接入正式版本。

## 禁止救援

- 不得看结果后改树参数、特征、板块、窗口、LR、权重、TopN、标签、fold、日期、年份、品种、路径、门槛或tie-break。
- 不得删除失败月/年、把B改成候选、增加blend权重、只报告有利子集或重跑第二次效果实验。
- 任一门失败即闭线，不运行真实C9、holdout、shadow或生产接入。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：Stage002均不适用。

## 过拟合反思

- 运行前判断：是，高风险。
- 原因：全部development月份已被多轮研究观察，且有效宏观状态只有308个month-sector单元；预注册和固定浅树只能减少自由度，不能制造独立holdout。

## 继续价值反思

- 运行前判断：有，限本次唯一Stage002。
- 原因：全球美元/人民币/VIX状态是独立PIT信息源，C只改变板块残差而保留正式LR品种内排序；严格联合收益/回撤门可以用一次实验快速证伪。
