# Stage420：u21/D22 完整874合同的有界日期与生命周期续接

记录时间：2026-10-20 18:47 CST。line_id=`futures_full_market_long_signal_ai`；非重要突破。先读registry、417continuation pointers、351模板、354身份/旧展开、356时钟边界，再按418冻结scope SHA69cbc7ff9ff16bb0b46ec3704f6add980c33a4777f96eea4c353579ee117d9da实施。只改新增420工具/outputs及本记录；旧353/354/356、模型、账户、LINE/registry/Git均未改。

## 实际结果

已一次纯元数据展开exit0（exec chunk1536d3，运行耗时0.06408975秒；无live handle），起止2026-10-20T10:45:15.568871+00:00—2026-10-20T10:45:15.677877+00:00。完整874合同×21/22日=1748条同353 schema sessions，按原metadata expiry逐合同生成lifecycle。21日840 operational_regular_schedule、4 expired、30 unknown；22日840 regular、34 expired、0 unknown。不是继承u20的870活跃集合，且未按价量或分数先筛。

sessions.jsonl.gz为85058字节、SHAfb8561c65797b9c2100d035d014cdf3aa46450004009548916c4ef4a905f6bfa；lifecycle.json为814693字节、SHAaaa2dd91753b69a09a160bea3772d5b83968fc8ad85f6df38d3910335b5f4477；manifest.json为9632字节、SHA151cfe8da98d3a0234feb21f3880ce1d083fb090e985ed292e1cd92da95aecc4。bindings已投递419/421作者，键为sessions/lifecycle/calendar/identity/metadata/scope/regular_evidence等。

338原实收TqSdk calendar覆盖10/16—10/27，21、22均明确trading=true；直接复用原绑定，不用周几猜测、不取新calendarAPI。351当前874合同9字段/6模板，以及354全部874显式身份原绑定复用；没有重取metadata或把multiplier未知补0。源模板接收时刻保留，不能把它称明日新接或穷尽当日临时变化。

实现采用原353 expand_sessions同一code对象的FunctionType私有globals，仅替换ANCHORS为21→20、22→21。原module三日期ANCHORS和原文件6387字节SHA均不变，没有复制整个金融引擎。一次六项synthetic fixture通过：原353仍拒22、新隔离22锚21夜盘、26:30跨日、23越界未知、21最后交易日未知、22过期无首开。无旧suite、无实际价量或模型执行；fixture与真实1748展开分开标识。

## 30个最后交易日未知与原13依赖

并非全是郑商所。30个均为202610合约：

- CZCE 15：AP610、CY610、FG610、MA610、PF610、PK610、PL610、PR610、PX610、SA610、SF610、SH610、SM610、TA610、UR610。
- DCE 10：b2610、fb2610、i2610、j2610、jm2610、l2610、p2610、pp2610、rr2610、v2610。
- GFEX 5：lc2610、pd2610、ps2610、pt2610、si2610。

原726依赖中13为：CZCE MA610/SA610/SM610/TA610/UR610；DCE i2610/jm2610/l2610/pp2610/v2610；GFEX lc2610/pd2610/si2610。此列表只说明原依赖归属，不把它继承为u21真实新依赖域。

30个原expire_datetime实际均2026-10-21T15:00:00+08:00；当前常规日盘均09:00–10:15、10:30–11:30、13:30–15:00。但原353语义明确最后交易日必须有exact override，故仍last_day_override_missing、first_open/session_end均null；expire字段不自动充当exact交易结束证明。D22逐合同after-expiry=known lifecycle不准新进，不等于能忽略任何原账户持仓/pending执行依赖。

lastday_source_end_candidates.json仅另存未接受15:00候选上界。若仅提前收盘且没有额外/延期时段，15:00可以在同等级操作假设下作为完成时间上界，早收盘不推迟完成；这与确切session_end、D首开、vendor finality不同。420没有接受该上界、不覆盖unknown或改356约束；root若采用须另显式裁决仅source-completion用途。不能因为收集在15:15之后就把缺失证据悄悄涂known。

## 公开资料及判断

实际4次web定位调用、0原官方HTTP GET。SHFE原小HTML可选项已省略：已有338实收日历足以给这两天候选，额外落盘SHFE年表不解决跨CZCE/DCE/GFEX的最后交易日。未安装SDK、未建永久六所日历服务，不继续查询。

[SHFE 2026休市安排](https://www.shfe.com.cn/services/calenderandholidays/holiday/)显示国庆10/8恢复，与21/22无年度假期冲突；只支持SHFE范围，不排除六所临时公告。[TqSdk维护者datetime.py](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/datetime.py)支持夜盘锚上一真实日期，但通用周几辅助逻辑不是节假日日历资格，因此未取代338。

[郑商所2022 PTA业务细则](https://www.czce.com.cn/cn/uploadfile/2022/08/31/20220831175708933.pdf)提供常规15:00结束和公告调整条款；未声称2022文本就是所有2026品种最新版。[大商所2026焦煤/焦炭factsheet](https://www.dce.com.cn/dce/file/2026-01-15/17684624156122c9a882b9ae6dcbb289019bc092f6fc1681.pdf)官方搜索索引有相同常规末端及其他时段条款；不是已下载原PDF或10个受影响DCE品种的全面证明。[广期所铂官方页](https://www.gfex.com.cn/gfex/sspzb/sspz.shtml)官方索引同样有15:00及其他时段；后续web open超时如实记录，不冒称HTTP原件获取成功。这些资料只佐证候选上界的经济常识，不消除当日exact override缺口。完整限额/访问和判断另存finite_public_reference_judgment.json。

## 反思与后继

开始/结束新增收益择参过拟合：否，完全没有读取价格、score或收益；历史策略适应性风险并未因此消失。继续价值：是，这个必要日期续接避免复用错误活跃集；完成后不扩日历工程或修全域零碎问题。新增/修改/删除金融参数和结果均0，期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A；0 TqApi/行情价格/SQL/fit/cash/financialD/CTP/账户操作，源source_completed_at和D_open_at未由420赋值。完整目标仍active未达成。

本阶段完成即止，后续由419/421使用已投递绑定、422作有界独立审查；明日源窗口前不取价，不回放u20/415，不初始化旧空账户，不执行任何今日不存在的D21成交。
