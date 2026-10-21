# Stage162 精确合约会员分布 source-only 实现

时间：2026-10-19 02:05 CST；line_id `futures_full_market_long_signal_ai`。先读 registry/LINE，按 Stage161 冻结协议实现；仅本文件和两个专属源码/测试文件新增，不改 LINE、registry、161或旧数据。不是重要突破；没有实际全历史运行，没有新金融结果。新增 fit/cash/SQL/network/下载/价格/labels/模型均0，累计仍397 fit / 210 cash；所有权益、收益、DD、Sharpe、交易等指标 N/A。

协议为 `outputs/stage161_member_distribution_source_protocol/protocol.json`，11728B，SHA256 `ce6329b0f806e69d62d34a894b3738df2a65fdcf557c873bffb37392208b73ca`；补充解释1244B、SHA `9e94d0e977f4ae56ac3329a5db9e2a23b9dea5b71e8daf99482cdd6573ec439a`。两者在CLI硬绑定，不添加授权系统；root另做exact-source实际授权。调研沿161已接受的本地语义和来源认识，本轮不再联网或重复六日期稀疏probe。

新增 `tools/stage162_member_distribution.py` 与 `tools/test_stage162_member_distribution.py`。导入不读取研究数据、无输出副作用；入口仅 `--output` fresh目录，已有目录拒绝覆盖。actual只由root启动一次；失败留下started/terminal，不自动重试。本记录仅交付实现，不声称完整数据结果已经通过。

## 固定输入与输出接口

输入只沿161 `input_bindings`：119完整3588日 date_manifest及accepted source acceptance/receipt、108源日期清单、154已接受10880 epoch/98代码目录的epoch/product_id、完整052绑定5587日历、129 dataset manifest与原1552456 action/399252 mother身份列。129大CSV仅单遍身份投影，原文件SHA继承已接受manifest并核尺寸/前后stat，明确不宣称本轮重新hash；只取固定身份/u/epoch列，不消费收益、标签、价格、成熟、score或未来状态。action序号意义沿129原写出代码核实，不猜旧score字段。129:218—221直接写 `sequence_index=action_sequence_index=seq`、`event_id=action_id=key`、`actual_epoch=reference_epoch=epoch`；mother_sequence_index/mother_event_id是独立母行身份，不能与action字段强制相等。root确认accepted132:298已验此语义。最终实现只核这三组action自身别名，母子ID保留原值；actual_epoch不是未来选中合约。

known响应仅由119索引指定 `archive_path` 或 `source_path` 取得。每份一次文件读取，同时核原压缩/HTTP body字节与hash、解析JSON；8未知源日原样保留，不打开不存在原文、不重试。正文report_date存在必须匹配源日，否则该日unknown；缺时钟不造日期。没有扫描/下载raw目录，没有读取native价或重新hash DB。

预定输出全部在root指定的 `outputs/stage162_member_distribution/<fresh-run>/`：

- `normalized_scopes.csv.gz`：每源日原始instrument一个scope，精确映射状态/epoch/所/代码，双方独立H/sum/sumsq/人数/空槽/未披露rank/真零/匿名零/999/校验/原因，以及唯一q、版本。all单独审计，不聚合或复制到真实月合约。
- `source_day_audit.csv.gz`：完整3588日、原状态/消费状态、原/current文件及body bytes/hash、report元数据、行/scope/映射/状态计数。未知原8日不填空表0。
- `actions_projection.csv.gz`：原1552456同序全部身份（实际epoch用于取源）+u/v、scope引用、q/missing/原因。`mothers_projection.csv.gz`：原399252同序全部身份（reference_epoch用于取源），包括空ref/noobs。
- `support_summary.json`：源scope和两类完整投影按年/所/产品/状态的分母、观察/缺失/合法q=0；投影另报2020+完整域和2020/2023 cutoff前**来源可得性**。未读成熟/labels，不能称实际成熟训练支持。
- `started.json/terminal.json/manifest.json`：冻结协议/clarifier、全部输入身份、实现/测试身份、新输出hash及0金融预算。manifest不复制全部原raw。

scope_id=`YYYYMMDD|strip(raw INSTRUMENTID)`，source_index为119原清单0-based。每侧vector仅留原source_row/rank、strip ID/name、qty_state/qty及原类型/表示；ID存在优先，否则name，不跨日归并。vector JSON为UTF8、`ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False`，另存SHA；不保存重复完整原表。

## 关键语义与测试

只1..20参与分布，999仅合计，0/-1类别排除；左右榜独立。ID/name任一非空即可识别；原JSON整数/整数float/严格十进制整数字符串数值等价。空identity+空量为物理空槽，无原rank行另计not_disclosed；有identity真0保留，无identity真0不造席位。负/非法/缺量、无身份正量、重复rank/优先侧identity冲突、不明rank均unknown，不删坏行、不修量。每侧999必须有效且等具名有效量之和；不强迫20个会员或左右等量。无999只可留诊断H，primary `total_unverified`；真零分母仍missing。只在双方校验、正和、唯一精确epoch时q=`H_long-H_short`可用。

只按目录code+YYMM唯一映射，SHFE/INE与ordinary/F分别保留，缺失/多候选/不明世纪不猜。每个u只取052日历紧前v同完整epoch；v缺源/缺scope不找最近成功、不ffill、不用u日、不借all。可得性不删母行/子行，也不是后续开仓资格。

TDD七项先RED（实现缺失7 failures），再GREEN，均用合成小fixture，不读取原raw/行情或旧suite：

1. 独立双侧、999/类别排除、手算HHI差。
2. 少于20人、物理空槽/缺rank/实名真0/匿名0区分及左右总量不等合法。
3. 缺/负/非法量、无身份正量、重复rank/侧identity保守unknown。
4. 999缺失/不符不得认证主字段。
5. INE/普通F/世纪歧义/all/无映射不混。
6. 完整日历前驱、失败源日不ffill、不用u、无观察父行身份保留。
7. 原archive/body绑定、坏hash拒绝、fresh输出失败证据保留。

自测命令：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage162_member_distribution.py -v`。初始7/7通过0.003秒；actual前root最后检查发现后来新增的母子别名断言有误，尚未执行全历史。增加第8项“action别名正确而母子ID不同仍须通过”：在原错误断言下RED（7通过、该项明确FAIL），修正后最终 **8/8通过，0.002秒**；同时检查action自身三组别名不一致仍会拒绝。没有运行旧全套。此次是身份断言实现错误修复，没有改161测量或金融参数；actual及新全表审查仍由root安排。

实际命令接口（尚未执行）：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage162_member_distribution.py --output research/lines/futures_full_market_long_signal_ai/outputs/stage162_member_distribution/actual_run1`。不得自行retry已存在的目录。

交root实际运行前的**更正后冻结**：实现29721B、SHA256 `f92940ecdd4c3f2457091b2f3970c677f5e27c7a36b9e4680651543c0fd81a97`；测试9433B、SHA `7e58295ce0e1cb67b79d8f26b18460a2ecd29b6c8adc0c5342b4354f09421383`。旧实现 `204c25fa…38e528`/旧测试 `c426489d…b183ca` 冻结已撤销，未actual。最终8例已过，仅说明有限实现语义；仍不是新输出全表验收。不自行启动actual，只有root可外部授权并执行此新字节版本一次。

开始/结束是否新增过拟合：**本轮没有收益后调参，但长期同史择题风险仍在**；唯一源诊断q由161先冻结，不预设涨跌方向、不扫topN/归一/符号/lag。继续价值：**是，限一次已存全历史来源测量与完整身份可得性审计**；首发PIT、真实成熟训练支持、金融增量和原完整目标均未因此认证。不加注，不恢复旧K/OI/FX/模型/stop/risk救参。

## 02:14 root唯一actual事实补记（尚未accepted）

root以更正后冻结字节完成唯一全历史source-only实际运行，`outputs/stage162_member_distribution/actual_run1/terminal.json` 为 `completed`，耗时 **169.720891375秒**，retry=false；新增fit/cash/SQL/network均0。只核小型 `support_summary.json/terminal.json/manifest.json`，本执行者未重测源码、未重读raw或大CSV、未重复actual。163独立审查已由root启动，**本补记不是accepted声明**。

3588个源日状态保留为3567 HTTP200、13复用、2 interrupted_unknown、6 network_error；3580份已知原文各读一次，8未知未读。目录10880 epoch/98代码。消费原body **1266731628 B**，等于新原取1261656239 B＋13复用5075389 B；这是读取已存归档，新增下载为0。消费压缩/原样文件共142503204 B。

规范化共211023 scope：170803 verified、4335 unknown、35885 all排除审计，total_unverified为0；映射171066 exact_epoch、4072 unrecognized、35885 all。有效源观测仅SHFE159838、INE10965；不能写成六所分别都有新增观测。all不进入真实合约投影，不明instrument未伪映射到相邻月份/市场。

| 完整身份投影域 | 全部原行 | 来源可观察 | 来源missing |
| --- | ---: | ---: | ---: |
| action全域 | 1552456 | 165413 | 1387043 |
| action 2020+ main | 966740 | 110474 | 856266 |
| mother全域 | 399252 | 48796 | 350456 |
| mother 2020+ main | 161014 | 30058 | 130956 |

六所全部母/动作仍保留，其中mother无reference原186400行、2020+44788行原样保留missing。full action合法观测q=0共114、2020+39，未把这些真0当missing；mother观察q=0本次为0。上述均是来源可得性，未读成熟/labels，不能解释为实际训练样本或金融支持。

新manifest为9226 B、SHA256 `16fd10c44f69f40d787fcb221d37b2755a2a3e881a89bc6ed3dc84f5f9278531`，在 `outputs/stage162_member_distribution/actual_run1/manifest.json`；其同目录 `support_summary.json` 给完整年/所/产品/原因及cutoff前来源分母，`source_day_audit.csv.gz` 保存逐日原文绑定与消费状态。当前仍397 fit / 210 cash，不增加金融运行；来源成功不等于PIT、alpha或原全市场目标达成。
