# Stage015 并发共享 builder 竞态 fail-stop

## 时间与性质

- 时间：2026-09-01 23:22（Asia/Shanghai）。
- 研究线：`futures_trend_ai_xgboost_ensemble`。
- 重要突破版本：否。本阶段是开发标签基础设施的确定性故障定位与停机，不是 alpha 突破。
- 线上/正式版本：未修改；仍是 `m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`。

## 运行结果

- campaign：`campaign_20260901T205915+0800_36804`。
- 冻结合同：`b2b529c15293c320d5f2ac1c6b410e4ed1c3243bec43dcfaaa5a6557168b9f14`。
- 完成任务：226 / 355；失败任务：`20240430_R17`。
- 异常：`pandas.errors.EmptyDataError: No columns to parse from file`。
- `development_labels.csv`：未生成，部分标签禁止汇总或训练。
- sealed holdout 标签读取数：0。
- 订单 API / CTP：未调用、未连接。

## 根因证据

- worker 在进入真实引擎前调用正式 `build_official_live_strategy_overrides()`。
- 该 builder 最终调用 `build_static18_plus_fu_universe()`，并以普通 `DataFrame.to_csv()` 重写同一个共享产品池文件。
- 两个并发 worker 可形成“一个截断写、另一个 `pd.read_csv`”的竞态；失败栈正好停在 `load_product_universe_symbols()` 的 `pd.read_csv(path)`。
- 失败后同一路径恢复为完整 CSV，排除固定输入本身为空；这是时间窗口竞态，不是品种池内容错误。
- 因成功任务同样经历了未冻结的共享写路径，已完成的 226 个任务也不复用，整个 campaign 判废。

## 版本改动

- 新增参数：无。
- 修改参数：无；`MAX_WORKERS=2`、`MAX_JOB_SECONDS=600`、货币量化 `0.000001` 元均未改变。
- 删除参数：无。
- 逻辑修复：正式 overrides 只允许在新 campaign 准备阶段构建一次并写入 `official_overrides.json`；worker 仅从 campaign 快照生成候选 override，不再调用有写副作用的正式 builder。
- 身份增强：`official_overrides.json` 与 campaign 私有 `official_product_universe.csv` 纳入 campaign 和 worker 执行文件合同；worker 收据必须声明 `campaign_snapshot`，绑定 campaign ID/绝对路径、原始 TMP/MPL 环境并记录快照 SHA256。
- 发布前门禁：删除跨 job 身份缓存；全部对账和 gate 完成后再做一次无缓存完整 campaign identity 重建，漂移时直接 fail-stop，不生成开发标签或 PASS decision。
- TDD：新增竞态、跨 campaign receipt、废弃恢复、同长/异长输入漂移、发布前最终身份、空产品符号等回归合同，均先红后绿；Stage015 23/23、研究线 91/91 测试通过。

## 回测指标

- 新增回测结果：无可发布结果；本次是不完整标签批次。
- 修改回测结果：无。
- 删除回测结果：无；仅将 226 个部分任务整体判为不可复用。
- 期末权益：不发布（不存在完整一致的组合回测）。
- 总收益：不发布。
- 最大回撤：不发布。
- Sharpe：不发布。
- 总滑点：不发布。
- 总交易次数：不发布。
- 胜率：不发布。

## 反思与后续

- 是否过拟合：否。故障处理未查看标签分布、未调整特征/目标/模型参数，也未读取 holdout；只修复并发确定性。
- 是否值得继续：是。真实账户级完整标签仍是比较逻辑回归与 XGBoost 的必要前置，但必须从零创建新 campaign。
- TODO：独立 reviewer 审查根因、TDD 和冻结快照合同；通过后新建 campaign，重新跑 smoke，再决定是否允许完整开发批次。
