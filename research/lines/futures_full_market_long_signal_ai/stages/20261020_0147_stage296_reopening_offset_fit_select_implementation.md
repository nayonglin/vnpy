# Stage296：全98真实月reopening单scalar冻结52修正实现

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:47 CST；仅实现与新合成验证，非重要突破、未实际拟合或重选。新增actual fit/cash/SQL/网络/旧大CSV、NPZ、标签、native读取均0；累计441fit/238cash不变。不改LINE/registry/旧source/正式版本。
- 全文读取294协议，SHA `82a4e3f88c4c17c6319e298a2ad6c37ac1070f62fff6cd9eb5d25be857251016`。外部原论文和GitHub调研直接复用294已冻来源及293独立信息自由度证明，未重复联网。判断：历史Open在旧COMMON/20×4外有自由度只支持一次新量证伪，不代表alpha、可迁移股票结论或窄损加注资格。

## 实现及依赖

新增`tools/stage296_reopening_offset_fit_select.py`和对应test；仅复用285纯权重恢复/原52设计评分/无截距scalar解等辅助，不调用其WASDE时钟、原actual入口或Corn映射。输入295的量为全部原1552456真实月action对齐vector；与295作者直接对齐：`outputs/stage295_reopening_contribution_source/actual_run1/source_vector.npz`，keys为sequence_index(int64)、q(float64，缺NaN)、available(uint8 0/1；显式转bool核对finiteq)，可忽略state_code。legal q0参与正常标准化，不能按false/missing处理。

原130六个scope/cutoff各用**自己的冻结52coef/intercept/scaler**及原成熟身份、原target和原sample_weight；无D<K训练过滤，无K重标，无新missing/ID/intercept。实际只一次旧COMMON读取、6份train CSV各一次直接字符串→float恢复、源vector一次读取，最多6次无截距scalar解，不重训旧52。训练缩放使用该折有限q行原权重，两独立u日期与正方差才支持；原总目标权重不对有源子集重归一。每折保留model/scaler/gamma/充分统计及compact支持NPZ（sequence_index/w/y/s52/residual/z/delta），不复制宽训练CSV。

完整1933480旧scores一次流读，沿130原连续scope顺序分别私有main别名接156，实际scope/candidate保留；完整966740 main动作与同数held并集、161014 main母行与同数held并集均核对。全部旧非正分也处理；q因真实月不同，允许参与翻转及月份重排。NaN或delta0用条件赋值保留旧score浮点位；全域先D<K再positive argmax及原ordinary/F/family次序。只保存完整新choices、原K boundaries、有限anchors和全折汇总，不复制193万宽scores。

main旧选择只读156。held旧选择使用**现成已接受纯COMMON52同K缓存**：205 actual_run1/control_held_K.csv.gz（SHA `b9091d70…40e30e0c`），205小manifest明确绑定130原score与模型，207小review core0接受；不用205 CURVE53模型或失败候选。由授权绑定这三项，不重新推旧held控制或重算旧金融。

新旧held选择不同才允许单次读取129 actions的action_id/label_state/participation_state/net_R_stress/label_known_date五列，筛全部新旧held所选ID。然后复用130原held诊断：先family-u再等u，closed且known≤2026-10-16用原stress R、无选/已知不参与为0、相同未知动作增量0、不同未知不填0；不是K现金标签。若held选择完全相同，跳过该标签流，明确common outcomes未检查而非冒称全部已知。输出两组mean/unknown及held_nominal_nonharm bool/unsupported。

manifest为`stage296_reopening_offset_fit_select_manifest_v1`，candidate=`REOPENING_GAP20_OFFSET`，artifacts字典包含choices_main/choices_holdout/held_diagnostic/held_daily/boundaries；inputs.mothers/actions原129。boundaries精确沿`stage156_voluntary_K_only_v1`、account_deadline_certified=false及epochs；choices内部arm仍VOLUNTARY_RESELECT，只供297/157兼容，外部新candidate单列。

## 验证与交接

新fixture先RED（新296模块尚不存在）；初次实现GREEN。295最终将available指定uint8后，新增该真实边界先RED，定点改成0/1校验加显式bool，再GREEN。最终**6个新tiny tests全部通过，0.878秒**，覆盖：legalq0与缺失位保持、ownfold不同γ/原固定base辅助、原权重精确恢复、held family排除、源sequence对齐及uint8非binary拒绝、完整held别名/K选择/nochild、相同unknown零增量/不同unknown保留与known截止日。语法compile及`--help`通过；不跑旧suite，不实际读金融数据。

298已一次静态读取最终296及test，报告未见核心模型/选择/held接口阻断；其receipt等待295最终源一并绑定，未重复静审。root执行澄清保持分离：**main有实际动作变化则仍完成原297最多4cash；held原R负仅使研究/泛化门失败，不能代替共同K现金收益/DD判断。只有main执行身份相同才以独立经济等价跳过现金。** 本代码cash_eligible仅标main选择变化，不将held负提前混入现金门。

[实现收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage296_reopening_offset_fit_select/implementation/implementation_receipt.json)及[授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage296_reopening_offset_fit_select/implementation/authorization_template.json)已保存。模板source_manifest、static_review_receipt为待root取得完成产物后替换的显式占位，**不能直接执行**；其余原输入、源bundle和293 stage已精确绑定。CLI为`--authorization --authorization-sha256 --source-manifest --output`，fresh输出`outputs/stage296_reopening_offset_fit_select/actual_run1`。只有root最终精确绑定并启动actual；失败保留terminal与已消耗计数，不自动重试。

- source 25154B，SHA `40f3e55262465229b429a6b0bff2ceae7e7cf32aaaed5e5261e7ca0baa663987`。
- test 6244B，SHA `1ad3661a4a54f582712c05218f51bc8d779cbbd98eb21ed09ea93c73972c969f`。

本阶段没有新增/修改/删除科学参数及实际回测结果；权益、收益、DD、Sharpe、滑点、交易数、胜率和CI均N/A。开始/结束新增收益调参过拟合：**否**，未产生新金融结果、未改294；长期441/238同史选题适应性风险：**是**。继续这项一次有界证伪：**有价值**；结果后改窗口、方向、normalizer、产品、模型、stop/risk：**无价值**。完整全市场目标仍未完成，不授PIT/alpha/窄损/加注/晋级资格。actual后须由298全面独审新源、训练、全域选择、现金及置信度。
