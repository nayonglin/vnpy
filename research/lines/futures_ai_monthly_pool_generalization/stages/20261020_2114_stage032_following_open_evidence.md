# Stage032 后续普通退出 session 首 open 定向证据

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:14 CST；非重要突破。
- 从 Stage011 清单、Stage014 逐来源合同和 Stage028 两固定观察继续。只读10个已定位 AU/JM 小缓存，每文件一次 OHLC 投影，保留内部 minute_source；大 Stage861 扫描0，不新扫磁盘、不下载。源 stat 不变、小文件全SHA及投影SHA绑定齐全。
- AU@2021-07-30→2021-08-03：Stage461 单文件555/555，session首2021-08-02 21:00，open377.44，日OHLC377.44/380.10/377.32/377.82全吻合。可连接普通退出的条件参考 anchor；未实际成交、未记费/收益。
- JM@2021-09-30→2021-10-11：Stage491 单文件345/345，首2021-10-08 21:00，open3145，日OHLC3145/3428/3143/3409吻合。JM入场C2参考已flat，后续日仅库存，不产生实际第二退出。
- 冲突与未知保留：JM Stage448全grid但日H/L/C不符；AU Stage504/506只有346/555且日H/L/C不符；其他无目标行。不拼源、不定provider优先级、不修clean日线。一个吻合单来源不能证明源真值、tick顺序、成交、生产资格或转授入场C2资格。
- 工具与证据：`outputs/stage032_following_open_evidence/{inventory.py,summary.json,README.md,source_audit.csv,projections/}`。当前helper的硬编码表未扩展，历时不外推到全市场；Stage006静态费用历史PIT仍未认证。
- 模型/alpha参数新增、修改、删除均无；halfR/retry仅训练源关闭、C2保留、正式未改。新增金融回测结果无；权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A（未运行金融回测）。fit/下载/订单/生产修改0。
- 调研和判断：继承Stage010官方vn.py/GitHub与Stage014/028绑定源码合同；自然日分钟命中不能代表下一session首open，按原helper日历和单来源独立聚合才足以提供条件参考证据。
- 开始/结束新增收益选参过拟合否，无收益择源/扫参；固定两案例存在条件选择范围，不能宣称泛化。继续价值是，AU pending request 的首open可供后续成交/费用组件连接，JM防止重复平仓；完整60日标签仍未生成。独立review由root另行安排，本记录不代替独审。
