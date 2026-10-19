# Stage091 0.25%风险下的原exact-contract周门

时间：2026-10-20 01:43。仅新增 `tools/stage091_quarter_weekly.py`，从冻结075复制，文本白名单只改变风险基础导入为090；其余周线信号/成交校验、long授权、原日期/相位/身份和拒绝行为逐字一致。

enabled臂仍只对所有真实long OPEN检查当前交易合约自身至少40根有效已完成周K，严格MA5>10>20>40；short/CLOSE/env_probe不加门。signal_close可用已完成当周，实际open只用严格早于填单日完成周，缺/坏周failclosed，不借主力连续或其他合约补历史。058 provider、原始行情和完整交易日历不改。disabled臂不将本模块的weekly strategy或execution mixin放入MRO，不构造/query/export provider。

新增/删除/修改经济参数无；只承接090的0.0025风险政策。类身份在091定义，字段仍用 `stage059_*` 兼容审计。两最终MRO真实long/short、flat/reverse/rollover sizing、旧单重挂和provider poison验证已通过，short/env_probe不触周线。反手当前原生禁用时不因周门重新开通；周门不能复活native已拒绝量。

源码SHA256：`f62474b4d21b1b0d0b19f48967ca6a7e353db6ef6f134bfde25d150bd0a6f983`。文本白名单及完整513项回归通过。没有金融运行和新增业绩，所有金融统计不适用。不是为弱窗口调参，有价值作为同风险配对臂；下一步独立预审后由Root运行，不改旧模块/LINE/Git/生产。
