# COMMON52＋K 2015起区间延展实施计划

> 执行：subagent-driven-development；沿用户已授权的现有规则延展，不重新询问设计许可。

- 时间：2026-10-21 14:27 CST；line_id：futures_full_market_long_signal_ai；day；branch codex/ai-training-data-expansion；有界延展，不触发正式A/B/C或多周期晋级。
- 目标：原100万账户从2015首个源交易日连续运行到2026-10-16，输出基础/压力两曲线及原始数据。
- 合同：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage673_common52_2015_extension_protocol/protocol.json)，所有新结果前固定；非重要突破。

## 固定边界

原52特征、Ridge1、单族0.25%/总2%/保证金25%/1.1、.25N止损、非单调20low、无止盈/加仓、K及anchor、费用/容量全部不变。新增2015模型只读2015前已成熟样本，旧2020/2023 scores精确复用；2015起资金连续运行，不拼旧净值。全98/95及无源/无观察/未知保留；严禁未来标签筛预测或今日仍存续品种筛历史。

## 任务

- [ ] 674只metadata核129原全历史、130旧分数与132native覆盖；不重复payload审计，不SQL/下载。
- [ ] 675新增最小runner与有意义fixture：双时钟成熟、3段cutoff、K历史边界/元数据、完整母体与旧2020+选择身份；复用已验纯函数。
- [ ] 676独立源码预审，root绑定source_ready/source+inputs后唯一actual：最多1新fit/2新cash；同session持续观察，不因超时重启。
- [ ] 676实际终态后一次完整核验：训练方程与时间/预测、选择、2账会计/成本/未知/summary/年度/curve，0refit/0策略重放。
- [ ] root绘制PNG+可交互HTML、导出CSV并视觉核对；记录完整参数/结果与反思，最后一次更新LINE/registry。

## 重点核验

156旧cutoff_for不能把2015伪标2020；157旧硬编码起点不能截掉早期；native/K边界须覆盖早合约；旧score只用main；资金从2015自有状态连续。失败只定位实质性问题，不修无关小项或用收益救参。

## 财务指标与反思

本协议尚无结果，期末权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A。预计新增1fit/2cash，旧587fit/294cash+1partial。开始新增按结果调参过拟合否；长期同史择题风险高；继续本次周期延展有价值。完成后保留所有结果，不自动晋级或增加投注。

无新分支/工作树/Git暂存提交推送/正式/生产/CTP/邮件/定时任务变更。根总账不写普通阶段；root仅收口一次LINE/registry。
