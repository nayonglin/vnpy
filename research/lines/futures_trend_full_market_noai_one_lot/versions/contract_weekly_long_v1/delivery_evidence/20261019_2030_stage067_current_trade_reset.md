# Stage067：逐笔切换后的Reset axes只读UI修复及最终v2绑定

- 时间：2026-10-19 20:30—20:32 CST；研究线 `futures_trend_full_market_noai_one_lot`。
- 重要突破：否；纯交互缺陷修复，不产生金融新结果。
- 新增：`tools/stage067_current_trade_reset.py`、对应3项测试、本记录与机器验证JSON。未改canonical、063/062或任何既有模块/输出/LINE；金融没有重跑。

## 问题与判断

根任务浏览器复现：首笔LH范围约0..315，切到下拉value=1的ag202602.SHFE long（1145..1658），增加周K到3周期，Zoom in后点击Reset axes会复用首笔范围、令当前交易空白，next/prev可恢复。根任务并已确认资金总览v1的独立固定曲线没有该问题。

查阅 [Plotly官方modebar源码](https://github.com/plotly/plotly.js/blob/main/src/components/modebar/buttons.js)：handleCartesian的reset确实复用初始range；另参考[公开Plotly.relayout接口](https://plotly.com/javascript/plotlyjs-function-reference/#plotlyrelayout)。判断：不改canonical或其私有state，以最窄的当前交易重置处理替代该按钮的继承行为。

## 实现范围

在新版本HTML的 `</body>` 前追加唯一经典script（独立IIFE），原HTML其余字节不动。document capture只拦截 `#chart` 内 `[data-title="Reset axes"]` 的click。读取页面已有 `filtered[active].meta` 和 `visiblePeriodOptions(meta)`：当前所有可见xaxis.range重置为当前交易的chart_x_start/end、autorange=false；每个周期价格和成交量yaxis.autorange=true，再调用公开 `Plotly.relayout(chart, update)`。preventDefault+stopImmediatePropagation仅对有效的本chart重置动作执行。

不读取/修改Plotly私有state；不改过滤、排序、翻笔、其他按钮、records或任何图形数据。空filtered、空周期、非本chart/其他按钮不操作。所有父产物hash和source冻结证据核验后才生成独立新目录；新增provenance绑定父summary/全产物/生成器/script/records。金融summary原字段、原周线provenance和source_warning保持原值。

## TDD与核验

- RED：067入口缺失时3项测试全部明确失败。
- GREEN：**3 tests PASS，0.137秒**。Node fakeDOM+Plotly spy覆盖0..315→1145..1658两笔不同range、2→3周期、所有x/y轴键、空filtered/空周期/其他按钮/非chart不操作；private getter若被访问会抛错。临时fixture证明只追加HTML、其他文件字节/summary金融与周线字段不变，拒绝输入篡改/嵌套/重复输出/重复补丁。
- 此前全线216项通过；新增067后整线最终测试按根任务安排执行，本子任务未重复该整套，也未提前宣称219通过。
- 067生成器SHA256：`6dc2b20582ba593f9e337112e1e738f52ff5e8e845a5f93a721d06095d7af68b`；新增script SHA256：`42f4ba41a48a97646262576e04181fdf1cdea87443251bd0005fedfbd3268520`。

## 实际输出与独立验证

按根任务明确授权，067生成后使用冻结062重跑总览到新目录，均退出0；旧两个v1目录保留：

- 新逐笔：`outputs/recap_20261019_contract_weekly_long_v1_reviewed_v2/index.html`。
- 新总览：`outputs/overview_20261019_contract_weekly_long_v2/index.html`，parent明确绑定上面的reviewed_v2。

机器报告 `20261019_2030_stage067_current_trade_reset_actual_validation.json`，20:31独立核验 **PASS**：

- 160项来源/三个金融版本/parent/新产物文件hash绑定通过。
- 新逐笔HTML去掉唯一新增script后，与原reviewed HTML**逐字节完全一致**。1,558笔records.json的SHA仍为 `47ed5feadc0d8205943238e780866bd1e3f6089168e118ce5c7939692df8dba0`，所有其他原非HTML产物字节均一致，包括精确合约周表、OHLC/MA、闭合交易、风控和独审证据。
- 新旧summary除UI补丁provenance及输出hash/bytes清单外，全部原字段完全相等；HTML内嵌records与冻结cache完全相同。063的全周值/非周块/坐标验证链完整保留。
- 总览v2全部**2,862点**、两张**24行**版本表再次核对；曲线CSV、figure.json、PNG与已验证总览v1**字节相同**，内嵌Plotly data/layout与figure完全相同，唯一页面链接改指新reviewed_v2。
- 两页各**3段JavaScript**均通过bundled Node `--check`。浏览器当前交易切换/3周期Zoom+Reset由根任务继续验收；本机器报告保留 `browser_check=pending_root`，不以fakeDOM测试冒认真实浏览器已通过。

| 产物 | SHA256 |
| --- | --- |
| reviewed_v2/index.html | `92e94f0d7fbb5fd442e6f65760d75f46bd035503e880c58907de609ef2c0bf9e` |
| reviewed_v2/summary.json | `5c2b8000a950e5e05f5e55c9e30a4888cead22fc9fb1e46350261b76b103fb6b` |
| overview_v2/index.html | `0d495b242eeef0dcd6761a86ae303b4eb969f7de599a663cbc2b83dd0e595d36` |
| overview_v2/summary.json | `52a0a142ff1f7ef4711a8218cfca7ce1c14d30aada59902a28f8db3cdbc09674` |
| overview_v2/figure.json | `9a928f048c17f9fca9c75b1f135f660a5e03bb1943b7d0a82ee479577024a67d` |
| overview_v2/equity_drawdown.csv | `022b3daf458e109100624228f63efdfb37ded967201e81449abf95ad4d222e77` |
| overview_v2/equity_drawdown.png | `e1022a20c01c9b83b0f11aaf2e5b449accdb40cc51be7d58a8fcf6167ef5fb1d` |

## 参数、金融结果、反思和后续

金融参数新增/修改/删除：无；金融结果新增/修改/删除：无。期末权益1,205,102.81元、收益20.510281%、DD-17.650750%、Sharpe0.161625、1558完整交易仍只属于原唯一冻结金融源，不因UI修复改变。根任务负责最终整线检查、真实浏览器复现、交付记录及提交推送。

过拟合：本修复否，是与收益无关的多记录Plotly交互纠正；继续价值：是，防止Reset造成空白误导用户判断图形缺失。没有金融再跑、下载、生产/CTP或订单调用。
