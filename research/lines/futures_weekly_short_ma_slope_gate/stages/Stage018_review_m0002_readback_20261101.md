# Stage018 m0002物料独立只读readback

时间：2026-11-01T05:16+08:00。范围：source/release/manifest、已完成CI的文件子集、旧物料/CURRENT、fresh clone实际文件、inactive市场pins。不重复alpha/CI/datareader，不执行CTP/SMTP/HTTP服务、Git修改或生产操作。

**结论：本范围候选物料绑定核对通过；production_qualified=false。** 只说明候选发布物料与已测源码字节/现有clone一致，不授予实际CTP、人工cash review、qualification、activation、远端master或生产安装资格。

## 关键身份

- strategy_version：official_live_weekly19_base15w_reserve15w_stage014
- ruleset_version：stage014_week_close_19_short_bottom20_original_risk_external_reserve_v1
- source_commit：e89fdcbb68260a647372f03626800110470f61dd
- material_release_id：m0002_20261101T050816+0800_e89fdcbb6826
- release_commit：48839375c26081bf6aeb5610aab70c72c688c59c
- remote_master_sha：本独审未进行远端transport验证；本clone不是remote-master clone。root另有connector只读记录，不能将Gittransport timeout写作fetch/push证明。
- production_source_commit（实际stable只读）：d55887e1def72629fbfa310e439dc3a879969a14

通用material manifest未提供top-level ruleset_version；本ruleset绑定来自源码与payload逐字节相同的固定execution profile，不伪造manifest字段。

## Material/source/release

release父commit恰为source e89；manifest source/releaseID、index项、inventory.csv、checksums.sha256与tree fingerprint一致。378个payload逐项实际SHA/size等于e89对应Git blob及当前top-level源码；全部Git source/payload mode一致，无symlink。release commit变更仅新m2/index/.gitattributes允许范围。manual cash组件、可执行CLI、人工runbook、SOP、shadow skill与945都在payload。

raw manifest文件SHA：1a23fda7a25051c4890d190c146ce33068ba1c478ce90fc3e0385e733ec5989c。manifest内部canonical digest：85425232204ab3af875167705afbc58d57f8000985e86f0e46ff8373d0eaa7b4。两者是不同校验口径，均重算通过，不能混称同一个SHA。

manifest qualification明确candidate、production_qualified=false、evidence_ids空。operator_manual_v1来自payload实际config与provenance；不以0F改变自然研究NO_PROMOTION或真实运行资格。

## CI子集

读取既有Stage018_selected_final_attempt002.json/XML而不重跑。288个before/after SHA完全相同且全是m2 378清单的subset，并逐项等于source e89 Git blob；JUnit实数90个module、2309 testcase、0 failure/0error/0skip。源本身记录accepted_offline_only=true、production_qualified=false、无金融回放/CTP/API调用。

CI原source_commit字段是pre-commit HEAD b086，保持原记录不改。测试时工作树字节与后续e89的绑定通过288个精确Git blob/hash完成，而不是冒称CI当时已在e89 HEAD运行。完整映射证明存readback_result，未把90额外payload文件也说成“全部CI critical”。

## 旧m1与CURRENT

旧m1目录Git tree从首次引入commit d5243461b9cf0368723899bcce67a3dc6fb0ec1a 到source/release/HEAD相同，树OID 1c4347e235dc1fda9a0608022cc6c14c9ed4e234；官方读取校验也通过。

开发树、fresh clone与stable CURRENT仍为m0008_20261008T204054+0800_2a7420a9f955，不是m2。stable只读HEAD为旧d558且worktree干净；candidate未激活/未成为生产事实。

## Fresh clone实际验证

clone：/private/tmp/weekly19-stage018-m2-fresh-i8o9o39a/clone。

实际HEAD=488、worktree干净；378payload和378顶层文件逐项SHA/size/文件系统执行位与源Git mode一致。manual CLI实际可执行，objects无alternates且object文件link count均1；30份历史release manifest全部以官方read-only verifier核通过。

历史LFS通过commit内exact LFS pointer oid/size与clone真实文件比较：2865bytes、SHA ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66，实际内容不是pointer。首attempt因本独审PATH没有git-lfs命令中断并保留log；第二次用纯Git pointer解析和实际字节核验，不安装、不下载、不改clone。

receipt声称的最初空LFS cache/原clone命令参数是历史状态，未重复clone故不虚报亲历重验；当前object隔离与实际LFS内容已独立核。此clone明确remote_master_clone=false、runtime tests未重跑、production_qualified=false，不能替代日后remote-master fresh clone或真实production qualification。

## Inactive市场generation

/Users/mac/Library/Application Support/qmt-roll-stage179/weekly19-calendar-candidates/Stage018_calendar_20261101T043315_ad4afb28/Stage018_complete_market_20261101T043552_3f8943b8

原五源+forward_calendar.csv的六个实际SHA仍全部匹配；两vendor原raw及新calendar source receipt SHA保持，独立private市场输入可读。未重复datareader/AM/金融运行，未把calendar可读写成实际broker来源资格。

## 边界

本独审没有发现本范围新的物料绑定差异；不评审/修改alpha或覆盖其他独审范围，不以本报告授予实盘执行。原冻结研究经济失败/限制继续保留。策略参数和金融结果新增/修改/删除均无，收益/回撤/Sharpe等不适用。

过拟合：否，本轮纯字节/身份/readback核对。继续价值：是，为后续真实来源、人工cash review与生产资格提供明确候选身份；实际promotion前仍需root受控流程与native fetch/push重验。

完整证据：Stage018_review_m0002_readback_result.json、readback.py、readback_run.log、首失败log；source与产物SHA另存Stage018_review_m0002_artifact_hashes.json。
