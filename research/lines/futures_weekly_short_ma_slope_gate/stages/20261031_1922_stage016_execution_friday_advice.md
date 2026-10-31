# Stage016 周五同批资金建议纯helper

- line_id：futures_weekly_short_ma_slope_gate；时间：2026-10-31 19:22（北京时间）。
- 仅新增 qmt_roll_weekly19_friday_advice.py 与 tests/test_weekly19_friday_advice.py；不修改资金schema、root pipeline/backend/config/state或已锁执行器。
- 固定Stage014工程迁移，非重要突破版本；production_qualified=false，无SMTP/CTP/Git或金融回测。

## 调研与判断

依据既有资金V2、PipelineStateStore只读校验和已核对的VeighNa完成周线/实际回报语义。建议不是债务，外部备用金不增加权益。公共fund V2只有superseded_current_gap允许同ID再offer，expired_superseded/equity_recovered消费旧admission；helper保留该边界，不改schema或制造第二个原生信号。

## 接口

refresh_friday_advice(bundle, broker_account, now) 返回 weekly19.friday-advice.v1：status、funding、recommendation、source_bindings、advice_id、original_offer_remaining_fen、before/after_funding_sha256、broker_account_raw_sha256、blockers，始终production_qualified=false/order_api_called_count=0。

仅上海时区周五、同ISO周已完成原decision、有完整原admission records及receipt/origin绑定时评估。复用现有store validator，只读验证原decision_state与当前资金前向账本；不读写store、不运行on_bars、不重建原决策或AM。节假日周四信号在周五以calendar Friday作为fund target_week_end，原Thursday source与原全部IDs单独保留在source_bindings。

已知现金连续性必须由public recommend/retire验证；缺initial cash observation、fresh account、day-close或有unknown Deposit/Withdraw时，返回原资金深拷贝与0 actionable金额，不吞错或虚拟到账。

- 未确认offer当前gap变化：先public retire(superseded_current_gap)，再public recommend。
- E回到15万：public retire(equity_recovered)，旧建议不当欠款。
- 到期：public retire(expired_superseded)，同批不续期或重新造建议；真正新周/新decision才可新T。
- 同canonical Friday + sourceReceipt的所有native IDs属于一个portfolio admission batch。任何历史request已有confirmed_fen>0，该批剩余ID即使未记录在第一个request也不能再次创建或放大offer。
- active partial且gap仍等于原remaining可沿用原offer；gap变化返回confirmed_batch_no_additional_offer、amount0、nonactionable，另保留历史remaining上限；不绕过公共changed-gap门。
- 创建与即时重读统一显示funding_pending；advice_id绑定输出资金、不可变source与recommendation。重复调用/已提交后重读不新增request、不续期、不增加现金。

root须先将返回资金同步到同一runtime actor，再CAS持久化，后渲染邮件；helper的allowed/ready均非来源资格。

## 验证

10个新helper条件fixture与未改的61个资金、12个store测试：83 tests / 2.505秒，OK。日志20261031_stage016_friday_advice_final.log。包括真实原runtime双symbol同批（初始request仅第1ID）、完整/部分到账、holiday Thursday、cash/day-close缺项、错误receipt/admission、stale/跨周、过期retirement及原bundle/decision/AM不变。fixture先构建原runtime，helper阶段不调用on_bars；不是金融回测或真实生产资格。

新增/修改/删除金融回测结果均无；期末权益、收益、回撤、Sharpe、滑点、交易数、胜率均N/A。运行前后过拟合判断：否，只修工程时序/现金保守边界。继续价值：是，满足周五邮件偏好并避免整批重复补钱。交root接store/renderer，未发布邮件或委托。
