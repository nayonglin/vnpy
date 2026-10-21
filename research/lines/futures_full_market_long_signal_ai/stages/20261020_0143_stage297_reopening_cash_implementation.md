# Stage297：新增q候选现金薄适配器就绪（未实际运行）

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:43 CST；root实现，沿当前分支，不改旧源/内核/正式。
- 精确复用286接受的四本预算、全selectedID一次129流读、157→131、native缓存/旧157控制和loggrowth统计，仅切294/296/newcandidate身份。去掉WASDE更正时钟资格字段；held状态由296单独评估，不保留单Corn硬编码false。不增加alpha/风险/止损/成本参数。
- 按test-driven-development先写唯一新增身份适配边界：新模块未实现时清楚FAIL；实现后1/1通过0.231秒，未调用kernel/数据/actual。此测试确认294新身份可接受、旧284身份拒绝且不创建现金输出；没有重跑286旧suite。随后只校正started stage号/错误信息元数据，不改金融逻辑。
- 源/fixture小SHA绑定和root授权模板见outputs/stage297_reopening_offset_cash/implementation/authorization.template.json；296完成后root填唯一manifest并授权。当前0actual/fit/cash/SQL/native读取，累计441/238。
- 本轮新增调参过拟合否，长期历史择题风险有。四本新候选仅在动作/执行输入有差异时有价值；与基准完全相同则独审等价后跳过。名义现金门与held非害只是必要研究支持，不等于PIT/真实成交/alpha/极窄损加注资格。
