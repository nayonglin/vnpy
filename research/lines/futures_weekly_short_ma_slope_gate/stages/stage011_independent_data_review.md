# Stage011 独立数据、对照与运行时入场审查

- 时间：2026-10-30T17:10+08:00。所属线：futures_weekly_short_ma_slope_gate。
- 结论：PASS_DATA_BASELINE_RUNTIME_WITH_LIMITATIONS；P0/P1/P2=0/0/0，仅数据/对照/依赖入场，Stage011源码冻结与真实canary仍须分别审查。
- 三份指定冻结证据SHA全部相符；对照为Stage009实际补资46run，不是Stage008闲置备用对照；23起点、截止2026-10-29、交易15万+场外备用15万一致。
- 四份数据SHA和原19品种10/29映射与正量真实日线全部通过，未包含10/30形成中数据；SQLite quick_check通过，共1,345,757行。
- 按运行入口实际vendor路径导入vnpy、vnpy_sqlite、portfolio、pandas/numpy/matplotlib/TA-Lib成功；解释器为仓库.py311/bin/python的实际符号链接目标。
- 独立去重校验4,238文件、5,159,557,464字节，共166,755条检查。后续只允许精确device/inode/size/mtime/ctime命中已实读SHA缓存；新金融输出仍独立实读和会计复算。
- 独审attempt001缺ROOT导入路径，依赖导入失败，日志保留；修复后attempt002通过。该错误发生在独审工具，没有金融运行或金融参数修改。
- 原source/PIT、2014预热、18项结构缺口、生命周期、零手续费、静态保证金×1.65和无盘口容量限制全部继承，缺失/已知零量不能伪造K线。
- 外部调研沿已固定设计中的CME OI说明和Backtrader官方PercentSizer；资料说明OI是确认和仓位整数化路径，不能证明6%优于1.8%。本次独审不新增阈值或金融假设。
- 运行前过拟合风险：有，同历史多次查看且起点重叠；固定三风险参数回归普通档、完整23网格且不救参，可限制新增自由度。继续价值：有，可证伪高风险档是否只是杠杆效应。
- 金融回放0，行情下载0，生产访问0；NO_PROMOTION。

JSON证据：`stage011_independent_data_review.json`，SHA256 `59c6db4d4dfcba3cbf8cf9a20fcba1ce3ac40ece2e91e2c9d9d461df866000d8`。
