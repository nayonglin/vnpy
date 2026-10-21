# Stage122：固定12月同合约链投影实施

- 时间：2026-10-18 21:05 CST。研究线：futures_full_market_long_signal_ai。
- 是否重要突破：否；这是冻结 Stage121 的实施，不是金融结论。
- 授权边界：仅实施和有限纯语义 fixture，actual 必须等待 root 的精确源码、输入、协议、fresh output 授权。未下载、未读原生 SQL、未训练 actual 模型、未新建标签或资金回测。
- 当前结果：新增收益/权益/最大回撤/Sharpe/滑点/交易次数/胜率均尚无 actual，不填入虚构值；旧结果不修改、不删除。

固定输入角色为 market_protocol/narrow_labels/narrow_manifest。用 accepted070 kernel 的来源桥进行一次原生 SQL，保留 399252 行、98 品种、95 family、六所及原 4074 母表日期；不重认证或 hash 大库。每个 v 使用严格 prev(v) 那天代表 epoch 的两日合法 bar，保留原 5587 native calendar 中 u_index；代表换月时不跨合约除价。固定公历一年前边界，闰日映前一年 2 月 28 日；窗口内任一所需 factor 不可得即 missing，不缩短窗口或补值；真实零保持 observed。新增日因子审计提供原代表、两价、native index、经济资格与状态，供独立审查重构。

投影状态为 observed_fixed12_calendar_month_return_chain 或 missing；完整输出也记录 lower boundary、所需/有效/缺失因子日数、首个缺因子日期。没有新增可调阈值，不做 sign、rank、波动归一化或窗口扫描。

有限验证：先执行新增 6 个 fixture，因两份新源不存在而出现 6 个预期 assertion failure；实施后同 6 个新 fixture 全通过（最近一次 0.791 秒），两工具 --help 均 exit 0。范围覆盖 prev 代表而非当前代表、非连续 native index、闰年边界、严格窗口缺项、真实零、经济资格缺失、train-only scaler、held 标签排除、预测 missing 保留以及六 cell 变异全包停止。不运行旧研究 suite 或重复金融。

开始/结束反思：本次没有依据新收益调参数，故不是本轮 outcome tuning；同史多轮研究的选择风险仍然存在，不能声称未见 OOS。继续有价值：这是一项已预声明、在相同风险成本和原窄止损下检验新增历史信息的问题。当前仍无加大投注、正式晋级或完成总目标的证据。

TODO：root 精确授权后只运行一次，随后由 Stage125 独立复核完整数据、模型、分数及 Stage124 资金；金融不支持就停止这个固定包。
