# Stage095 ORDER/BAG现金适配实现与小边界测试

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 18:25 CST。本阶段重要突破否；源码实现完成，actual未授权、未运行。
- 读取本线registry、Stage092协议及中文设计，沿用090/092的Deep Sets与有序/集合表示调研判断：只检验当前独立固定跨日目标中有限模型对位置的利用，文献不保证交易收益。

## 变更与冻结

只新增`stage095_order_bag_cash.py`与对应新tests。以已接受087流程最小适配，只导入070/042/054已接受pure函数；不导入094模型训练模块，不导入OI投影或080分配。导入及tests均native计数0，没有label、fit或现金。

- 新参数：无交易参数新增，臂名ORDER/BAG、上游094 schema接线、ORDER自身四组合净收益必须全部>0为092新增判断门。
- 修改参数：0；删除参数：0。100w/单.25%/总2%/margin25%/buffer1.1/.25N/Wilder20/20low/u预留D只减、原gap/换约/期限/缺价/破产不变。
- 当前实现SHA：`5fa699097d234171269b37d8e6f1f81b6a338cfc5d59572d18f43a5330ec876a`（25689 bytes）。
- 新test SHA：`b189dd253d806d1a5a730999684ff19670950ac3f2f07e8b122988d38e7e783c`（9078 bytes）。
- 机器可读freeze：`outputs/stage095_order_bag_cash/implementation_freeze.json`，SHA `6e96a1e6a23576db0cece0eff8a2d731596f7fec9a83c2499ca49b336ec960ca`。

## 新边界验证

先运行tests得到10个明确RED（095实现缺失），实现后10项GREEN、0.044秒，仅新接线与门：完整母体未知标签/sequence missing不拦交易、main与held隔离、共享missing一致、空BAG DD保留NA、ORDER相对较好但自身亏损/零收益不通过、四窗口齐全、held未知与真实stale分离、绑定错误不建输出、094第13attempt即便12complete也拒绝。未运行旧suite、未重建旧资格、未做真实金融重放。

## 实际入口与数据合同

现金授权只绑定六项market_protocol/narrow_labels/narrow_manifest/fit_manifest/predictions_main/held_diagnostic。094必须 completed actual12fit、644056预测、0native/0cash，terminal attempt与complete均12。只main每臂161014进现金，held两组仅诊断。使用同070既有bootstrap indices，不重造。

后续root按精确最终源码和输入manifest签发cash授权后，fresh `outputs/stage095_order_bag_cash/cash`唯一运行8账户/一次共享native SQL，失败保留无自动重试。输出8完整账本、费用滑点、年度、95family含零、风险/未知/实际有限案例、配对CI与092门、显式本地asset roles，等待096独立全量复核。

## 本次回测字段

新增/修改/删除回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A（尚无actual），不把10项synthetic tests称作交易结果。累计研究仍345fit/78cash，goal active。

## 反思与TODO

开始和结束是否按收益调参过拟合：否，本阶段无本实验收益输入，严格实现092单点冻结；历史多轮曝光与有限RFF几何偏好仍存在，不称新盲OOS。继续是否有价值：是，限一次固定跨日目标ORDER/BAG对照；若门不支持停止该固定包，不救窗口/模型/种子/止损/下注。

TODO：有限096源码preflight；等待093/094完成及root精确cash授权；唯一8现金；096一次独立全量review；交root判断，不改正式版。
