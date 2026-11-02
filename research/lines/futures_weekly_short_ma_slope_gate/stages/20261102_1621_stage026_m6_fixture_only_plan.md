# Stage026 m6仅修私有umask下的负例夹具

记录时间：2026-11-02T16:21:25.110323+08:00。本线futures_weekly_short_ma_slope_gate；无金融回测，不是alpha突破。

m5可信资格完整跑96套件，2408项仅1失败，未到native；旁路观察本次实际保留96×3=288原文件版本、0归档错误，原周报错误已可核。测试请求mkdir0755在私有umask077下实际为0700，因此产品正确接受安全目录而断言误报。不得降生产umask或改安全guard来过绿。

本次仅tests/test_weekly19_friday_report.py加p.chmod0755一行，所有原断言保留。作者完整24项在077/022各过一遍，独审原R5 fixture077红/022绿，修夹具后两mask全绿；297其余critical和全部生产源码不变。源码窄范围接受，m4原始trace丢失与m5已捕获原错误明确区分；旧失败不改名通过。

流程：冻结新source与m6→fresh clone/正式独立source review→精确R6可信资格实际重跑全部96套件和2次正式只读。该轮真实aggregate作为本版本完整CI，不为仅测试一行再额外重复全局CI；未运行前不能称R6通过。成功后继续原授权activate/master/remote clone/canonical stable资格/Stage948，失败保留原因。

没有改策略、19池、空头底20%、风险、资金、备用金、邮件节奏、实际持仓或44线。CURRENT/master/stable/生产未变。过拟合：否，修实际被测文件权限而非金融阈值；继续价值：有，完整独立资格必须可重复且数据安全要求不退让。
