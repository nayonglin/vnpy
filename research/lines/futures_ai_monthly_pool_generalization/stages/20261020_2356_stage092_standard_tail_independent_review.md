# Stage092 标准serial尾部独立预审及实际数据审计

- line_id：futures_ai_monthly_pool_generalization
- 时间：2026-10-20 23:56 CST
- 类型：独立只读输入审计；非回测、非重要突破、非正式候选、未触发A/B。

## 调研与判断

[天勤官方API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及本机3.10.2源码支持标准serial最新尾部最多10000，与专业任意区间下载不同，SDK仍自行检查行情权限。当前API命名不是任意历史权限证明。

预审发现3个P2：真实087 plan键错误、实际SDK FloatBlock与integer-only投影不匹配、一次性TimeoutError可能被逐请求捕获吞掉。作者分别先红后绿修复；26项独立预审及作者7测试独立运行通过，之后才GO固定4次取数。审核者未认证、未读取本地凭证/env值、未创建SDK真实API。

## 实际数据与逻辑

- 独立检查4×10000完整raw/projection：922818逐行字段检查0失败、0剩余P0/P1/P2。
- 0padding；原float raw完整保留，规范化仅宣称minute lattice；时间/id/全部OHLC/量/OI未丢改，symbol/duration一致。
- 服务器完整native/所/交割年月/expired/expiry与冻结epoch metadata全部匹配。CF005明确对应202005，未只按短码推年代。
- 固定目标CF/JM/LC分别0分钟，保留未覆盖，不追加请求/替换样本。AU完整555参考grid且OHLC/open通过055；逐555分钟4OHLC float64 bits与Stage089 AU小快照完全一致，为重复输入而非新路径。
- 本轮新增唯一输入0、模型拟合0、源回放0、标签0。旧119manifest/4767source/1374labels SHA重验未变。没有physical/PIT/broker/production认证。

## 变更及指标

只新增自己的[Stage092审核资产](../outputs/stage092_independent_tail_probe_review/README.md)及本唯一stage；没有改090作者脚本/旧数据/正式/LINE/registry。参数无变。没有新增/修改/删除回测结果；权益/收益/最大回撤/Sharpe/滑点/交易数/胜率不适用。

## 开始/结束反思

均判断没有新增调参过拟合：四请求冻结一次，不读收益、不成功换样本、不fit。继续的价值有限：验证合法尾部和旧AU一致性有价值，但本次未新增唯一数据，不能推销为793窗口普遍可补。接下来保持真实缺口与完整N，独立来源证据需独立通过资格后才谈注入，不因下载路径成功改变NO_PROMOTION。
