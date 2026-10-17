# Stage072：已接受等待数据增量层的有限独立复审

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 06:03 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`；同分支，无 worktree。
- 独立 reviewer：`accepted_delta_review`；不是重要突破，不触发 alpha/A/B。
- 范围：Stage061 spec、Stage068 root ruling、Stage069 实现与证据；仅新 freeze/loader/权限组合和三个新增合同测试。
- 结论：**P0=0，P1=1，P2=0；本版本暂不通过，真实 190 包 freeze 继续阻塞，交原作者修复。**

## 调研与判断

本次遵守 root 明确限定的无网络代码复审边界，未重新网上/GitHub调研；只读本地原021、022、036和063/064终态证据。已读 AGENTS 与 registry；当前 registry 未含本线条目，沿 root 指定的既有研究线目录完成唯一 Stage，不修改 registry/LINE。成功金融终态明确 unsupported、缺失顶层 run_id/context SHA以真实 failure和同owner context绑定，均是 root 批准的有界适配，不列为scope问题。

实际只读核对的063/064身份：
- failure SHA：`f39f9d60b3e975263b0ee9411b70b766a9a8c4a3f12d068b9c35650888928536`。
- terminal SHA：`8f556fb6b76c27f28db7ff7799643bda5c7e934c844a29546545efe10d21981b`。
- 064 receipt SHA：`916edbc472fb49dcb9e1fbcde396b0b555a82b1468622b1db526a98c1bee9963`。

判断：原B失败不使此前独立accepted且实际commit的前缀失效，但191个pointer不能当190个gate commit。元数据选集确为190；失败末包`6873f0…3730`排除。仅解析第一条真实已accepted delivery：225个键、full225/anchor0，audit与gate一致；31项source身份与owner吻合。没有重hash190包或读部分PnL。

## P1-001：SHA校验与实际消费字节之间存在替换窗口

位置：`tools/stage061_accepted_wait_delta.py:332-337`，相关`_bind:42-56`及`load:341-352`。

loader先对artifact路径调用`_bind`哈希，随后按同一路径重新`read_csv`。有限临时fixture中，原manifest/review及所有pin保持不变；在overlay的SHA校验后把符号链接短暂切向同键、open=10.25的CSV，解析后恢复open=10的原文件。loader成功返回open=10.25，最终artifact SHA仍匹配pin，真实`runtime.InputRecorder({}).verify()`亦通过。

这说明被消费价格没有与签署SHA绑定，会破坏本层最核心的七值和来源闭包。修复应将文件一次性读为bytes，对同一bytes验SHA并解析JSON/CSV，覆盖manifest、review、snapshot/deliveries和CSV等实际消费对象；仅加末次hash或仅拒绝symlink仍可能漏普通文件切换/恢复。由root安排原作者一次性修，不在review中改实现。

## 实际验证

1. `.py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage061_accepted_wait_delta.py -v`：exit0，3 tests，0 failure/error，约0.124秒。
2. 有限临时fixture反例脚本：exit0，静态rights篡改被`source_hash_changed`拒绝；注入manifest最后写失败后final输出不存在、temporary残留0；上述symlink窗口被成功复现，属审查发现，非资格通过。
3. 真实只读schema脚本：exit0，191 resolver/190匹配commit/1 failed；同owner context一致；仅调用一次021 parser。

完整实际命令、exit、输出及SHA在`outputs/stage072_wait_delta_independent_review/evidence.json`。原三个测试有效覆盖non859新anchor不误升full、真实full精确网格、旧七值逐项冲突、同值保留source、双记录选择与来源漂移；本次未发现这些逻辑中的另一个P0/P1。

## 审查身份与限界

- 实现SHA：`3f3cf7dfca8af51226271a3db4ea56927c6e8909f9a77ff262a1ea9d30a50e85`。
- 测试SHA：`fa0fde4ca859e1a921ec30b4d36bf6eac9678bdc475873c6f473626c282a928c`。
- Stage069 implementation evidence SHA：`d6a4c9980613e26f5dd0660e737ed3a73d6f1d2d4817595b87e8d2203eb69554`。
- 本次只写本Stage与`outputs/stage072_wait_delta_independent_review/{evidence,review_receipt}.json`，不改作者代码，不stage/commit/push，不自行派reviewer。
- 本receipt仅是代码审查，不是Stage061数据集资格receipt；真实manifest未生成，不能用来授权下一runner。
- 原058模型历史PIT两项P1与066旧source859问题独立保留；未重审旧022/016价格或原两个anchor。

## 参数、金融结果与反思

新增/修改/删除策略参数和金融结果均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。真实数据freeze、金融回放、模型load/fit/predict、网络、订单均0；`production_qualified=false`。

开始及结束过拟合判断：**否**，本次是按预定数据合同查身份、七值、权限与原子性，不看收益、不搜策略参数。开始及结束继续价值判断：**是**，有限反例已经发现能绕过SHA的真实消费窗口，应在复用190包之前修闭。下一步由原作者修P1-001，root安排针对同一反例及三个新增tests的有限复核，再决定真实freeze。

