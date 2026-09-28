# Stage015 嵌套 profile builder smoke fail-stop

## 时间与性质

- 时间：2026-09-02 01:07（Asia/Shanghai）。
- 研究线：`futures_trend_ai_xgboost_ensemble`。
- 重要突破版本：否。当前是执行隔离缺口的 smoke fail-stop，不是 alpha 结果。
- 线上/正式版本：未修改；仍为 `m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`。

## campaign 与 smoke

- campaign：`campaign_20260902T003958+0800_80965`。
- 冻结合同：`d8649b5d5c1d7215100834f372733d170c703ce168097ed11252545806eda2e2`。
- runner SHA256：`29797754f5a22597f28a29de78ac0d972f46b02b8718116f236b29bcf8662503`。
- 从零准备：355 jobs、351 eligibility、smoke 前 0 job outputs。
- smoke：4 / 4 冷进程完成；A/A、predecision、entry boundary、runtime、600 秒、8 项三源对账均通过。
- 独立审查：`P0=0 / P1=1 / P2=0`，决定 `STOP`。
- `development_labels.csv`：未生成；sealed holdout 标签读取数 0。
- 模型训练 / CTP / 订单 API：均未发生。

## 根因

- worker 只替换了 `s901.build_official_live_strategy_overrides`，最终策略确实读取 campaign 私有产品池。
- 但 `s901._run_live_c9()` 在合并该 override 之前先调用 `s847._c9_profile()`。
- `_c9_profile -> Stage830 -> Stage827 -> Stage825 -> Stage819 -> Stage813 -> Stage777` 会调用 `build_static18_plus_fu_universe()` 和 `build_ai_satellite_post_signal_eligibility()`。
- 两个 builder 都以普通 `DataFrame.to_csv()` 覆盖共享 CSV；smoke 运行窗口内共享文件 mtime 发生更新，独立计数 probe 也确认一次 profile 构造命中两个 builder。
- 私有产品池只解决最终读取隔离，没有实现 worker 零共享写；因此该 campaign 四个输出整体禁止复用。

## 版本与回测指标

- 新增参数：无。
- 修改参数：无；模型、特征、标签、并发数、超时与对账阈值全部保持冻结。
- 删除参数：无。
- 新增回测结果：无可发布结果，仅有被判废的 4-job smoke。
- 修改/删除回测结果：无；四个 smoke 输出整体标记不可复用。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不发布，因为没有完整一致的 development 批次。

## 反思与后续

- 是否过拟合：否。发现的是与标签值无关的副作用调用链；未分析部分收益分布，未改模型合同，未读 holdout。
- 当前 campaign 是否值得继续：否。继续会放大共享写，且修复后 runner SHA/contract 必然变化。
- 研究线是否值得继续：是。应冻结 Stage819 profile overrides 与其 eligibility，worker 同时替换 profile/live builder，并把两个底层共享 builder 设为 fail-closed guard；测试和独立复核通过后再从 0 新建 campaign。
