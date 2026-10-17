# Stage264 老合约日线补充与天勤失败归因

- line_id：`futures_trend_rollover_shape_same_volume`；day模式；分支`codex/ai-training-data-expansion`；来源HEAD `071018b0c3bbfe6cbc49191fea59fa91d50b8495`。
- 执行：2026-10-17 17:24起；本汇总记录时间17:48 CST。
- 是否重要突破：否，真实数据准备有明显进展，尚无新的策略或AI有效性证据。没有正式晋升或新A/B候选。
- 用户授权：继续补主力前真实日线，不下分钟、不缩AM、不反复跑回测；随后明确要求解释天勤为何失败。

## 外部调研与判断

先读registry、LINE及Stage263合同，调研TqSdk官方文档/GitHub、Akshare官方实现、EDB、三所官方历史档案，以及Tushare/RQData历史合约约定。日线必须绑定真实交割年月，不能用主连、2025同名CZCE合约或合成零值代替2015历史。

天勤账号成功登录，期货行情权限`futr=true`；区间下载权限`tq_dl=false`。`get_kline_data_series`在本机SDK权限门拒绝，错误明确为“仅限专业版用户使用”。普通`get_kline_serial`及2015年`TqBacktest`时间快照均由服务端返回`SHFE.rb1505`为non-existent instrument。后者只证明本次具体合约查询失败，不能外推全部退市合约不可用；更不能保证升级套餐一定补齐。不是密码或周末休市所致。未购买或申请试用。

依据：[天勤区间接口文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.TqApi.get_kline_data_series)、[Sina接口开源实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_zh_sina.py)、[EDB文档](https://doc.shinnytech.com/edb/latest/md_server.html)、[上期所官方下载索引](https://www.shfe.com.cn/reports/tradedata/datadownload/download.json)。完整天勤诊断见本阶段`outputs/stage264_pre_main_daily/tqsdk_diagnosis/explanation.md`及三个脱敏JSON。

判断：上期所官方年包是当前最可靠且实际可用的扩充路径；Sina控制样本存在OHLC与缺日问题，不能直接批量；其2015样本及EDB样本为空。郑商所当前客户端返回HTTP412，大商所官方请求超时，只记录当前访问阻碍，不把它们写成数据不存在。

## 本次变更与参数

- 新增研究工具：`stage264_build_daily_manifest.py`、`stage264_probe_public_daily.py`、`stage264_download_shfe_years.py`、`stage264_normalize_shfe_years.py`、`stage264_diagnose_tqsdk.py`及四个边界测试模块。
- 新增研究依赖：本机研究`.py311`安装`xlrd==2.0.2`以读取真实BIFF XLS；生产环境不变。
- 新增冻结manifest、请求/下载回执、原包/输出SHA、隔离数据及独立复核证据。日常记录只写本研究线；不触碰其他线与已有registry脏改动。
- 新增/修改/删除策略参数：均无；AM120、108特征、C=.20、60日标签、Top10+fu、风险、出场和正式0.5R均无变更。
- 修改/删除既有研究脚本：无；新增/修改/删除财务回测结果：均无。

## 数据范围与结果

完整目标为2015—2019的14品种、231个真实合约epoch，必要时补2014前史；231个上市/退市日期仍unknown，不能声称已获得完整生命周期。

本轮实际下载上期所2014—2019六个官方年度ZIP，共21,606,045字节、17个XLS，SHA/CRC与官方索引绑定通过。范围为au/cu/hc/rb/ru/sp六产品124个合约epoch：

| 指标 | 结果 |
| --- | ---: |
| 有效唯一日线 | 29,316 |
| 拒绝空OHLC无交易占位 | 376 |
| 相同/矛盾重复 | 0 / 0 |
| 相比现有库新增合约日 | 22,170 |
| 其中严格首主力日前新增日 | 18,594 |
| 与现有库重叠日 | 7,146 |
| 重叠OHLC不一致 | 0 |
| 重叠六字段完全相同 | 6,276 |
| 重叠V/OI至少一项差异 | 870 |
| SHFE首主力日AM120覆盖（全mapping时钟） | 6/124 → 99/124 |
| Stage263可比2015 preload时钟AM120覆盖 | 6/124 → 92/124 |

这是隔离数据集的联合日期覆盖计数，未导入或替换主库。仍不满足AM120的合约未用后续数据、零值或缩窗口凑数；实际上市较晚本来可能没有120日，覆盖不足不等于每一日都是漏数。

17个原XLS脚注均说明V/OI为双边手数，OI是当日收盘持仓。870个差异中868日同时精确满足“官方V=2×旧库V”和“前一有效交易日官方收盘OI=2×旧库当日OI”，支持旧库这一局部为单边成交量/开盘OI；同日OI无法统一除2匹配。剩余ru1905两日分别OI差2和V差4，保留隔离，不为小差异反复修补。官方raw保持原单位，旧库保持原值，未静默换算或混合。

官方档案处于202401重发布路径，属于事后档案；按历史日期过滤不能证明当时可见的发布字节。完整日历/上市证明、另外两所历史、跨源量/OI合同仍有缺项。

## 回测与验证

- 本轮财务回测次数0，模型拟合0。TqBacktest仅用于有界行情时间快照，不执行策略、不生成账户收益。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部不适用，不借用Stage263旧结果当新结果。
- 23项针对性测试通过，覆盖跨十年身份、首主力日时钟、无未来预热、源索引/下载边界、真实XLS格式、OHLC/重复、只读库、单位/OI时点与脱敏。
- 独立agent直接读取全部17个XLS，复算所有有效键与六数值、覆盖、重叠、单位证据，并检查下载器和天勤脱敏诊断；17:48签发`shfe_official/independent_shfe_review.json/.md`，P0=0、P1=0，接受限定数据结论，不为review状态改写冻结数据。
- 主库SHA仍为`273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`；映射SHA仍为`55e95a468f4ebd989e5db4da282d69a319ebc75ea08a068e1be8ff87ef1ff325`。registry保留进入本轮时的SHA与脏状态，未修改。
- CTP/券商连接与订单/撤单调用均0；正式源码、master、生产、launchd与私有配置不变。

## 输出与决策

- 总摘要：`outputs/stage264_pre_main_daily/stage264_summary.json`。
- 上期所精简证据：`artifacts/stage264_shfe_normalization_evidence.json`；下载记录、规范化和其余探针分别有本线独立stage。
- 大行情CSV、原始ZIP和完整原始审计仅在本机ignored输出保存。决策相关轻量证据登记到`research/ai_assets/`，不将原始行情、数据库或秘密加入Git。
- 本阶段接受边界：上期所独立原始/规范化数据验收；跨源合并与全池训练尚未就绪。下一步先获取另外两所可验证历史和统一量/OI时钟合同，再决定一次统一源与同模型比较；现在不跑部分池并将其冒充五年全池扩样。

## 开始与结束反思

- 是否过拟合：开始否，结束也无新增选参型过拟合。原因是仅按真实合约/年份与预声明数据质量补数，没有看收益选择数据、模型或参数；既有模型的历史选择偏差与事后档案限制仍保留。
- 是否值得继续：开始是，结束有条件是。新增18,594个主力前交易日确实改善数据底座；继续价值在剩余来源与语义一致性，当前重复训练/账户回测价值低，停止依赖缺项的运行。
- 合入建议：更新本线LINE；不改registry或根memory/back_log；仅归档当前研究分支，不晋升正式版。
