# Stage086 下载工具/SDK时钟独立只读审计

- line_id：futures_ai_monthly_pool_generalization
- 时间：2026-10-20 23:43 CST
- 模式：输入管线独立审计，不是回测或新alpha；不是重要突破/正式候选，不触发A/B。
- 起点：Stage085收束4767条件点值、1374 robust、NO_PROMOTION；下一批793精确需求/1926首C2窗口。

## 外部调研与判断

已交叉查看[天勤官方下载器](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html)、[官方回测语义](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html)、[官方GitHub时间函数](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/datetime.py)及回测源码。文档3.10.3与本机3.10.2不同，实际源码SHA另行锁定。

判断：旧提取器本身足以造成部分缺夜盘/OHLC冲突。859/900新datetime仅保存last[-1]第一次值，保存形成bar开盘快照，随后同datetime完整CLOSE不会覆盖。自然日午夜窗口及date过滤又裁掉前晚。491调用459已改[-2]，但终端bar无下一实际交易bar时可漏存；15:10结束、14:58 cache门槛均不足以证明会话完整。UTC→北京时间转换本身正确。

## 证据

- 19项离线断言全部通过：真实859函数AST隔离+内存OPEN/CLOSE复现错误快照；真实459函数复现终端14:59漏存及下一实际OPEN后可存；真实900函数将周一555参考grid裁为225；本机SDK date/datetime/UTC等价及auth懒认证边界。
- 固定doc7去重8小缓存27,853行，27,849行O=H=L=C且volume0。指纹与缺陷高度一致，不是所有文件历史因果认证，不能据此修造HLC或删除所有平价bar。
- 只读Stage088实际login收据：authenticated、tq_dl=false。init-only空grants的早期false无许可含义；本阶段没有认证、读取设置/env值或市场下载。
- 详情、逐文件SHA、反例、接口：[Stage086输出](../outputs/stage086_download_clock_audit/README.md)。SDK结束前2038哨兵不能当真实完成水位。

## 变更及参数

仅新增本目录审计脚本/19检查/小样本指纹/最小readonly adapter设计合同及本stage。没有修改旧下载器、模型、参数、费用、source、半R/retry/C2、LINE或registry。没有新增/修改/删除回测结果；权益/收益/回撤/Sharpe/滑点/交易数/胜率不适用。新拟合0，新下载0，新标签0；原4767/1374保留，不因管线诊断晋级。

## 过拟合与价值

开始及结束均判断无新增收益调参过拟合：固定样本、不读收益、不挑成功窗口。继续有价值：补真实数据前必须保证完整交易时段和已收盘值，防止重复制造缺口。下一步只允许独立版本实现合同反例后受控取数/独审，不保证取得所有需求或改善泛化结果；无权限不购买/试用/绕过。
