# Stage005B v2标签批次编排迁移预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 记录时间：2026-09-02 20:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage005批次编排器静态迁移、测试和批量前独立复审
- 是否重要突破：否
- 是否运行回测：否
- 是否授权270任务：否

## 开始判断

- 是否过拟合：否。本阶段只迁移已预注册的266 main + 4 A2标签生产器到已经通过固定smoke的v2运行身份，不读取新标签、不改样本或策略参数。
- 是否值得继续：是。Stage005仍指向已失效的Stage004旧运行时；不完成完整身份迁移，后续批量标签即使跑完也不可解释。

## 外部调研与判断

- XGBoost官方Learning to Rank要求训练样本按`qid`分组并保证组内标签可比较：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 官方仓库文档同样把标签、组身份和排序目标作为训练前合同：<https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst>。
- 我的判断：本阶段没有必要调整XGBoost参数；正确动作是先让35个development月份的账户标签共享同一冻结运行身份和精确执行合同。

## 冻结迁移范围

1. Stage005必须指向`/private/tmp/vnpy-stage005-curve-account-runtime-v2`，并使用以下冻结输入：
   - 数据库SHA256=`db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b`；
   - 主力映射SHA256=`093d3bc767c09d9e0e4f4fbeb9846a091bf25c163cc31eddfd382cc1ff5490b7`；
   - 分钟数据SHA256=`8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`；
   - 合约元数据SHA256=`24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`。
2. Stage005静态和run authorization必须绑定Stage005A runtime receipt、成功smoke receipt、scope audit、post-run review与decision；旧Stage004材料仅保留历史来源，不得决定当前运行身份。
3. worker入口不得安装或覆盖父环境；必须在加锁和策略运行前机械验证QMT guard及`TMP_ROOT/<campaign>/<job>/<run>/tmp|mplconfig`。
4. campaign manifest必须包含v2数据库、映射、分钟数据和元数据；resume前后逐字节身份一致。
5. 原Stage005治理合同保持不变：append-only attempt、rank10原始predecision证据、逐操作数`1e-6`金额量化、精确允许文件树、显式holdout/model/CTP/order零计数。

## 不变量

- 任务固定266个main + 4个A2，35个development月份，不增删月份、品种或rank。
- sealed account-label holdout仍为12个月，读取/任务/标签/输出计数必须为0。
- 账户15万元、正式策略、滑点、手续费、保证金、整数手、相关性和最多4持仓均不修改。
- 不训练模型，不选择XGBoost目标或参数，不生成模型产物。
- 不连接CTP，不调用订单API，不修改生产checkout、release或数据库。

## 测试先行合同

- 先新增失败测试，证明Stage005当前仍指向旧runtime且缺少worker环境门。
- 最小实现后，专项测试必须覆盖：v2常量与四项冻结输入、成功smoke/post-run证据绑定、worker保留job环境、orchestrator环境拒绝、结构化BLOCK拒绝。
- fresh运行三个相关测试文件及`py_compile`；只有全部通过才请求独立批量前review。

## 放行门

- 本阶段唯一可能决策：
  - `stage005b_v2_integration_pass_ready_for_batch_prerun_review`；或
  - `stage005b_v2_integration_fail_stop_no_campaign`。
- 即使静态门和测试通过，也不授权`--prepare-campaign`或`--run-batch`。
- 只有独立review给出结构化`ALLOW_STAGE005_BATCH`、`P0=0/P1=0`，且另有绑定当前代码和全部证据SHA的run authorization，才允许创建一个Stage005 campaign。

## 预注册TODO

1. 先写测试并观察预期失败。
2. 迁移Stage005 runner到v2冻结输入和worker环境门。
3. fresh验证并冻结代码/测试SHA。
4. 拉独立批量前review；不在本阶段运行任何标签任务。
