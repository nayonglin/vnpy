# Stage028实施分工

来源：同分钟`stage028_conditional_execution_contract.md`，用户授权持续离线自主实施。

1. 独立agent实现`tools/stage028_ordered_strategy.py`及必要真实hook测试，只写该模块/测试和唯一receipt；root提供接口，Stage027状态/缓存不变。
2. 独立agent实现`tools/stage028_ordered_engine.py`及必要真实hook测试，只写该模块/测试和唯一receipt；factory接收base engine与资格callable，复用真实827队列/_fill_order，不改正式源。
3. root编写新C_TS runner，复用022已接受的runtime/stack/capture helpers但新scope/provenance/output；Stage021 scope返回gate可用于独立intent stub的full资格，不需修改021。
4. 两模块测试按各自必要行为RED/GREEN，接合后用一个账户/未来数据sentinel组合场景补接口证据；独立审查无重要缺项后才跑一次C_TS全周期。
5. C_TS金融完成后由新独立agent审查，记录完整正负结果，决定B_TS及稳健性下一步；不重复A0或已通过的数据构建。
6. Stage025—028决策资产按角色登记，中文记录与LINE由root整理，不改用户脏registry、不推送/部署。
