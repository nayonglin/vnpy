# Stage002A精确输入合同冻结

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 记录时间：2026-09-05 17:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage002唯一执行前的字节级输入冻结
- 是否重要突破：否；没有事件、标签、模型或回测结果
- 是否触发reviewer：否；不属于有价值回测候选

## 冻结合同

- 输入文件数：`1416`
- 逻辑key SHA256：`8987c5c62fd8758fa6076c94bbdea3ce5b5f6d40405529c48a7ad5f875f94312`
- file contract SHA256：`5e0786df548061361f0ad8266b6cdc7a443eeddf88f64b3d522c5f192af9a453`
- runtime contract SHA256：`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`
- 正式release：`m0005_20260901T165450+0800_1961d98ccb2b`
- 正式策略：`ai_top10_plus_fu_official_live_v1`
- 正式执行：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 资本口径：`150000`
- 正式manifest identity：`4d92133bd67821a421bf6017c477015e79a3a8e36889ae4eb527bb11a31956a5`
- 正式eligibility SHA256：`fafe6fbaf9836706e2d70d40c799dd4ea4db279fb283fda76d18a797f126d018`

## 执行边界

- 冻结凭证JSON不属于1416项输入，避免凭证哈希自引用；runner只读取并核对其四项精确合同值。
- claim创建前必须重新生成manifest并与本凭证完全一致；不一致则不消费执行机会。
- claim创建后任何成功、失败或中断都视为唯一执行已消费，不允许修改输入、阈值或代码后重跑。
- A1/A2各只允许一次正式A路径回放；不运行XGBoost、不读取标签、不计算候选绩效。

## 回测结果字段

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；未回测
- 胜率：不适用；未回测

## 过拟合与继续价值

- 当前是否过拟合：否。合同在事件结果不可见时冻结，所有资格阈值保持预注册值。
- 当前是否值得继续：是。唯一运行将回答正式根事件样本与12项特征是否具备最低建模资格；失败即闭线。
