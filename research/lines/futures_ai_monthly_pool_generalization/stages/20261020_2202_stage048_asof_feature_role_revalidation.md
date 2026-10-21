# Stage048 大小写身份勘误与asof12特征重验

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 22:02 CST；修复错误，非收益突破。不改LINE/registry/正式/其他线。
- 原044输出/receipt冻结不覆盖。before_role_fix源码快照SHA与原summary绑定相同。新增Stage048独立builder及4项身份TDD先红后绿；原12特征函数和公式未改。

## 修复、运行与逐位验证

product/exchange统一uppercase后比较，原18仍从同冻结AST名单读取，FU.SHFE独立fixed，_F marker与后缀不一致拒绝。22:01:00–07新跑过去panel：19,698行/98域/201月，8,998已知12/10,700未知、368,918精确past41投影；73固定分层样例/1,123手写Wilder/算术/source检查0失败。

与原044逐key比较：2,211行只domain_role变化，所有其他cell文本完全相同；12列CSV文本完全相同，SQLite所有12float64及missing pattern bitwise完全相同。text SHA c08c0d8cd13e51589411055ca0cdfecabd9061f14d853dfe4cec11ac550ccade；float64 SHA 5eaa5a361be80a1b7bd9fed8771e0bb29afb5f26deac9938d46f56138c455564。独立校验脚本/role-only收据在outputs/stage048_asof_features_revalidated。

## 正确分组与Stage008历史汇总勘误

| role | 产品域 | 月格 | 过去41已知 | 月末fresh观察 |
| --- | ---: | ---: | ---: | ---: |
| 原18 | 18 | 3618 | 2306 | 40 |
| 非fu扩展 | 76 | 15276 | 6547 | 144 |
| fixed FU | 1 | 201 | 122 | 1 |
| monthly_F | 3 | 603 | 23 | 0 |

普通已知8975=2306+6547+122；原18外含固定fu为6669，严格非fu扩展6547。此前1010/7965是exact-case分组错误，不是行情增删或性能变化。总185 fresh、8998已知/8975 ordinary不变。Stage008原矩阵SHA c65d8c6ee017e578e13e0d3ea0b9d65f0f41f49782db86123d451ee0ef77d832未改；本目录给逐product勘误CSV与normalized_role_counts/role_changed_rows，保留旧账由root更新当前摘要。

root反馈042 asof_status用upper排FU，045既有N/labels不受044 role错误影响；这是root核查，不把本项检查冒充label重验。此处不读future target/不重算labels。

本项4身份+原8特征测试通过，最终本线149 tests通过。独审待root安排，本项source/手写oracle自验不是独审。

## 反思与边界

新增按未来表现择参过拟合否，修复来自身份错误，不读future target/fit，不改12项合同。继续价值是，非fu扩展仍有6547过去输入月格，但不是新增独立经验或可训练净标签。未知future不能删候选。正式/模型alpha参数新增修改删除0，权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A。未来标签读取、fit、金融回测、正式A/C、下载、订单、生产修改均0；正式A/C仍因身份缺项禁跑。
