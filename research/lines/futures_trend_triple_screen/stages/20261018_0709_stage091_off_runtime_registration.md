# Stage091：共同OFF账户与有界数据通路复现冻结

- line_id：`futures_trend_triple_screen`；记录：2026-10-18 07:09 CST；root。
- 分支`codex/ai-training-data-expansion`，同checkout、无worktree；登记时HEAD `e59055face49e2eda17bfcdd11d834905b987c42`。保留用户其他线与registry脏改。
- 本轮分类：**progress**。084实际接线、089独立接受，087实施/090反证/093一波修复/094定向接受均有真实文件及有限执行证据；不把它们计作账户回测。
- 是否重要突破：否，仅是取得公平完整账本的必要接合；收益更高且回撤更低目标未达成。

## 调研与取舍

沿086已核对的Backtrader官方执行说明、LEAN原始fill源码和埃尔德三重滤网原始说明：方向许可、回调准备、随后触发须分别实现；不利跳空如实用实际fill，不以事后成交价反改u已冻结q。本轮不增加alpha或指标扫描。旧pairwise19的057/058历史训练时点限制仍保留，月度AI池是另一个继承链，不能因关闭pairwise就声称全体系严格OOS。

## 已接受边界

- 084 runner `d83b4cc20c09e07e9bcecfd541ba223fbf602db194430e6ed307a80e5e25ed09`；089 receipt `55b72c489dfcc282aaa4c3122e2e9d74215fa243d1242265461d6a5c887015ab`，P0/P1=0/0；保留非阻塞失败取证P2，不追加修补。
- 087原源和090失败P1=2完整保留，未覆写为通过。093只修owner内部身份/原始时钟和公开parent启动前余量门；新增两回归RED/GREEN各一次，原三测不重跑。
- 最终scope `5919f098af14ea9819cee3445e2555f9a740ebc2c808af1afdafa508235d01fb`，provider `33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46`；094 receipt `48bc517989da434e22db70fbb7d603ff09c7f52581f67c868cb0ca736aae2684`，剩余P0/P1/P2=0/0/0。094只定向关闭090两项，继承其余有限验证，不冒称重跑原三测。
- 正式八项共同OFF、月AI10+fu、0.5R/retry、150000本金、2020-01-01—2026-10-14、原成本和1800/7200限额不变。每批最多4连接含daily、840启动余量、570/600父子限额不变。071外层统一隔离、061先等值合并及021旧重叠七值门保持。

## 实际复现资产登记

实际命令：`.py311/bin/python /tmp/register_triple_off_runtime_20261018.py`；工具chunk `e92967`，真实exit0、0.109625333秒。此命令只登记/精确暂存本地复现材料，不是数据provider或金融进程。

- 目录：`/Users/mac/Desktop/fian/research/ai_assets/futures_trend_triple_screen/stage091/20261018_pairwise_off_runtime`。
- 资产：101项payload及manifest；manifest internal SHA `aa9770302433cbae17b1d3a963037c7ca24be8d7c1bc3fc0bed08c4f379d47b3`；逐资产归档bytes SHA全部核对一致。
- 保存当前五项源码/测试、084—090和093—094记录/证据、旧08716对象和090原反例、精确修复diff。原始行情、DB、pickle市场缓存及私有配置均未入归档；旧190包数据资格继续用083，不重复登记原始overlay。
- 登记后还需将本次选定源码/记录与LINE精确加入同一本地Git检查点，不包含其他研究线或registry改动；本文件不预称commit成功，不推送/部署。

## 参数、成绩和下一步

新增/修改/删除可调alpha参数：0；新增/修改/删除完整回测成绩：0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。累计金融8attempt/3 accepted、训练0、当前新金融/provider/网络0，production_qualified=false。

下一步：真实两臂preflight各一次取得实际来源闭包；root据真实089/094、原失败终态和固定数据签readiness，再仅启动各attempt1。真实PID/context出现后才签owner并响应真实缺口。095独立会计适配并行准备，实际每臂工具终态后再独立复算；A0受限反事实与原B失败N/A必须和新两臂同时披露，不能只胜弱A_OFF称目标完成。

开始/结束新增过拟合判断：**否**，本轮没有用PnL选择参数；既有选择偏差限制未被撤销。继续价值：**是**，已完成必要接合，应进入真实预检和账户结果，停止继续扩大工程审查。
