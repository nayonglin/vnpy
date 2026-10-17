# Stage029：仅为真实C_TS等待请求提供同一已验分钟下载通路

- line_id：futures_trend_triple_screen；2026-10-18T02:43:07.650005+08:00。
- 原023冻结工具不改，新029仅复制后修改docstring、OUTPUT、REQUEST_ROOT、PROTOCOL四处绑定；原source SHA 6d056953e6e200435b3c75a02ca7922883db9402b2bbb1c72b242f296adeff34。
- 只认outputs/stage028_ordered_account/C_TS/data_wait/request_<canonicalSHA>/request.json及实际文件SHA，不接受fixture作真实provider请求；SDK/鉴权/endpoint/600秒硬限/原completion和逐日价格资格全沿原规则。
- 不因准备工具而联网；仅金融engine实际请求时取对应精确分钟，原request与worker各唯一attempt，外部独立agent验收并签delivery receipt后才给同一等待engine response。
- 不使用日线价替代、不重启金融、不自动重试、无broker/CTP/订单。不改原数据或宣称策略收益。
- 过拟合前后否，纯数据通路不按收益选参；继续价值是，避免实际必要缺口出现时破坏回放连续性。金融新增0、下载新增0、模型新增0，production_qualified=false。
