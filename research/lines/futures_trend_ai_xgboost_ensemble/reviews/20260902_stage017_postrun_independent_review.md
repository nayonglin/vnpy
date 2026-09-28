# Stage017 运行后独立复核

- 复核日期：2026-09-02 CST
- 模式：独立只读复核
- 未重跑正式训练，未读取sealed holdout标签，未修改任何文件，未连接CTP或订单API
- **结论：确认正式失败决策，不予推翻**
- **确认决策：`stage017_target_standardized_oos_fail_stop_feature_label_family`**

## 严重度

- P0：0项。未发现产物损坏、标签泄漏、选择器错误或效果门误判。
- P1：0项。正式失败结论可以由冻结原始输入和发布产物独立复现。
- P2：0项。未发现影响后续归档或审计解释的非阻断缺陷。

## 产物与授权

- `artifact_manifest.json`声明72个非manifest文件；独立枚举为72个，加manifest共73个。
- 文件集合、大小和SHA逐项重算：缺失0、额外0、不匹配0；manifest SHA为`6613eebd7a0db12d94ae3304600c1b129ef5d0d88d0413f4f7298f9849ecfb81`。
- `run_authorization.json`自身SHA为`366a36fffe05c542136530a6dd4112387ce6a7af878e0f9ea25e461e392c132b`。
- runner、tests、contract、预注册、Stage017 prerun review、Stage016 postrun review六个绑定文件当前SHA全部与授权一致。
- `run_receipt.json`中的输入before/after/final三份身份对象逐字段相等；`run_authorization_stable=true`、`input_identity_stable=true`。

## 技术复算

- 15个测试月为`2024-04-30`至`2025-06-30`；训练月份严格为`24..38`，训练行数`216..342`，每折测试9行，PIT违规0。
- 30个模型、30个scaler的名称集合、文件SHA、manifest和fold audit完全一致。
- 不调用`fit`，仅加载发布UBJ重新推理：135条标准化预测最大误差0，逆变换预测最大误差0。
- 每个模型均为64棵树；独立解析得到split nodes总计5444、leaf nodes总计7364，与正式审计一致。
- 从Stage015训练标签直接计算scaler，mean、scale、var最大误差均为0。
- `y`与`100y`标准化数组最大差`1.7763568394002505e-15`，低于`1e-12`门槛。
- 30组repeat模型SHA全部相等，30组repeat scaler SHA全部相等；标准化及逆变换repeat预测最大差均为0。
- 因此`technical_passed=true`成立。

## 选择器复算

- `oos_predictions.csv`的135条记录与Stage015同OOS日期标签135对135逐键匹配，五项realized字段误差均为0。
- 独立重算月内average percentile、双头等权分数、预测收益/回撤/rank/品种tie-break及A/B/C双正门，与`monthly_arm_selections.csv`逐项一致。
- 4个最高分并列月份的tie-break结果全部一致。
- 实际替换3个月：`2024-04-30 AP rank16`、`2024-08-30 OI rank14`、`2025-05-30 FG rank12`。

## 效果复算

- replacement months：`3`，低于最低`4`，失败。
- replacement years：`[2024, 2025]`，通过。
- 总收益增量：`0.09110551661593003`，通过。
- 总回撤改善：`-0.008373187923382819`，失败。
- leave-best-out收益增量：`0.0`，失败。
- leave-best-out回撤改善：`-0.008373187923382819`，失败。
- 分年收益：`2024=0.09110551661593003`、`2025=0.0`，通过。
- 分年回撤：`2024=-0.008373187923382819`、`2025=0.0`，失败。
- 替换月双目标联合正收益率：`0.0`，失败。
- 九项门仅3项通过、6项失败；与`effect_qualification.json`逐值一致。

## 隔离验证

- Stage015 development标签共351条，最大`eval_date=2025-06-30`，`eval_date>=2025-07-31`为0条。
- 最后一个development标签的`next_eval_date=2025-07-31`，但其`eval_date=2025-06-30`，不属于合同定义的sealed holdout记录。
- 生产checkout保持clean，HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- runner AST无CTP、订单、网络或子进程依赖；receipt记录生产未修改、CTP未连接、订单调用0。
- Stage017专项：`9 passed`；整线：`132 passed`。

## 最终判断

- **必须按照预注册停止当前九特征/账户边际标签XGBoost族。**
- 不得继续更换scaler、目标单位、损失函数、树参数、阈值、rank、年份或品种，也不得读取sealed holdout。
- 过拟合判断：Stage017本身具有较高自适应风险，但唯一规格和冻结门槛使本次失败结论有效；看到结果后继续修补同一形状将构成明确的事后过拟合。
- 继续价值：当前形状没有继续建模价值。正收益增量完全由单月贡献，剔除最好月归零，同时回撤恶化且联合命中率为0；继续只会放大选择偏差。该结论不等于否定所有XGBoost方向，但任何新探索必须是不同特征或不同标签机制的新研究线，不能视为Stage017续调。
- reviewer agent：`01a05f50-0d25-7213-a2f2-eccac9c53a5c`。
