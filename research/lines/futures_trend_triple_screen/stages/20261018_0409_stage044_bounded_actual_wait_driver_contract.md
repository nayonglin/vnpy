# Stage044：同一 B 引擎实际请求的有界数据交付复用合同

- line_id：futures_trend_triple_screen；冻结设计时间：2026-10-18T04:09:30.474871+08:00；非重要策略突破，不改变alpha。
- 用户持续自主研究授权内的常规数据执行选择，不要求重新确认；不是生产部署、金融重跑、模型训练或定时任务。
- 当前唯一金融B attempt1：session70433/PID21822，runner036 SHA34563257...ff43，源HEAD008575e13；原1800秒单请求/7200秒全程预算保持。

## 目标与约束

将已经人工验证通过的 request→已有缓存或正常provider→独立数据算法→atomic response 复用，减少每日期临时副本与人工等待。策略目标仍为更高净收益且更低回撤，数据管线完成不能算实现该目标。

1. 只处理本B已存在、canonical digest与request_fingerprint吻合、audit正在等待的实际request，确认原PID/命令仍live；不生成理论B需求，不提前资格未来日期，不启动或重启金融引擎。
2. 043独立审者的固定算法负责精确DB六字段、raw真实后继、合法分钟、canonical full/anchor、七值聚合、A0新增键及实际gate旧键保护，生成独立receipt；044只编排，不捏造独立审查。041/039/042/040及其协议进入收据后全程不改。
3. 优先已有缓存。只有独立检查返回真实缺分钟、日线已签，才准备并运行冻结041，正常SDK/鉴权/端点/570soft/600hard/父子闭环不变。参数用数组传递，不执行来自request的shell命令。
4. 真实subprocess returncode0后才写terminal_observed并调用043签收，不能从parent_receipt存在推断终态。已存在成功attempt只消费；已有残缺/失败attempt不得自动新起或覆盖，provider错误立即保存事实并退出，不自动重试。
5. 只有receipt/hash/schema/request/原始key集合核验通过才原子发布022 pointer，数据实际注入仍由021原子append保证；不手改engine mapping，不降低门槛、不改数据。
6. 第一批最多4个新增provider连接，运行预算固定且启动provider前预留完整600秒与后处理余量。达到批次上限仅结束driver，不停止原B；后续可用同一冻结source显式续批，不重复已有networkattempt。缺daily raw、未支持多目标、源漂移或资格不通过时保存具体原因并退出，由root处理。
7. 全程journal每个实际request、使用的源码/输入/receipt/data/pointer SHA、local或provider、真实exit和新provider数、总耗时；原始行情与凭证不入Git。独立金融038仍需完整真实B终态后逐账复算全部数据/成交/账户身份。

## 实施与验证计划

- 新建tools/stage044_qualified_wait_driver.py；与043作者协调最小CLI/JSON状态，不触碰对方目录或旧source。先1—2个有意义的拒无真实request/不重试已存在attempt测试RED→GREEN，不扫旧suite。
- root独立源审/精确source冻结后才启动第一实际小批；实际tool句柄必须可持续观察，用户更新不超过60秒。
- 期末权益、收益、回撤、Sharpe、滑点、交易数、胜率=N/A；策略参数和金融结果新增/修改/删除均0；当前累计仍金融8attempt/3 accepted，B1，训练0。
- 开始过拟合判断：否，执行冻结候选实际数据请求，不看收益择取样本或调参。继续价值：是，减少人工等待/一次性代码副本，仍需完整金融结果反证alpha；结束依据实际batch和B结果另记。production_qualified=false。
