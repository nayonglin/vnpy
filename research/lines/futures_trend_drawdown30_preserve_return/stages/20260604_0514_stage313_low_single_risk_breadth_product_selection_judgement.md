# Stage313 低单笔风险扩池选品判断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读综合判断；回应“减少单笔风险、扩大品种池、每年抓部分趋势、避免高相关、选对品种”的结构路线。
- 是否重要突破：否。方向继续成立，但没有形成可部署候选。
- 是否触发A/B：否。当前新增风险预算仍为 `0%`，没有 paper selector、没有交易白名单。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 外部调研与判断

- 参考资料：
  - A Century of Evidence on Trend-Following Investing: https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing/
  - Trend-Following, Risk-Parity and the Influence of Correlations: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2673124
  - Trend Following, Risk Parity and Momentum in Commodity Futures: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
  - Optimal trend following portfolios: https://arxiv.org/abs/2201.06635
  - pysystemtrade instrument diversification / correlation framework: https://github.com/robcarver17/pysystemtrade
- 我的判断：
  - 这个方向是对的。趋势跟踪的长期优势通常来自多市场、多经济驱动、低相关收益流的组合，而不是单品种持续高胜率。
  - 但“扩大品种池”必须翻译成“扩大有效独立风险槽”。同产业链、同交易所、同宏观驱动、压力期相关性高的品种不能算多个独立槽。
  - “选对品种”不能定义为历史收益榜 topN；更稳健的定义是：低核心相关、不同经济驱动、当时可得 source、容量合格、真实成交/TCA 可闭合、同族同向 top1。
  - 继续宽池收益扫描会有过拟合风险；继续做 source/TCA/forward monitor 和新经济驱动搜索有价值。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无策略参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：只读复核 Stage304/309/311 冻结证据，不新增交易回放。
- 账户规模：沿用 Stage526/Stage079 研究线既有口径，本阶段不生成新权益曲线。
- 成本口径：沿用既有正常成本证据；本阶段不新增滑点压力。
- 样本过滤：
  - 当前 P0 结构槽：`grains_oilseeds / petrochem / base_metals / energy_oil`。
  - P1 新独立槽线索：`black_ferrous(j/i)`。
  - P2 观察族：`soft_agri / precious_metals`。
  - 高相关拒绝：`rubber/br`、`other/PR` 等压力期可能共振品种。
- 策略/归因口径：
  - 使用“有效独立风险槽”而不是“产品数”衡量扩池价值。
  - 使用年度 top6 family 捕获代理衡量“每年抓部分趋势机会”是否成立。
  - 使用 3/6 个月持有体验、source、容量、TCA、live context 作为资金前置闸门。

## 结果

- 期末权益：不适用。本阶段无新增权益曲线。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 当前有效独立风险槽：`4`
  - 目标有效独立风险槽：`7`
  - 当前单槽风险代理：`25.00%`
  - 目标单槽风险代理：`14.29%`，偏好 `<=15%`
  - 若 `black_ferrous(j/i)` source/TCA 全部解决：`5` 槽，单槽风险 `20.00%`
  - 仍缺少独立槽：`2`
  - 当前新增风险预算：`0%`
  - 当前可部署 selector 槽：`0`
  - 当前 paper allowed rows：`0`
  - 当前 trading whitelist rows：`0`
  - 年度非核心 top6 趋势机会：`7/7` 年为正
  - Stage304 宽池壳对比：`All noncore r020` 收益 `3701.4472%`、最大回撤 `-36.3714%`、交易 `1354`、滑点 `1,349,620`；Stage526 参考收益 `3699.9195%`、最大回撤 `-36.2670%`、交易 `905`、滑点 `1,342,190`。说明盲目扩池没有改善回撤，还增加交易复杂度。

## 关键判断

- 可以减少单笔风险，但前提是有效槽数足够。`4` 槽下每槽约 `25%`，风险仍集中；`7` 槽后每槽约 `14.29%`，才接近低单笔风险结构。
- 可以扩大品种池，但必须按独立经济驱动扩，不按品种数量扩。`y/c`、`j/i` 同族同向只能算一个槽。
- 每年抓部分品种趋势收益这个假设成立：年度非核心 top6 趋势机会 `7/7` 年为正。
- 但当前不能晋级：`j/i` 是唯一 P1 新独立槽线索，source/TCA/live context 未闭合；`soft_agri/precious_metals` 低相关且 source 较好，但历史材料性不足，只能 forward monitor；`br` 有收益但核心相关 `0.2783`，继续拒绝。

## 选品准入定义

| 维度 | 当前定义 |
| --- | --- |
| 经济驱动 | 必须能解释为不同产业/宏观/供需驱动，不是同族替代品。 |
| 相关性 | 偏好核心相关 `<=0.10`；压力期共振品种即使历史收益高也拒绝。 |
| 同族预算 | 同一产品族同方向最多 top1 获得风险预算。 |
| 材料性 | 历史机会要足够，但不能仅靠历史收益晋级。 |
| source | 必须有 point-in-time 可得外生/状态源、received_at、source_url/raw_hash。 |
| 容量 | 保证金、成交量、交易成本要能承载 50万/目标账户口径。 |
| 执行 | fresh live context、真实 tick、真实 `vt_orderid`、order/trade/tick TCA 闭合前新增预算为 `0%`。 |
| 持有体验 | 不能恶化任意启动后的 3/6 个月左尾体验。 |

## 结论

- 本阶段结论：
  - 用户提出的方向成立，而且比继续微调 Stage079/C3 小参数更接近第一性原理。
  - 当前不应该直接加宽池或回测收益榜；正确路线是把风险预算从“当前 4 槽高集中”推进到“7 个左右独立风险槽”。
  - 当前唯一值得补证的新槽是 `black_ferrous(j/i)`；但它成功也只到 `5` 槽，不足以晋级最终 allocator。
- 是否进入下一步：进入，但只进入补证和 forward monitor，不进入收益回测/A/B/交易白名单。
- 下一步：
  1. 继续闭合执行无偏差链路，至少完成 fresh live context、tick snapshot、`vt_orderid` mapping 和 P0 live TCA。
  2. 修 `j/i` 的 DCE source 或授权替代源，并补每品种真实/独立分钟 TCA。
  3. 对 `soft_agri/precious_metals` 建 point-in-time forward monitor，只观察，不回头拟合。
  4. 寻找至少 `2` 个非 DCE、低核心相关、source 可执行、容量合格的新独立经济驱动。

## 过拟合反思

- 运行前判断：否。问题是结构性风险分散，不是拟合单品种收益。
- 运行后判断：否。高收益但高相关的 `br` 继续拒绝，低相关但证据不足的 `j/i` 也不晋级，说明没有用历史赢家救结果。
- 原因：本阶段输出是准入定义和缺口，不是交易名单或收益优化。

## 继续价值反思

- 运行前判断：有价值。它直接解决 Stage079/Stage526 的集中度和持有体验问题。
- 运行后判断：有价值，但必须收敛。年度机会存在，证明方向值得做；盲目宽池已被 Stage304 反证，下一步只能做独立风险槽和可实盘证据。
- 原因：当前瓶颈不是没有想法，而是缺两个可部署独立槽，以及真实执行/TCA证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage313 判断。
- 是否更新 `research/registry.md`：是，更新最新阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选或重要突破。
