# Stage027：因果特征与有序准备状态独立复核

- line_id：`futures_trend_triple_screen`；2026-10-18 02:27 CST。
- 结论：本组件有限范围通过，未发现剩余 P0/P1/P2；这不是金融臂、收益优势或生产资格通过。
- 本次仅新增本独立复核输出及本唯一 stage，不改实现、正式策略、LINE、registry 或其他研究线。

## 范围与调研判断

审查设计、计划、两个实现、两个测试及 Task1 修复收据，承接本阶段设计已记录的 CMT、LEAN ForceIndex/EMA 和 Backtrader 调研。此次独立复核未重新联网；不声称再次核验全部经典原文。判断是：两 Force 均值 seed、固定 FI2、逆向准备后以后触发可作为因果机制实验；经典名称、组件正确性和潜在需求数量均不证明盈利。

本次属于纯组件与真实无账户潜在需求复核；未启动第二次 builder，未重复既有 8 组状态、2 组 builder 测试或全仓 suite，未全量重算 FI，未重跑旧 DB 全量 hash，未检查分钟源资格、训练或读取收益结果。唯一真实 builder 的终态由主代理提供为 exit 0；本复核对其输出绑定 SHA 后独立检查，不把代理报告单独当作验证。

## 关键语义判断

1. FI 按真实合约独立计算；三个连续有效 close 才有两个 Force，首 FI 为两 Force 均值，后续 alpha 为 2/3。非正/无效量价、缺真实 calendar 日切段重暖；周末、节假日不制造缺日。源码及已有行为测试覆盖缺日、零量与跨合约边界。
2. B 可于准备当日收盘发 D 条件；C 必须 `setup_day < signal_day < execution_day`，同日准备与信号不通过。首次 setup 不被后续逆向日覆盖。
3. intent 只对唯一 D 有效，不代表成交；只有合法当前 ID、唯一 D 的 `on_fill` 消费准备。下一次 close 使旧未成交 intent 失效，C 不续用旧信号。目标换月、未知周/FI、AI 不允许或已有持仓均取消旧准备；新合约可用自有 FI 历史，但不能搬旧 setup。
4. u 收盘冻结许可、合约和 D；D 收盘的新主力、最终日线或资格不能追溯取消已经发生的盘中 fill。已知 ineligible/position 状态优先 unknown；非正 trigger 阻止 intent。Task1 首版两反例的修复已绑定最终源码 SHA。
5. AI 精确沿原默认 `ai_product_pool_use_next_trade_date_for_entry=False`，按 signal-day 查严格更早 eval-date。2019-12-31 首快照为 18 产品且无 fu；首次含 fu 的 eval-date 是 2022-01-28，不补早期 fu 资格。
6. 原 900 条 native 只投影五项身份字段，C 标签原样保留；B 明确标注 triple_screen。未把 native 与收益、胜率或事后交易结果联表。

## 新鲜验证证据

- 五项构建产物 SHA 均与 summary 一致；summary SHA 为 `8089f924ac5b81ead6acefcbb833b5cd93495facae1c5641facc84df61685c63`，input manifest SHA 为 `426cd031619b42167b150a1c543e367d39f75911612aa5bc101a14da754b3ae8`。
- 只读 SQL 读取源 key，116,394 个真实日线 key 与 FI 缓存完全相同；日期并集为 1,786 个真实 calendar 日。112,953 个 ready 的字段、有限值、连续三日关系及 previous_date 全量自洽。806 项合同 metadata 沿原输入。
- 缓存原因分布：ready 112,953、warmup_close 1,095、warmup_force 878、invalid_volume 1,468。真实样本未出现 calendar_gap 原因；缺日规则的证据来自源码及既有合同测试，不能伪称真实缺日样本已验证。
- 全量 13,900 个 intent 的 ID 唯一；B 13,600、C 295。每项 setup/signal/execution 日、真实目标合同、FI ready、逆向准备、周方向/asof、严格前置 AI 资格自洽；所有 C 均严格先后且匹配原 900 native 的当日身份和标签。
- 原 900 native 的 key、目标与下一真实日全部成立；104 个 C fallback 候选均原身份一致、有资格且指标 unknown。fallback 不构成强制开仓。
- 少量真实价格手算：MA005.CZCE、cu2005.SHFE、rb2005.SHFE 各 10 根（2019-06-03—2019-06-17），共 30 根，独立 raw Force/首均值 seed/后续递推与缓存一致。
- 仅一个新组合因果实验：C 较早准备、u 信号、D 盘中合法 fill；随后 D 收盘发生换月＋ineligible＋周/FI unknown，结果 blocked 且无 fallback，不追溯破坏 fill；另一未成交实例过 D close 后旧 intent 无法复活。fresh 命令 exit 0，细项见 `outputs/stage027_independent_review/component_checks.json`。

## 置信度、限制与后续

对已检查纯状态语义及当前真实产物身份关系置信度较高；未完整独立重播全部状态或计算全流 FI，不推断未测路径绝无缺陷。B 13,600 是永久 flat、尚未消费 setup 的无账户潜在 intent 保守上界，不能解释成真实委托、成交、全账户需求，也不能据此全量补分钟。C 条件 295 与 unknown fallback 104 同样不含资金、仓位、费用或真实执行资格。

本次没有金融回测：期末权益、总收益、最大回撤、Sharpe、滑点、交易次数和胜率均不适用；新增/修改/删除 alpha 参数与经济结果均为零。`production_qualified=false`。后续必须先固定预算分配、首触发分钟成交/止损/重试和真实 hook 因果合同，通过后再讨论一次 B/C 账户实验及独立经济复核。更高收益且更低回撤的总目标仍未达到。

开始反思：过拟合否，审查冻结公式、顺序、身份和因果边界，不搜索收益；继续有价值是，因为不可信状态会使后续金融比较失真。

结束反思：本次没有新增过拟合行为，未按结果修改参数；继续有价值是，但价值在下一实际执行合同与一次可证伪账户实验，不能反复用准备成功代替目标进展。既有历史研究选择偏差继续保留。
