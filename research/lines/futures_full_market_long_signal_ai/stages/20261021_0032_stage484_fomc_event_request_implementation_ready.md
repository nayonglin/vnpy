# Stage484：FOMC公告前精确请求构造器已准备，仅合成数据验证

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 00:32 CST。
- 当前模式：Stage483固定协议下的纯元数据实现与合成验证；非重要突破；不触发策略A/B。
- 研究线：已先读取`research/registry.md`确认本线；本子任务只写本线工具、唯一stage及本线outputs，不更新LINE/registry/根总账。
- 本阶段真实源内容读取0，真实actual未启动；由root按唯一CLI执行一次，再独立审查。

## 外部调研与判断

复用Stage483已固定的作者main/mypc、BoE1114边界及Stage480两个Fed官方夏冬锚点；本实现任务不新增网络请求。两个固定锚支持以America/New_York解释start的条件假设，不能推广为385事件逐行时区证明。UTC+25小时是已知测量窗的保守结束约束，不是首发PIT/供应商接收证明。上海15:15和冻结源日历映射均为研究重建，不声称当年未来交易日历已公布。

独立pre-review提醒已落实：有限日历两端不夹取、不环绕；deadline早于首cutoff时输出`before_source_calendar`且u/D均空。原早期事件不会因研究起点恰等于日历起点而被伪造为首日可决策。

## 本次变更

新增单文件`tools/stage484_fomc_event_requests.py`（23,358B），SHA256：
`46b8d8f75f3bc3ac0dca993203aa7fa0cf9bad13e3330296c4da30050365b2f5`。

新增仅四项检查`tools/test_stage484_fomc_event_requests.py`（5,200B），SHA256：
`8755c4e8eff63cd9e3ac882ccdce7d1cb4c831ed8f1194f2d929576a1e843fd1`。

合成fixture `outputs/stage484_fomc_event_requests/tiny_fixture.json`（3,164B），SHA256：
`3d33524eb34b740979346e7ccaa978a24245cf88fcd09417d624a9d630854902`。

CLI仅`--protocol --protocol-sha256 --output`，输出目录必须不存在；终态记录`auto_retry=false`。无生产代码导入、网络、native、SQL、Y/exit、COMMON/score、fit或cash。策略/训练/资金/止损参数新增、修改、删除均0；新增CLI技术参数3个；不改既有脚本。

实际接口绑定Stage483的12个action metadata字段、7个母字段。227 metadata一个完整窄列流，470母一个完整窄列读，calendar/FOMC各一次；大源SHA继承，前后device/inode/size/mtime/ctime一致性闸门，不重hash大源。整数日历按YYYYMMDD解码。全原始母/子、全产品/family roster及母子计数有独立解析digest，即使仅展开事件u子集也不缩小总量身份。

每个源事件保留ordinal+原timestamp身份、原Event空值和完整时钟状态；只按u是否落study决定展开资格。每eligible event-u展开全98母，保留nochild；该u所有子行动保留资格0、ordinary/F及未观测pre状态。`pre_observed_any_epoch`只按全metadata中的精确(epoch,pre_date)匹配，独立于未来路径/标签，且只披露不筛。raw键只按(epoch,pre_date)去重，子请求保留全部事件/父母/原序号链接和request ID。D取u的实际下一源日，无D状态仍保留；不声称会成交。

## 新检查和真正结果

只运行本阶段四项合成检查，未运行旧suite。实现创建前记录4项`FileNotFoundError`，如实保存在`tiny_red.txt`，不把它称为行为断言失败。实现后真正运行：4 tests，0.191秒，OK；完整输出保存在`tiny_green.txt`。

四项检查覆盖：

1. 2025-06-18和2025-12-10两个独立夏冬锚及elapsed UTC+25小时，夏冬公告分别18:00/19:00 UTC，deadline分别次日19:00/20:00 UTC。
2. 同日不同时间事件以原ordinal各自保留，缺Event仍保留。
3. 整数YYYYMMDD解码；study=calendar首日时早事件不夹取首u；u_before_study、尾端无未来D和calendar之后无u均不环绕。
4. tiny全roster、nochild、pre缺支持、eligible0、ordinary/F和唯一键链接守恒。

另一次全合成CLI已真正完成，输出`tiny_cli_run1/terminal.json`为completed：完整9母/5原子，2事件展开6母/6子，2唯一键；nochild母2、pre无支持子2、eligible0子4全部保留。4源各一次尝试/完成读取，前后stat一致，0fit/0cash/0网络。合成CLI用tiny_protocol SHA`baa4b4bda0aba104ec7a96eec6f65fd66c99631438ca43be07c99a1509fe8638`，不代表真实483源验收。

所有新输出SHA及source/fixture绑定见`outputs/stage484_fomc_event_requests/implementation_binding.json`；合成CLI自身manifest包含八输出中的前六文件SHA，terminal绑定manifest，准备绑定再覆盖terminal SHA，避免自指。

## root唯一建议actual CLI

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage484_fomc_event_requests.py \
  --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage483_fomc_request_protocol/protocol.json \
  --protocol-sha256 b1d88000c22701a029a1735f80ecdba64bd91801ec035a4d93a83d285066d4ed \
  --output research/lines/futures_full_market_long_signal_ai/outputs/stage484_fomc_event_requests/actual_run1
```

只建议一次；本子任务没有执行。若source stat或任何全身份、顺序、calendar、母子链接闸门失败，保持failed，不自动重试，不删行或补日期后重跑。

## 结论与反思

本阶段只证明实现经过新合成检查与小CLI路径验证；不证明真实385事件请求投影完成、不认证市场源字段价格、首发PIT、FF4经济正号、训练就绪、alpha或账户收益。金融八指标、回测区间/账户/成本均N/A；新增回测结果0，累计481fit/258cash及1旧partial保持。

开始/结束新增按收益调参过拟合：否，没有收益、标签、模型或参数选择。长期历史择题风险：是，仍需保持固定协议和一次执行纪律。继续一次真实必要请求投影的价值：有条件是，它能把所需原始字段身份具体化，并显式保留缺支持；重复扫描同源或把请求工程当alpha没有价值。

下一步由root核对source绑定后一次actual、再派独立新结果审查；本子任务不启动actual，不worktree/commit，不更新正式版本/生产/CTP/邮件/调度。原全市场目标active未完成，原四前瞻保持。
