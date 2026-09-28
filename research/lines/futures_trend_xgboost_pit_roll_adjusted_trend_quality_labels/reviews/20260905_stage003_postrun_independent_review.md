# Stage003 运行后独立复核

- 复核时间：2026-09-05 05:06 CST
- reviewer：独立 agent `01a06e09-bf46-7b01-962f-4e183604ef16`
- 结论：**PASS（结果证据有效；模型决策保持 FAIL-STOP）**
- findings：P0=`0`，P1=`0`，P2=`1`

## 证据链

- Stage003 manifest SHA256：`c423ded94b0c7bedc3eaa339a027d23695dbec5460447c6a30ebe5604baa7ebe`。
- 10/10 个产物和16/16个输入身份通过；before/mid/after 身份完全一致。
- authorization SHA、receipt、event 和 summary 的 nonce `2c2de944-bb5a-4adb-a5e2-3507a9a8c9be` 一致。
- Stage002 上游仍为固定 manifest `a20fa63a1c95a9d37fdc0485ddebd9e5ff403e36d4349d79b04e81e87143e904`；复核未把 Stage002 lossy predictive/effect CSV 作为输入。

## 技术复核

- `fit/load/predict=0/74/74`，74个模型文件身份全部匹配。
- 37/37 折 primary/repeat 预测 bit-exact；prediction seal 与 selection seal 均为37/37。
- 2,000条 `float.hex` 回读 bit mismatch=`0`，seal replay=`37/37`。
- 36/36 access event 合法；原始标签重放1,940行，opened-label SHA为36/36匹配。
- 标签为55,226行/1,046 qid；最终训练元数据为55,168行/1,045 qid。

## 指标复算

- Predictive：mean/median Rank IC=`-0.0232133/-0.0229765`，正月`16/36`，leave-best sum=`-1.3866123`，正年份`2`，NDCG delta=`-0.0530824`，胜出月`13/36`；除月份数外其余7门失败。
- Effect：替换`28`次；质量改善率`0.5000`，中位质量差`-0.0030311`，quality sum/leave-best=`-0.5742274/-0.6548494`，正年份`0`；幅度 sum/leave-best=`-0.1511225/-0.2654736`；路径回撤代理 sum/leave-best=`-0.4231049/-0.4728027`。仅月份数与替换次数范围通过，其余9门失败。
- 独立重算表与落盘表最大浮点差约`1e-16`；汇总及 gate 与 summary 完全一致。

## Finding

- P2：冻结 `report.md` 将已经计算并失败的门写成“失败或未开放”，措辞不够精确。summary、门值和 decision 均准确，因此不影响证据；不得为修饰措辞改写已经封存的 bundle。

## 最终判断

- 必须保持 `stage003_lossless_evidence_recovery_effect_fail_stop_no_true_engine`。
- 当前候选不得进入 true-engine A/C、holdout、shadow 或正式接入。
- Stage003 本身没有新增过拟合；依据已见失败结果调参、改门、删月或反转方向将构成明显过拟合。
- 当前模型形态没有继续价值；仅保留负结果，或凭独立经济机制另立预注册研究线仍有价值。
