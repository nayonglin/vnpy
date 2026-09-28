# Stage013B 官方下载协议修正

- 2026-09-06 03:25 CST，本线`futures_trend_xgboost_history_compatible_root_utility`。
- Stage013的94项输入和84份历史ZIP验证、解析完成；202606首次HTTPS GET在443端口连接时出现`Errno65 No route to host`，HTTP状态为空，没有收到行情或拒绝页，未尝试07/08月。原输出完整保留，不改源合同/代码/测试/结果。
- 根因范围是本次HTTPS连接路径不可达，不是已证实的价格缺失或策略失败。库错误文字`Max retries exceeded`不是本工具做了重试；每月GET调用预算1、应用重试0。
- 核对旧成功`source_archives.csv`和当前安装AKShare `futures_daily_bar.py:121`，二者实际都用`http://www.cffex.com.cn/sj/historysj/YYYYMM/zip/YYYYMM.zip`。Stage013擅自改为HTTPS没有证据证明该端口提供同一下载服务。
- 现仅修正传输协议回到已观察到的官方HTTP路径：同一主机、同一路径、同三个月、同请求header/超时/无重定向规则、每月1次。无账号、凭据或个人数据传输；不是更换IP/代理、冒用身份或绕过HTTP权限拒绝。HTTP没有TLS传输认证，原始SHA仅证明取得后内容不变，不夸大来源完整性。
- 新适配器仅绑定原Stage013的解析、选约、收益和覆盖函数，单独`artifacts/stage013b_cffex_root_source_http/`；额外冻结适配器/测试/本修正记录/旧成功URL清单/AKShare源码。科学输入、原始84份数据及新数据的选择规则全部不改。
- 本修正只允许一次有界HTTP重建尝试；失败不得继续改header/协议/接口或重复请求。技术问题可用证据明确修正，但不据此改变收益目标、标签或参数。
- [AKShare官方GitHub日线实现](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_daily_bar.py)支持原HTTP月档案路径；未读标签、未拟合、未回测、reviewer0。
- 反思：不是过拟合，尚无效果数据且只修正与已知工作方式不一致的协议；有价值做这一次排障，继续无限改网络访问方式无价值。
