# Stage046：原037数据provider独立reader作用域适配

- line_id：futures_trend_triple_screen；时间：2026-10-18T04:13:46.409407+08:00；非重要策略突破。
- 仅从已独立验收043来源派生037的作用域reader，供actual request全部日线已有原CSV/013批准资格时复用；新daily需041/043，不允许把已批准日线重签覆盖。
- 原043 SHA373493d9eb50647063044e53c2c669584f237345cf2a8edf8f5d0d282c1b1d54保持immutable；新reader源显式固定037 SHA19c9a83e83f2d69b70446cd49a8c84201c44e65a4f20380b0aaa8698ca2786d1。只变LINE位置、provider import/pin、独立输出/审者标识和本协议绑定，所有精确request/真实terminal/单attempt/分钟合法完成/grid/7值daily/旧key/A0/Stage021 parse核心不变。
- 仍只支持已存在actual request、全部完整packet、physical existing0；anchor只给anchor权利，multi packet需全部到齐。源来源由root显式pin、由044调用真实观察子进程后提供terminal SHA，不从文件存在推断终态。
- 不网络、不启动engine、不写response、不修改原数据/策略。源/协议一旦被实际receipt引用即全程immutable。root实现此作用域副本，不冒称是对原源全新独立金融复核；043独立算法继承，其他agent另审本范围。
- 验证限定：源diff、核心函数AST相等、CLI import/help与错误provider根路径拒绝；不重跑旧fixture/金融/大源栈。
- 策略参数/金融结果新增修改删除均0，期末权益/收益/回撤/Sharpe/滑点/交易数/胜率=N/A。开始过拟合否（只执行数据合同）、继续价值是（减少重复provider副本和人工等待）；actual调用结果另记。production_qualified=false。
