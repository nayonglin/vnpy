# Stage017 运行前复核

- 复核日期：2026-09-02 CST
- 复核方式：独立只读审查
- 未执行Stage017正式训练，未读取sealed holdout标签，未修改任何文件，未连接CTP或订单API
- **独立决策：`ALLOW_FROZEN_STAGE017_RUN`**
- 该结论仅授权当前冻结字节进行一次development OOS运行，不授权holdout、生产接入或实盘交易。

## P0

- 0项。未发现会导致正式运行结果无效、标签泄漏或错误发布的阻断问题。

## P1

- 0项。合同、预注册、身份检查、技术短路与原子发布闭环完整。

## P2

- 0项。旧review提出的两项P2均已闭环。
- 两次scaler现为独立对象、独立payload、独立序列化bytes和SHA，并返回`repeat_scaler_raw/hash`。
- 新测试覆盖`y/100y`模型SHA、标准化预测和逆变换等价，以及`main`三轮身份复核和技术失败发布短路。

## 核心证据

- 唯一变化确为每折、每目标只使用训练标签拟合`StandardScaler`。release、9特征、两个目标、XGB参数、39个月/15折/PIT规则、selector和九项效果门与Stage016逐项相等。
- scaler拟合只接收`train[target]`；测试月只提供特征用于预测。逆变换结果才进入Stage016冻结的双头等权percentile、tie-break和C双正门。
- 独立合成复算得到：`y/100y`模型SHA均为`315d89eb0af4791676e3d6eee9e8902529d22f5de4ce959dd1ff3d83d5022e76`，标准化预测差`0`，逆变换除100后最大差`2.168404344971009e-19`，且模型包含184个split nodes。
- 授权绑定runner、tests、contract、预注册、本review、Stage016运行后review共六项；`main`在训练前、训练后和效果评价后分别复核合同、授权与九项输入身份。
- 技术门失败时不调用效果评价，只发布技术审计、decision、receipt和fold audit；不发布预测、月度选择、效果值、模型或scaler。
- 发布使用同父目录partial、文件及目录`fsync`、manifest、原子rename、父目录`fsync`；拒绝覆盖，rename后失败会隔离到quarantine。
- Stage016 manifest的41个文件已逐项重算，文件集合、大小和SHA全部匹配；30个模型、15折、训练月`24..38`、135条预测、PIT违规0，决策仍为`stage016_development_oos_proxy_fail_stop_no_holdout`。
- development标签共351条，日期为`2022-04-29`至`2025-06-30`；`2025-07-31`起记录为0。生产checkout保持clean，HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- 专项测试：`9 passed in 1.99s`；整线测试：`132 passed in 14.95s`。

## 冻结SHA

- runner：`f40770af5e638a096e5fb52242f390c7496f2e758b94abbe584aefa104e824de`
- tests：`2a3905f5f2e2e1dd869800c3aec3b7701bf4db172b9af9f1a255865d0b3ecdea`
- contract：`d7af14a69f636b56bb1f63ccd9d511a2925a1e20c6b5a98acf09edaf1572a013`
- preregistration：`bface574b2b6c3ef84067dcf08ee834dd74efa02376d5b9a44e231d218569fc5`
- Stage016 postrun review：`89f18a67181e98536abe5dddb19454b62826f2ee84e2ca66feb34b2bef52f662`
- Stage016 runner：`b78bd1cb5e7b49ce49bff683a38f4d34656a6d88ac147fdd25bf285b38543847`
- Stage016 decision：`6f21fbf74ef9abdb2b142d786cfd950411ec9e37726c9aff519e4a8b3cdb6ca8`
- Stage016 manifest：`bfdae5a931d980548dcbe9f58563d831c5c98218f22953ad61d6ed1956ffbdcb`

## 运行前置

- review落盘后需重算SHA，再生成绑定六项文件的授权及其自身SHA。任何绑定字节再次变化，本ALLOW自动失效。

## 反思

- 过拟合判断：**是，风险较高**。Stage016 development结果已知，但本次只验证预注册的单位尺度机制，没有扫描参数、特征、transformer或门槛，因此风险受到约束但没有消失。
- 继续价值：**是，但只值这一次**。任一九项效果门失败，必须停止当前九特征/账户边际标签XGBoost族，不再用scaler、损失、树参数、阈值、rank、年份或品种继续补救，也不得读取holdout。
