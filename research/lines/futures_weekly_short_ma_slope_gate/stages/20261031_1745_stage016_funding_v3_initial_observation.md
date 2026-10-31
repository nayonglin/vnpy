# Stage016 首个真实资金观察checkpoint

- line_id：futures_weekly_short_ma_slope_gate；2026-10-31 17:45 CST。
- 资金schema仍weekly19.external-funding.v2；只新增入口，不覆盖V1/V2与1723 IO证明，不改alpha/比例/原风险。production_qualified=false。

## 问题与判断

- 原始state的cashflow_checkpoint=None会直到首个原生周五admission才建现金基线；若coldstart在其它weekday，此前现金未知，不能让root手写CP字段或把初始15万误算为场外备用到账。
- 复核现有funding checkpoint/Deposit守恒与backend初始真实15万flat门，选择在首个已资格账户查询上进行一次CAS观察，不加新schema，不推断此前资金来源，不把E差额当入金。
- 外部资料核验与原生callback来源判断沿用同分钟cash_provider_v4记录；初始query envelope仍需qualified provider/caller真实门，纯资金函数不自授生产来源资格。

## API及状态

- begin_cash_observation(state,broker,now)->new_state，不原地改参。仅v2、无requests/receipts/admitted_entries/day_rolls/retirements/request_attempts、confirmed=0且R完整时可进入。
- fresh/aware原始SHA/账户/release/完整CNY query、last=true、error_rows严格int0、严格Decimal字符串Available非负、实际Balance恰好150000，以及coldstart本地日期/observed/day已到才可首次观察。
- 用真实日Deposit/Withdraw及rawSHA建cashflow_checkpoint，revision+1；初始Deposit可以含初始15万，仅作baseline，R/confirmed/建议/请求/原signal去重一概不变。
- 相同原始snapshot幂等不增revision；已有CP不同首始/非初始权益/已有资金活动拒绝，不能用此API重置或绕过日切。
- 调用后FundingStore.commit(oldrevision,newstate)成功再启动信号/开仓。后续任何Deposit/Withdraw变化需要真实到账守恒，日切仍需要最终cashflow continuity；无证据明确block。

## TDD/证据

- 新6组测试首先因API缺失RED，随后资金全61（原55+6）GREEN，含任意weekday/initial Deposit15w不扣R、same raw幂等、later reset、E149999.99/150000.01、Available异常/float/缺字段、query错误、错账户/release/rawSHA/未来陈旧、coldstart/已有活动、首周五前现金delta及日切阻断、store CAS restart。
- 与provider47/warm11/旧22/旧25共166项GREEN，完整日志见同分钟cash_provider_v4_unittest.txt；本记录manifest单列资金源与61tests，其余新证据不冒称旧证明涵盖。
- 未执行金融回测、CTP、银行、SMTP、生产、index或commit；未创建真实registry/key或执行真实qualification。此处只条件会计正确性，尚非实际到账E2E。
- 真实final cashflow statement/parser与source qualification缺项继续准确block；不能以clock或fixture替代。root负责完整release source pins与最终独审/激活。

## 反思

- 运行前/后是否过拟合：否，无历史业绩拟合、没有收益参数变更。
- 运行前/后是否有继续价值：是，首周五之前就建立真实资金观察边界；下一步价值在真实证据接入。金融结果、胜率/PF等均不适用。
