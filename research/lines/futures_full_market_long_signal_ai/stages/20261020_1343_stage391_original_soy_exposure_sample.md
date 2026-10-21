# Stage391：实际取得并解析固定2020原发布大豆暴露样本

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 13:43 CST；非重要突破，属于386/388已固定单样本的来源实物推进。
- 先读registry及388 `next_scope.json`。固定`newrun=2020-08-31 00UTC`、`oldrun=2020-08-30 00UTC`、`asof=2020-09-01 21CST`、`V=2020-09-02至09-09 UTC`；本阶段只接原产量与生育暴露，不取得温度、mask或收益。
- 开始过拟合判断：本轮不按结果挑日期/州/列，否；整条路线存在长期适应性择题风险，是。继续做此唯一原发布实物样本有价值，可把386的经济定义推进成可审核数字。

## 实际结果

已从ESMIS两个原发布日期页面中的实际anchor取得两份原TXT，并完成18州全部当前阶段列解析。原件、响应headers、字节数、SHA256和下载时钟保存在`outputs/stage391_original_soy_exposure_sample/actual_run1/`。

| 项目 | 结果 |
| --- | ---: |
| 2019全美产量分母（千蒲式耳） | 3,558,281 |
| 原周报18州产量合计（千蒲式耳） | 3,431,875 |
| 18州产量/全美分母 | 0.964475543106348261983806225534183500 |
| 18州当前pods/leaves缺失州数 | 0 |
| `Σ(Q2019州/US × (pods−leaves)/100)` | 0.846006077091719288049482320255201880 |
| 年报可见各州数字合计−US | 0 |

这是当前覆盖州的**生产加权生育暴露份额**，不是预期收益、胜率或热害值。报告原脚注的96%是上年播种**面积**覆盖，不能代替实算的96.44755431%产量覆盖。未将18州权重重新归一到100%，其他州没有被赋0或分摊给覆盖州。

## 原件精确通路与绑定

1. [官方2020-01-10年报原发布页](https://esmis.nal.usda.gov/publication/crop-production-annual-summary/2020-01-10)实际HTTP200，21,034B。由该页`cropan20.txt`anchor取得[原TXT](https://esmis.nal.usda.gov/sites/default/release-files/k3569432s/sj139j59z/vm40z7543/cropan20.txt)：549,247B，SHA256 `232aadcb45eafd4638d1b87977065cf0d99aa9352c775f1d810213018328319b`。原表2017/2018/2019六列中第6列才是2019产量（千蒲式耳），不是第3列2019单产；TXT行2632—2679附近对应PDF第53页。原全美行2675为3,558,281。逐州原行号和完整六token均入输出。
2. [官方2020-08-31周报原发布页](https://esmis.nal.usda.gov/publication/crop-progress/2020-08-31)实际HTTP200，20,898B。由该页`prog3620.txt`anchor取得[原TXT](https://esmis.nal.usda.gov/sites/default/release-files/8336h188j/t722hz61w/cf95k112t/prog3620.txt)：63,712B，SHA256 `d62776648672a0da1656b4bcc67419745be826809ad964fc5ef5fd1eb3c81918`。Pods表TXT151—181行，Leaves表183—214行；对应先前已读PDF第3、4页。四列是上年同周、上周、本周、5年均值；只取本次原发布的**第3列**（week ending2020-08-30），不取下周对上周的修订值。

两个定位HTML的真实下载及hash也留在收据里。工具web缓存曾不能打开Progress页，但实际源HTTP200；缓存错误没有被解释成源不存在，没有换日期。PDF是root事前批准的同次发布备用分支，实际未使用，未安装PDF依赖、未新增PDF下载。

## 全18州与原显示的零/缺失

完整逐州数据见同目录`exposure_rows.csv`和`exposure_rows.json`。每行含`Q2019、US分母、pods、leaves、w、g、w*g、缺失原因、三条原始行及行号/单位/原token`。州集合按原Pods/Leaves实际共用18州，不按天气/金融结果删选：Arkansas、Illinois、Indiana、Iowa、Kansas、Kentucky、Louisiana、Michigan、Minnesota、Mississippi、Missouri、Nebraska、North Carolina、North Dakota、Ohio、South Dakota、Tennessee、Wisconsin。

Illinois与Missouri本周Leaves显示`-`。**同表214行明确`- Represents zero.`，所以它们是明确报告的0**，并非未展示、空格或不报道补0。原年报Florida与West Virginia的2019`(NA)`仍保留null及“2019停止估计”的脚注，不被改为0。年报已显示数字相加恰与US相等，只作为表内算术检查，不推断未单列州真实产量为零。

原周报自带18州汇总Pods95、Leaves8，未被当成本文加权`g=0.87`；使用逐州2019产量乘逐州阶段差再求和。`pods≥leaves`且都在[0,100]范围，未clip或修补原数。

## 日期与研究可知假设

- 年报：官方页发布日期2020-01-10，正文2019 Summary/January2020；当前响应Last-Modified为`2020-01-10 17:17:18UTC`。2019产量在2020生长期前已公布，未使用2020收成。
- 周报：正文6—8行与官方页都标2020-08-31；参考周日2020-08-30不是可知日。884—886行原政策写首个工作日16:00 ET**之后**发布、次周可修订。按`America/New_York`真实夏令时转换，最早政策下界是`2020-08-31T16:00-04:00`=`2020-08-31T20:00Z`=`2020-09-01T04:00+08:00`。固定asof9月1日21CST比这个下界晚17小时。
- 当前周报响应Last-Modified为`2020-08-31 20:01:22UTC`，折中国9月1日04:01:22。但这只是2026年取得实体的archive metadata，不是我们实际在2020观察到的first-seen；定位页日期字段的12UTC也不是报告真正12UTC发布。
- **历史研究假设**：这份标注8月31日的原官方报告在固定9月1日21CST之前已公开。政策“after16ET”只给下界，不能单凭它证明上界；当前Last-Modified与原发布日期支持可行重建，但严格历史首见未验证。`strict_historical_first_seen_verified=false`，不声称已获得交易PIT资格，也不因缺严格first-seen永久否决有限历史研究。

## 实际执行与机械适配

唯一脚本：`tools/stage391_original_soy_exposure_sample.py`。实际HTTP共4次、2定位页+2原正文，全部200，每件≤1MiB；正文合计612,959B，连定位HTML合计654,891B。**自动重试0、重复下载0、替代日期0**。

获取脚本启动2次，第一次在第3件年报已完整保存后，因为本地标题guard不接受原件`Crop`与`Production`换行而退出；原件本身正确。首次真实终态完整留在`acquisition_initial_terminal.json`。只将标题空白归一化，并在严格验证前3件原hash与预算后手动完成原计划中**从未请求的第4件**；没有重发前三个请求。修正后第二次终态为两个原件已取得。当前收据中旧`error`是首次guard错误的保留历史，最终状态以`status=acquired_original_bodies_not_yet_parsed`及初始收据绑定区分。

离线解析启动2次：第一次在读年报UTF8时遇原件西语`ñ`字节0xf1而退出；原件高位字节只有0xf1与度符号0xb0。改为无损cp1252解码，表内数字/州名/标题token均ASCII；第二次成功。未改原数据、年份列、州集合或数值规则，不是训练或金融回测失败/重跑。没有执行旧suite。

实际命令依次为：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage391_original_soy_exposure_sample.py acquire
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage391_original_soy_exposure_sample.py finish_unattempted_progress
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage391_original_soy_exposure_sample.py parse
# 上一个parse仅UTF8解码失败；无网络、无产物写入。改无损文本解码后：
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage391_original_soy_exposure_sample.py parse
```

`exposure_manifest.json`绑定全部原件与headers、获取/初始终态、当前脚本和三个解析输出。`original_table_excerpts.json`另留小段原表，便于root/389独审直接核列，无需重下文件。独立复审由root安排，本作者没有给自己颁独立通过结论。

## 边界与下一步

本阶段关闭“唯一固定2020样本的上年原产量/当周生育暴露未取得”这一缺项。没有cropmask或geometry，不能将18州产量权重当州内天气权重；没有接入任何温度修订，`Σw*g`不是全国热害指标。下一步由root把同valid-time热害修订和此原发布暴露样本有限连接；不以全史完整覆盖当先验要求，也不因此扩成全球/多年下载。

本轮代码变化只新增单用途获取/解析工具；新源参数是固定年份/日期/本周列及原权重定义，未修改、删除任何模型/策略参数或旧回测结果。fit=0、cash=0、行情API=0、天气/大栅格下载=0、账户/模型/正式C9/CTP/Git变更=0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

结束判断：本轮没有按收益调参，属于原来源实物推进，继续这个固定样本**有价值**；它不能证明高质量做多信号已找到，更不能支持极小止损加注。完整策略目标未完成，研究记录应保留上述时钟与地理局限，不把一次解析通过变成alpha/资金资格。
