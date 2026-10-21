# Stage036 两固定条件 episode 单次连接结果

- 2026-10-20 21:25 CST记录，line_id=futures_ai_monthly_pool_generalization；非收益突破。root driver合成与Stage035预审绿后明确通知单次run，未改费用、数量或输入；input mutation0。
- 输入/工具/来源见执行前Stage036协议与outputs/stage036_real_episode_cases/{runner.py,inputs.json,bindings.json,bound_daily_rows.csv}；结果、receipt与summary单独落盘。84个精确日键，4个AM41窗口和guard配置来源、固定Stage014/032 anchor证据全部绑定；driver与6个依赖模块hash记summary。无大文件重读/下载。

## 实际条件结果

两case各1条known路径、60个source-day trace、2腿参考fill，合计120trace/4reference fills。D60仍AU2021-11-02、JM2021-12-30，maturity=True不等于training资格，两者training_eligible=False/complete_monthly_source=False。

- AU：D1 open381.4 qty2；C2先确认，收盘提出long_base_stop；D2 canonical首open377.44平，之后无持仓且无fresh重入。初始风险货币360（signed价差0.18×1000×2），毛额-7920，静态费用40，条件净额-7960，净R=-22.11111111111111。
- JM：D1 open3232 qty2；按current adverse-ties同分钟C2参考3224.5平，D2仅库存不再出腿。风险货币877.2（价差7.31×60×2），毛额-900，静态费用464.868（open232.704+close_today232.164），条件净额-1364.868，净R=-1.55593707250342。

以上均conditional_economics/historical_validated=False，显式extra压力0；qty2仅诊断。AU超1R亏损来自极小初始风险与C2确认后普通收盘请求/次会话执行，保留原负值，不截断、不重定R、不择源。既定两个条件点不能外推正式绩效、收益分布、真实tick或全市场泛化。

## 边界、独审与反思

源真值/历史PIT/真实交易未认证；C2只入场日，普通退出次会话open；没有fresh重入或账户/加仓/heat/margin逻辑，本entryepisode不是旧108训练源。target同native只在已早平条件下有意义，不能取代roll验证。正式策略未改；净60日训练标签0、fit0、订单0、生产修改0。

模型/alpha参数新增修改删除无；金融账户回测权益、总收益、最大回撤、Sharpe、总滑点、真实交易次数、胜率均N/A。此处新增仅两条隔离条件参考账本，不把4reference fills称4笔真实交易。

已通知monthly_driver_review独立agent按Stage035最终复核真实文件、minute/anchor、费用/R、60日时钟和边界；本记录不替代独审。调研判断承接Stage010/021/022官方vn.py/GitHub及冻结源码、Stage014/028/032单来源合同：交易频率、请求时钟、实际执行时钟必须保持分离。

开始/结束新增收益选参过拟合否，固定观察、固定费表/数量、无择优；继续价值是，检出了潜在远超1R亏损与成熟时钟/标签资格分离，后续需先定义完整月度source、多次入场和未知路径合同，不能凭两例立即拟合或升正式。

## Stage035输入校验修复后的同输入重验（21:26 CST）

独审提出NaT/布尔anchorprice/布尔configuredguard的输入校验问题，root补测试先红后绿，通知使用同inputs重验。新输出`revalidated_20261020_212602/{revalidate.py,results.json,summary.json}`。新旧结果对象与字节完全相同，SHA256均`881ce3e87eb358775b7fdb056fc5b8049d61e74283c1a8757f968efe4e0a8805`；首跑7个artifact前后hash不变，首receipt保留旧driverSHA，新summary明确旧/新driverSHA和输入/依赖绑定，不伪称旧首跑用了新代码。

本轮仅增强输入验证，无费用/源/qty/alpha变化。实际执行首跑+重验共2轮，每轮同2case，不增加独立样本数；模型fit仍0。Stage035最终真实文件review已通知审新子目录及历史对应。
