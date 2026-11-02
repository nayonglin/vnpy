# Stage027 R6真实资格尝试独立复核

工程部分完整通过：96套件2408测试，0失败/错误/跳过，96份exit均0。288份XML/output/exit原字节归档与193个唯一对象SHA/bytes核对通过，observer errors为0。当前R6及690项资格源闭包保持同字节。

真实连接部分失败，NOT QUALIFIED。首次Stage907/174实际只读已调用，但TD/MD连接、认证和登录均未得到确认，所有查询回调0、broker trading day空。position_query_not_available只能记实际仓位UNKNOWN，不能当空仓；账户现金同样UNKNOWN。8项实际报单/撤单/native变更尝试及调用计数严格0，firewall证据完整。

Stage174状态readonly_logs_without_ctp_progress，Stage907 blocked且快照证据不全；可信构建器在release_builder_production_readonly_raw_capture_invalid拒绝，未形成qualification文件，不得激活/接管或作为已合格安装。首次失败后无第二份完成capture。12份实际失败原件与归档SHA/bytes一致，stdout/file规范摘要绑定一致。

正式env选择、framework搜索优先级、两真实Dyld image，以及Python/扩展/framework二进制SHA核对一致；missing_env为空仅代表字段存在，不能证明凭证有效或已认证。TD/MD补充TCP5秒均Timeout，仅支持可达性未建立，不能单独定位路由、服务窗口或前置健康。记录不包含原账号、地址、余额或实际仓位。

本次独审接受的是工程通过及真实失败证据的准确分类，不是生产资格。m4/m5旧失败保留；晚间接续必须新exact-R6 trusted run，生成自身完整测试与两份真实快照，不能升级本批或拼接旧证据。审查者未连接CTP/TCP/SMTP、未金融回放、未交易/撤单或修改生产/Git。

过拟合：否，只有工程/连接证据审查；继续有价值：是，按已授权单次晚间接续重新验证真实就绪并保留失败。
