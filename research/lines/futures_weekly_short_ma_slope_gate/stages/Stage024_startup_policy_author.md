# Stage024 私有启动政策边界：独立测试作者记录

- 时间：2026-11-02（北京时间）。所属线：futures_weekly_short_ma_slope_gate。
- root委派范围仅新增`tests/test_weekly19_startup_policy.py`；startup module、backend、pipeline、runtime及政策源码均由root/其他owner修改，本作者没有代改。
- 全部为合成fundsbroker envelope、临时0700目录与0600文件，没有读取或操作真实资金、凭证、CTP、SMTP、委托、转资或生产。测试不授予来源或生产资格。

## 合同与测试覆盖

只测试`load_startup_authorization(config)`及`assert_startup_snapshot(policy,snapshot,*,account_key,material_release_id,now)`的安全边界，不镜像逐行实现，不调用carry-in builder或实际broker。

- exact默认返回None；不能在默认mode偷偷附加授权ref。
- 显式mode下，账号/release/cold-start与历史completed day准确绑定；scope必须固定，operator来源明确。
- 两层私有policy/metadata ref按原始bytes SHA核验；改内容、改digest、relative/symlink/hardlink、文件或父目录权限不正确均拒绝。
- 不支持mode、扩范围、bool/非正授权手数、重复合约、非operator声明、metadata非零API计数拒绝。
- 同源fresh完整快照正例通过，但不生成source_qualified/production_qualified或任何委托授权。
- 数量/方向变化、未知附加仓、缺仓、重复仓、active/unknown订单拒绝；已完成/撤销/拒绝订单仅允许完成校验，不代表send许可。
- 原始account、positions、orders分别核账号/release/trading day/query generation/profile、freshness、last/error/complete等；混入foreign/stale/incomplete envelope不能借有效account蒙混。
- 关键反例：授权整数1手，snapshot手数True或1.0在Python相等比较下可被误认。公开snapshot guard也须严格`type(volume) is int`且正，不能只靠字典相等。实际provider另有原始来源/整数校验，因此没有将这个纯helper反例宣称为整条source门已被绕过。

## 实际验证历史

1. 初查指出原snapshot helper仅_parse positions/orders而未绑定其各自query身份/新鲜度，以及mode列表形状会抛TypeError；root在作者首次测试执行前已补源码guard。不存在作者以旧源码运行该P1 RED的声明。
2. `/private/tmp/weekly19_Stage024_startup_policy_red.log`：13项中5个positive/terminal subcase错误，实际原因为初稿合成fundsbroker缺execution_profile。按真实provider公共metadata补齐，未放宽源码守卫或更改production资料。
3. `/private/tmp/weekly19_Stage024_startup_policy_green_attempt001.log`：13项通过，0.019s。
4. `/private/tmp/weekly19_Stage024_startup_policy_quantity_red.log`：新增数量类型测试1方法/2subcase失败，真实重现True/1.0与授权1混同；立即交root，不改其module。
5. root已最小增加snapshot positions exactdict/方向/strict整数手数，报告其policy14＋原入口5＋opening funds20共39项通过，0.58s。本作者按root要求未重复跑整组。
6. 独审报告`Stage024_review_root_components_attempt002.json`（SHA c301fa9a4e049dc885a9340bdbcd632f3333135cd31f212f1cd8651aa120f1b3）：新opening20＋作者startup14＋原入口5＋额外坏形状/CLI3共42调用通过，11文件前后SHA无漂移。该结果为组件partial scope，不包括后续runtime/adoption或整链资格。

## 当前锁源

- 作者测试（14方法）SHA256：`1d3a57f82ab53b70e89f04e8d3e1f99e862014350aab4e185210758c6cf19ae7`。
- root-owned startup module在作者最后只读核验时SHA256：`2a07a6c396462a43b69277a871688b276a530678a9f061cdce4158e9bd79eaff`；该项由root后续统一锁，不由作者代签全局source。
- compile(source)与尾空格检查通过。作者测试已LOCK，不再修改；源码新finding先交owner，不在全套CI期间悄改。

## state→fund前向桥只读核对

`PipelineStateStore.transact`明确调用`FundingStore._forward_ledger(...,strict_manual_parent=True)`，后者无条件接入`assert_opening_equity_forward`，因此已有actor普通提交的opening改写/删除及基线替换守卫可达；decision-origin的_validate前向核验也间接接入。

同时已告root一个适用范围：新的`initialize_weekly19_existing_account`最初走store.initialize(bundle)，不是transact；initialize只有_validate/_write，没有previous fund可比。当前实际caller以backend.begin产生fund再bootstrap，正常数据来自正确来源；若要求首个初始化也硬性保证“只能精确一笔begin输出、不夹带其他fund活动”，应在该首次入口从_initial(context).funding到最终bundle.funding显式调用同helper，不能误称transact hook已自动覆盖initialize。本作者仅报告入口差异，没有代改或声称这是已证明的生产绕过。

过拟合：否，全部为会计与来源边界，无策略参数、信号或金融回测变化。继续价值：是，以合成反例验证实际会使用的私有启动入口，而不是拿fixture通过冒认生产资格。后续由root统一新m4闭包、完整CI和生产来源/安装；m3与历史证据不覆盖。
