# Stage058 EIA旧期小表来源可执行探测

- line_id：`futures_full_market_long_signal_ai`；时间2026-10-18 14:59 CST。
- 目标保持全市场全品种long-only，先新信息净收益/回撤，再窄损/加注；不收缩到油品交易池。
- 本轮为只读来源可执行性探测，不是策略/模型实现或数据资格终点。先固定3个官方URL：archive首页、2011-08-03旧期、2020-01-03旧期；每请求上限20秒，不下载分钟，不读原生大库，不拟合或回测。
- 事前问题：官方旧期是否真的有Table1下载路径与release/data-ending身份，避免仅凭搜索摘要声称首发数据已可取。最多抓取这三页，能见Table1再取两份小CSV，不做全期扫描或新参数搜索。
- 外部依据：[官方archive](https://www.eia.gov/petroleum/supply/weekly/archive/)、[官方schedule](https://www.eia.gov/petroleum/supply/weekly/schedule.php)、维护者[eia库](https://github.com/ropensci/eia)；新信息经济判断见057。
- 开始过拟合：否，尚无新成绩且只核实事前固定来源。继续价值：是，直接决定能否一次获取新实物数量观测；若路径不可取则报告确切原因，不重启旧包。
- 所有原始HTML/CSV仅存outputs的excluded_raw_sources，不登记Git；派生身份/数值及收据随后另存。
- 本阶段新期末权益/收益/回撤/Sharpe/滑点/交易次数/胜率均N/A，不把来源成功当收益成功。
- 结果与终态见outputs/stage058_eia_small_source_probe/；本记录在探测前冻结，真实结论随后依完成收据补一份唯一结果记录。
