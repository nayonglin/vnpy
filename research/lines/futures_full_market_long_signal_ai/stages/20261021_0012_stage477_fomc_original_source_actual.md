# Stage477：作者原始FOMC事件表已真实取得

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 00:12 CST；非重要突破。新增数据来源，不是新模型、回测或alpha成果。六所98产品/95家族完整研究目标保持。
- 476 JSON协议在实际前冻结；本次唯一root进程session91694，真实exit0/5.586753秒，3请求/3 HTTP200/0retry。没有下载分钟K线、私有行情、数据库或安装外部工具。

## 真实来源与绑定

作者repo提交API解析为`f788aef7d573f87f28b70ffc3763e73c4886a53f`，提交时间2026-10-11T15:40:25Z，message为“update Fed shocks until September 2026”。随后README和原始CSV都使用该commit固定URL，不用可变main。原474科学调研未核得commit是其当时事实，本阶段真实取得后补齐，不篡改474。

| 原件 | bytes | SHA256 |
| --- | ---: | --- |
| commit API | 102111 | 961dedde41ad3d5cff708b4fb4fe899705ca07b00e001ff4d26121ec984cf2d8 |
| README | 5183 | 5b57b02f4bae14d0cc4a10da9b86147ec2c31c1cdffe3da2b134ebecd35416c2 |
| fomc_surprises_jk.csv | 69885 | 785cb0ac6e50df1779820dffdaf399c312510e44d2b547fabb3925ed9a443300 |

原始数值未改、缺失未补，保存为actual_run1下commit.body/readme.body/fomc_raw.body并有逐请求receipt。数据385行，实际首行1987-11-04 08:30、尾行2026-09-16 14:00；README“since1988”的概述不替代实际首行。FF4 330非缺/55缺；SP500 380/5；SP500FUT384/1。初始schema通用date/time列名启发式没有识别start，所以date_time_columns为空、timestamp重复为null，**没有给日期正确资格**；478独立显式start解析覆盖全385行，不改原源或重跑捕获。

## 语义和研究边界

原表与许可文件取得仅证明可以访问一个作者版本，不证明每个历史u的原发布/PIT。README数据CC BY4.0，代码BSD3，引用Jarociński和Karadi(2020)；不执行其Matlab/PCA/旋转，不取最终shock/月度聚合补输入。raw FF4的完整单位/正号规范与start时区尚未认证，不在本stage把FF4>0标作紧缩，不直接生成上海u/D。

README允许post测量窗口延长最多24h，后续计算窗口保守上界t+25h；这不是原档发布时刻或供应商当时接收证明。root另读作者main.m的“Interest rate surprises”列名单只支持FF4是利率意外输入的作者意图，未自动补齐逐字段单位或时区。原论文PDF未检得Eastern/timezone明文，有限检索结束，不因无匹配证明时区不存在。

478进行一次小源完整审查；480只用2025-06-18/2025-12-10两场Fed官方EDT/EST锚核对解释，不能从两个例子证明385行。后继新经济测量尚未启动、无fit/cash预算；须另冻异质载体、消费时钟和可得收益对象，继承270共同宏观scalar不能直接作全市场异质排序的限制。

## 变更、反思与TODO

新增原始源三body/接收manifest及记录，新增/修改/删除策略参数0、回测结果0。权益/收益/DD/Sharpe/滑点/交易/胜率N/A。累计481fit/258完成cash及1旧partial不变。

开始/结束新增按新收益调参过拟合：否，没有新收益；同史长期择题偏差是。继续一次有限源/时钟核验有条件价值是；无限扩采或重复已取3原件无价值。当前实际新原始观测是progress，但不是完整高收益/低DD或高质量信号目标完成。原四前瞻账户/正式C9/CTP/邮件/launchd/Git均未改，goal active未完成。
