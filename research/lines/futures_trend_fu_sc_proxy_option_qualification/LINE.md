# FU-SC 代理期权凸性保护资格线

- line_id: `futures_trend_fu_sc_proxy_option_qualification`
- 创建时间: `2026-07-12 23:00 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 独立研究分支
- 当前状态: Stage002 无网络 execution-data preflight 已完成并关闭本线；固定 `FU -> SC` 代理期权在3个事件只能选到开仓日当天到期合约，selection `29/32` 未过硬门；无策略候选
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改正式实盘、CTP、邮件、launchd、AI 月池或其他研究线

## 研究目标

- 验证 2022 年没有 FU 同标的期权时，SC 原油期权是否具备作为 FU 风险代理的最低数据与基差稳定性资格。
- 只在数据门和执行门都通过后，才允许讨论固定预算的 SC 期权保护层。
- 最终策略目标仍是每个验证起点保留正式 A 至少 `70%` 收益，同时严格降低最大回撤并缩短 2022 水下期。

## 第一性假设

- FU 是燃料油，SC 是原油；两者存在上游原料与炼化链经济联系，因此 SC 比随机商品或固定黄金更有跨品种对冲先验。
- SC 期权自 `2021-06-21` 起上市，时间上能覆盖 2022 FU 核心事件，而 FU 期权到 2025 才上市。
- 跨品种对冲把“同标的缺失”替换为 basis risk；若 T-1 相关性或 beta 在半窗中不稳定，这条路线没有资格进入期权行情与收益测试。

## 与既有路线的区别

- 贵金属/CFFEX overlay 是固定线性收益腿；本线只研究与 FU 风险同源的代理期权凸性。
- fixed sleeve/现金桶是资金稀释；本线不降低 C9 期货仓位。
- covariance/MRC 是缩原仓；本线不改变原候选手数。
- 行业 cap/删减是风险限制；本线额外购买最大损失限定为权利金的工具。
- 没有仓库历史阶段测试过当前 C9 的动态 `FU->SC` proxy-option cross-hedge。

## Stage001 冻结合同

- 样本：Stage131 中 SC 期权上市日及以后全部 `fu.SHFE` 事件；不只取亏损事件或 2022。
- 核心子集：`2022-03-09 -> 2022-06-29` 的 `6/6` FU 事件，只用于硬门，不单独拟合。
- 价格源：本地 SQLite 实际合约日线；禁止连续主连跨合约跳变收益。
- 每个日收益 `d` 的 FU/SC 实际合约只能由 `d-1` 已知 OI 最大值选择，平局按合约代码固定排序。
- 合约收益使用同一实际合约的 `close[d]/close[d-1]-1`；不得把不同合约价格直接相除。
- 每事件使用严格 `< entry_date` 的最后 `126` 个共同有效日；不足不补、不缩窗。
- OLS：`fu_return = alpha + beta * sc_return`；同时计算 Pearson correlation。
- 三窗固定为全 `126` 日、早 `63` 日、晚 `63` 日；不扫描窗口。

## Stage001 硬门

- Stage131 输入 SHA 匹配，post-listing FU 事件全部有唯一终态。
- 无重复 `product/date`、无未来日期、无跨合约价格相除、无同日 OI 选约。
- 核心 `6/6` 事件拥有完整 126 个共同日；全部 post-listing FU 事件完整率 `>=90%`。
- 每个完整事件的三个固定窗都必须 `beta > 0` 且 `corr >= 0.50`。
- 核心事件 beta/corr 通过 `6/6`；全部 post-listing FU 事件通过率 `>=90%`。
- 只有本地 beta 门全过，才允许逐事件查询 SC 历史期权链；历史链核心覆盖 `6/6`、全部覆盖 `>=90%`，空/目录缺失/权限失败均留在分母。

## 机械决策

- 任一本地 beta 硬门失败：`CLOSE_LINE_BASIS_RISK_INELIGIBLE`，不请求期权行情、不回测。
- beta 通过但历史链失败：`CLOSE_LINE_OPTION_CHAIN_INELIGIBLE`，不请求 premium、不回测。
- 全部通过：`ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY`；仍然 `ready_for_option_strategy_ab=false`。

## 反过拟合边界

- 不把 `fu` 换成别的亏损品种，不把 `sc` 换成 `MA/i/m`，不扩多板块映射。
- 不改 126/63、0.50、90%、OLS 形式、合约选择法或 SC 上市日起点。
- 不按 2022 结果挑方向、事件、月份、期权 strike/DTE 或保护预算。
- Stage001 不读取 realized PnL、未来收益、期权收益或账户权益。

## 当前 TODO

1. 本线关闭，不下载 entry-day minute/tick，不计算保护收益，不跑 A/B、多周期或 live。
2. 禁止删除3个失败事件、放宽 `expiry > entry_date`、改选下一 SC 月或扫描 strike/DTE 救参。
3. 下一实验必须另开结构不同的新研究线，并重新完成外部调研、预声明和独立 review。

## Stage001 最终结论

- SC 上市后全部 FU 事件 `32/32`、核心 `6/6` 均有严格 `<entry_date` 的126共同日。
- 三窗最低相关系数：full126 `0.744848`、early63 `0.667376`、late63 `0.714616`；三窗 beta 最低 `0.767208/0.713699/0.773751`，全部为正。
- T-1 违规、跨合约价格直接相除、重复日期和未来行均为0；数据库前后 SHA 一致。
- SC 历史 option metadata：核心 `6/6`、全体 `32/32` extracted；`2,148` 行，CALL/PUT 各 `1,074`，wrong underlying、event-option重复、无效字段与过期标记均为0。
- 两轮独立 review：beta `P0=0/P1=0/P2=2/P3=3`；chain `P0=0/P1=0/P2=1/P3=1`，最终准入置信度 `99%`。
- 32 个事件窗口高度重叠，最多共享 `123/126` 日；`32/32` 是机械事件 gate，不是32个独立统计样本。
- 当前机械决策：`ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY`；`ready_for_option_strategy_ab=false`、`ready_for_live=false`。

## Stage002 最终结论

- 32份 Stage001 cache 均完成 raw -> normalized 的独立语义重算，metadata semantic `32/32`，无网络调用。
- 固定 long FU -> PUT、short FU -> CALL，按 T-1 SC prior close 最近 ATM 且 `expiry > entry_date` 后仅 `29/32` 可选。
- 失败事件为 `2023-08-15 FU2310/SC2309`、`2025-02-12 FU2503/SC2503`、`2025-06-12 FU2509/SC2507`；目标期权均在 entry date 当天到期。
- 首轮独立 review 发现无选券事件被误计为粒度通过的 P1；修复后 selection/granularity 均为 `29/32`，核心粒度 `6/6`，聚焦测试 `4/4`。
- 修复后独立终审 `P0=0/P1=0/P2=0/P3=0`、闭线置信度 `99%`。
- 最终机械决策：`CLOSE_LINE_SELECTION_INELIGIBLE`；`ready_for_entry_day_data_canary=false`、`ready_for_option_strategy_ab=false`、`ready_for_live=false`。

## 外部资料

- https://www.ine.cn/eng/circularnews/circular/202106/t20210611_821168.html
- https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html
- https://www.sciencedirect.com/science/article/pii/0148619587900130
- https://www.cmegroup.com/education/courses/introduction-to-grains-and-oilseeds/learn-about-basis-grains
