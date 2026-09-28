# Stage000 旧正式评分器PIT可重建性审计预注册

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 记录时间：2026-09-02 12:34 CST
- 阶段性质：只读法证/可重建性审计
- 是否重要突破：否
- 模型训练：0
- 策略回测：0
- sealed holdout标签读取：0
- 生产/CTP/订单影响：0

## 已冻结输入

- 旧评分源码：`analyze_qmt_roll_ai_product_suitability_walkforward.py`，SHA256=`7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4`。
- 当前品种配置：`qmt_universe.py`，SHA256=`8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f`。
- 旧daily：SHA256=`9af514a3a5ab7ca4d982a31bd758522c32c4dec792f1b1819abb5462a391efcd`。
- 旧samples：SHA256=`4cbc9952a1dac4373ac1901f958b914ac1d3495e56873c21cc6187548a60311d`。
- 旧window metrics：SHA256=`869d634e1e56b99cac6f28cf4e0108942c104648b4cedd91fc8ee9961fee0da3`。
- 旧position changes：SHA256=`8117146732a165e9e61627e71a8b19044d3acddab9c7af1160ec20ac83fb7210`。
- 全市场主力映射：`tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv`，SHA256=`89c8ae7e66e67def7f2b9626a166d0d6582c30fe2e08ee6cf39808951146d851`。
- 主力映射导出器：`export_tqsdk_all_futures_main_contract_mapping.py`，SHA256=`1dd8642c91898889acdedaae2933e163b778b9ffe0c45945fd4be37feb4a5d5b`。
- 主力映射消费模块：`main_contract_mapping.py`，SHA256=`86f4baa027e1a236616d749895e349840a3db305b7ca87a7401ff4afc47bc503`。
- workspace日线库：SHA256=`7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a`。
- Stage001首条普通合约日线日期：SHA256=`d2fa054e4184371a987976c20544c036b9361f8ccd8410dcdc081463c4c3e038`。

## 外部调研与判断

- scikit-learn官方`TimeSeriesSplit`提供`gap`来排除训练末端与测试开端之间的样本；本项目标签期限按真实交易日变化，因此采用逐行`label_end_date < test_start`，而不是固定自然日近似。
- XGBoost官方说明树模型可原生处理缺失值；这只允许保留真正未知的特征为缺失，不允许把尚未上市品种补成全0训练样本。
- QuantConnect官方期货universe文档把“当日可见合约链”和连续合约映射分开；支持先确认当时可交易资格，再计算横截面标签和排序。
- 官方上市日期至少覆盖本面板中2020年后新增品种：`lh=2021-01-08`、`si=2022-12-22`、`lc=2023-07-21`、`SH=2023-09-15`。资格日取`max(官方上市日, 首条有限且OHLC均为正的普通合约日线日)`。

## 唯一审计任务

1. 从旧daily交易日历逐样本恢复真实`future_label_start_date`、`future_label_end_date`和观测数，并逐值复算旧`future_net_pnl_60d`。
2. 对旧9个walk-forward fold逐项计算训练标签与测试期重叠；严格条件为每条训练样本`label_end_date < test_start`。
3. 标记当月未满足上市资格的样本；禁止在资格过滤前做横截面future-rank或target。
4. 盘点旧samples、position changes、当前配置、全市场mapping和数据库的品种覆盖，判断能否恢复“历史批准宇宙”；不得用当前18品种集合冒充历史版本名单。
5. 审计主力映射来源是否具有本地可验证的同日或滞后因果合同；vendor历史日历若无法从本地输入独立证明，只能记录为残余风险。

## 预声明输出

- `fold_label_overlap_audit.csv`
- `sample_label_boundary_audit.csv`
- `listing_eligibility_audit.csv`
- `universe_provenance_audit.json`
- `stage001_summary.json`
- `artifact_manifest.json`

## 决策门

- 任一旧fold存在重叠时，旧模型证据降级，禁止直接把其分数当作干净PIT基线。
- 任一旧样本使用不足60个未来交易日，必须从重建训练集删除，不得混合不同标签长度。
- 任一未上市样本存在时，必须在重建时先过滤资格，再按当月真实候选做横截面标签。
- 若无法恢复历史批准宇宙，Stage002最多建立“固定当前设计宇宙条件下”的PIT基线；不得发布“无幸存者偏差”结论。
- 本阶段通过只表示问题已完整量化并能冻结下一阶段合同，不表示模型有效，更不表示收益或回撤改善。

## 运行前反思

- 是否过拟合：**否**。本阶段没有参数、模型或收益门选择，只验证时间与成员身份。
- 是否值得继续：**是**。若这一步失败仍继续XGBoost，任何高收益都无法区分真实alpha与前视泄漏。
