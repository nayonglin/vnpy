# Stage061：EIA 全市场事件学习实现与零 fit 预检

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-18 15:18 CST。
- 当前阶段：只实现新的 061 源码、测试和只读输入预检；没有执行研究 Ridge fit、现金账户、SQL、下载、commit/push 或生产操作。062 已由 root 另派原现金核作者实现，避免共享文件。
- 是否重要突破：否。没有新增金融结果，不能把实现通过说成信息有效。
- 依据：Stage057 最终提案、Stage059 实施计划和 SHA `ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158` 的机器合同；未修改其文件、LINE、registry、其他研究线或旧 053/054。

## 调研与判断

在已有 Stage057 的 EIA 一手资料、论文和获取代码调研基础上，本阶段另核 [scikit-learn Ridge 官方文档](https://scikit-learn.org/dev/modules/generated/sklearn.linear_model.Ridge.html)和 [维护方 Ridge 源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_ridge.py)。固定 sample_weight、带截距的加权中心化与 alpha 正则能够用正规方程单独审计。判断：保留固定 Ridge1/cholesky 和十槽设计，保存系数、截距、加权均值、XtWX+I、XtWy，方便独审；不增加一次用于试收益或挑解法的拟合。资料并未证明中国日级延迟后的库存信号有收益。

## 本次改动

- 新入口 `tools/stage061_eia_event_fit.py`：只读取 049 接受的完整经济标签和 053 prepared common NPZ 中的 `stress_u_cost_R、low20_distance_R、r1_atr`；校验 NPZ 列、399252 原顺序和 event_id 指纹。NPZ 只有 common/columns，不从中假造 row_id。
- 新测试 `tools/test_stage061_eia_event_fit.py`：13 项新行为测试，包含严格成熟、同 family 普通/F 含首尾并发、按 report cohort 同权、共享 missing、半权重 scalar scaler、COMMON 三新增槽精确 0、全 family 事件选择、非事件/未知行保留、过去52期确定 sham、event_map 防替换、未来特征污染隔离、标准化交互无二次 rescale、六格 stub 调度、零 fit 预检和 source-bound 授权。
- 两 cutoff 为 2020/2023；训练必须同时 `is_report_event && u<cutoff && label_known<cutoff && closed_complete_bar_model`。同 cutoff 三臂严格共用训练 ID、权重、scaler。所有 family 相同资格，四油品无交易过滤作用。
- `COMMON_EVENT / INVENTORY / PAST_SHAM` 每臂完整 2020+ 输出有限 score；`selected=is_report_event && history_ready20 && score>0`，不按未来 closed、stale 或持仓结果筛机会。
- CLI 分 `preflight/actual`；actual 必须另有 root-issued JSON 授权，并显式核对授权 SHA、最终源码 SHA、059 SHA 和 060 manifest SHA。授权预算固定 6；当前未发起 actual。
- 保存契约包括 6 套训练 ID/interval/uniqueness/report weight/sample weight、scaler、train/prediction X 与 y/weight 投影、joblib、便携 Ridge、正规方程、fit 日志及完整预测；顶层保存全母体输入投影、输入绑定、版本、开始、终态和 manifest。成功前再次核源码/测试字节，终态由 manifest 绑定，不把后改源码的旧结果写成成功。

## 真实 RED/GREEN 与只读预检

- 首轮 `preflight/red.log`：7 tests / 7 failures，原因是 Stage061 实现不存在。
- 源完整性增补的首次 RED 出现一个夹具 NameError，已纠正并保留原日志；纠正后的 `red_source_validation_corrected.log` 正确暴露缺失 event_map 验证和未拒绝错误 shared_missing。没有隐去中间失败。
- `red_start_receipt.log` 暴露预检最终 manifest 重复关键字的真实错误，修正后补齐 start receipt。
- 最终命令：`.py311/bin/python -m unittest research/lines/futures_full_market_long_signal_ai/tools/test_stage061_eia_event_fit.py`，13 tests，exit0，`preflight/green.log`。每次调度 6 个 stub estimator，实际研究 fit0、真实 sklearn fixture fit0、现金0、SQL0。按用户边界未跑旧 suite。
- `preflight/accepted_input_receipt.json` 只读验证：母体399252、ready20=195328、closed=180507、2020+每臂161014；3列投影形状399252×3；049/053 prepared common SHA/identity 全匹配。没有打开009或053模型/预测。
- 060 导入尚未终结；本阶段没有假造真实 report/s 或宣称全来源预检完成。完整零 fit CLI 在 060 final manifest 出现后由 root 或本 agent 执行。

源码 SHA：`7d61a8b5c309ad24881d9d36d0ffffe7f2ae39af4750b7d4130dbb316857503d`；测试 SHA：`1ae5502ffaaf3f16b3c59ed563f49327fd65daa09727fc270bb7caf431974ae6`。预检 receipt SHA：`9e604a9c77f0fb896add4c69282f4e0c4c0586971d7cb122215780b64a4ecba2`。后续若代码审查修正，以新 receipt 的最终字节为准，本段仅记当前阶段终态。

## root 接口与后续

完整预检示例（全部 SHA 显式，060 SHA 必须由真实最终 manifest 计算）：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage061_eia_event_fit.py \
  --mode preflight \
  --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage059_eia_full_market_protocol/protocol.json \
  --protocol-sha256 ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158 \
  --source-manifest research/lines/futures_full_market_long_signal_ai/outputs/stage060_eia_report_import/manifest.json \
  --source-manifest-sha256 FINAL_060_SHA \
  --output research/lines/futures_full_market_long_signal_ai/outputs/stage061_eia_event_fit/source_preflight
```

actual 另改 `--mode actual`，使用新输出 `.../experiment`，另给 `--authorization PATH --authorization-sha256 SHA`。授权 JSON 必须满足 `kind=stage061_fit_once, authorized=true, fit_calls=6, protocol_sha256, source_import_manifest_sha256, source_sha256`；未获 root 签发不得 actual。

061 manifest schema=`stage061_eia_event_fit_v1`，包含 completed 状态、actual_fit_calls_started/completed、native_source_queries=0、new_cash_accounts=0、protocol、source_import_manifest、inputs、predictions 单 binding、terminal、fits 六 records 和带 role 的 artifacts。预测文件 `predictions.csv.gz` 字段为 `event_id/product_id/family_id/u_date/u_index/is_report_event/report_id/external_missing/arm/cutoff/score/history_ready20/selected`，三臂各161014。062 作者已收到该接口。

本次新增/修改/删除交易参数：无，按059实现；没有新增/修改/删除回测结果。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均 N/A。等待完整来源零 fit 预检、独立代码审查，再由 root 分别签发一次6 fit和一次12现金；actual 后独立审计不可省略。

开始与结束过拟合判断：**否（本次没有新增收益搜索）**；历史多次择题仍有选择风险，不能据此声称未见 OOS。继续本固定实验的价值：**是**，它能用低预算检验新增实物信息及时间/资金口径；继续失败后换模型、分量、止损或加注救参的价值：**否**。完整目标、实盘、极窄止损与加注资格始终 false。
