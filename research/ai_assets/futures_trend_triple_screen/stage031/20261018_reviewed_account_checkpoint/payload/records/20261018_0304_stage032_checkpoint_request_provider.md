# Stage032必要数据请求通路：C_TS第二次只修导出回放

- line_id：futures_trend_triple_screen；2026-10-18T03:04:01.467357+08:00。
- 唯一维护本线新provider，冻结029不改；只替换docstring和三处作用域常量，request root为outputs/stage031_ordered_account/C_TS/data_wait。SDK、鉴权、completion、价格资格、一次attempt/600秒硬限全不改，fixture不得真实连接。
- 已有OI009与cu2609合格anchor由031直接复用，不重下。仅出现全新真实请求时才启动，当前新增连接/下载/金融0；独立验收后发布pointer，同engine恢复不重放bar。
- 当前不宣称金融成绩/资格；旧028 export失败不可补造。过拟合前后否，纯作用域适配不按收益改规则；继续价值是，为必要缺口保留正确通路。production_qualified=false。
