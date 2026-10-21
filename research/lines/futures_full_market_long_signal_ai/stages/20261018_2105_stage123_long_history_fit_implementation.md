# Stage123：固定12月信息12fit实施

- 时间：2026-10-18 21:05 CST。研究线：futures_full_market_long_signal_ai。
- 是否重要突破：否；这是冻结 Stage121 的实施，不是金融结论。
- 授权边界：仅实施和有限纯语义 fixture，actual 必须等待 root 的精确源码、输入、协议、fresh output 授权。未下载、未读原生 SQL、未训练 actual 模型、未新建标签或资金回测。
- 当前结果：新增收益/权益/最大回撤/Sharpe/滑点/交易次数/胜率均尚无 actual，不填入虚构值；旧结果不修改、不删除。

固定输入角色为 common_npz/common_identity/narrow_labels/narrow_manifest/projection_manifest/projection/projection_terminal。沿 accepted071 的 own NARROW raw net_R_stress 成熟时钟、family concurrency 后 u 日等权及 train-only 缩放。CONTROL/LONG_HISTORY 均为 COMMON26 + 26 common missing + shared external_missing + scalar 的同 54 维；CONTROL 最后一维恒零。先检查六个预定 fold 的成熟训练 scalar 正加权变异，任一无变异整包 0fit/0cash；不移动截止日或改变 family-held。正常路径固定 12fit，main 与 held 联合每臂 161014 行，总 644056 预测；held 只作机会诊断，不进资金。

保持两截止日 2020-01-01、2023-01-01 与三 scope。没有新 estimator、stop、target、risk、cost；预测期 missing/open/unknown 不以未来 closed label 过滤。schema 为 stage123_long_history_fit_v1，predictions_main/held_diagnostic/terminal 及 artifacts dict 供 Stage124 直接消费。

有限验证：先执行新增 6 个 fixture，因两份新源不存在而出现 6 个预期 assertion failure；实施后同 6 个新 fixture 全通过（最近一次 0.791 秒），两工具 --help 均 exit 0。范围覆盖 prev 代表而非当前代表、非连续 native index、闰年边界、严格窗口缺项、真实零、经济资格缺失、train-only scaler、held 标签排除、预测 missing 保留以及六 cell 变异全包停止。不运行旧研究 suite 或重复金融。

开始/结束反思：本次没有依据新收益调参数，故不是本轮 outcome tuning；同史多轮研究的选择风险仍然存在，不能声称未见 OOS。继续有价值：这是一项已预声明、在相同风险成本和原窄止损下检验新增历史信息的问题。当前仍无加大投注、正式晋级或完成总目标的证据。

TODO：root 精确授权后只运行一次，随后由 Stage125 独立复核完整数据、模型、分数及 Stage124 资金；金融不支持就停止这个固定包。
