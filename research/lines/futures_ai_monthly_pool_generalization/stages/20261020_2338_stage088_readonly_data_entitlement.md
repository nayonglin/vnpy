# Stage088 行情权限实测与探针更正

- 时间：2026-10-20 23:38（北京时间）；重要突破：否。本阶段是数据能力核验，不是策略回测或模型训练。
- 开始判断：新增收益调参过拟合否，仅核验现有账号和官方接口的真实能力；继续价值是，可避免把“能登录”误当“能批量下载指定历史区间”。
- 调研：[官方下载文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html)、[维护者源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/tools/downloader.py)。指定历史区间下载与标准最新序列是不同接口；权限必须实际登录后读取，不能用构造对象的默认 grants 推断。
- 实测：仅使用仓库现有行情配置，在内存读取凭据并访问官方认证端点；最终 `attempt_network_enabled.json` 于23:38:06完成真实登录，`history_downloader_entitled=False`。没有创建TqApi、连接券商、下单、试用或购买；凭据与令牌未输出。网络升级经自动审核允许，未被拒绝。
- 探索错误保留：初版仓库父目录取错，未触及认证；修路径版本只调用 `init` 而未 `login`，其“authenticated”状态无效，不支持权限结论，详见 `prior_probe_erratum.json`；补上实际login后在默认网络环境出现ConnectionError，单凭异常不能区分具体网络原因；最终网络可用尝试才是有效结论。原脚本与收据均单独保留，没有覆盖历史事实。
- 独立审查：Stage086审查者检查本机SDK的init/login语义及最终真实收据；Stage092另审后续标准序列探针。不能因无下载权限就修改授权检查，也不以TqBacktest导出绕过权限。
- 后续：Stage087固定四合约协议保留；Stage090仅测试官方标准 `get_kline_serial` 的一次最新10000根尾部能否覆盖既定日期。未命中不翻页、不替换样本，资格另审。
- 新增/修改/删除策略参数0；模型fit0；源回放0；生产变更0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。
- 结束判断：新增按成绩择参过拟合否；历史缺失与参考时段偏差仍在。继续数据核验有价值，继续复杂模型救分当前无价值；权限结果本身不是预测力提升证据。

证据目录：`outputs/stage088_readonly_data_entitlement/`。正式0.5R及其生产行为未改；仅本研究训练源按用户既有指令关闭halfR及耦合retry，C2保留。
