# Stage263：已接受自愿K现金接口只读盘点

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 00:18 CST；非重要突破、非新实验协议。
- 新增 fit/cash/SQL/网络/标签/预测/选择/回测/测试均 **0**，累计 **439/234**。仅源码文本/AST、小元数据及stat；未import/执行被盘点程序，未读价格、CSV、NPZ、标签或SQL内容。

**已接受现金核及四控制可复用，依赖在本次元数据范围内闭包；原157 CLI不能原样作新过滤入口，未来薄封装须另定协议，本次未实现或授权。** 身份固定为130纯COMMON52 → 156原D<K后选月 → 157四现金 → 158已接受算术；排除238失败K_TARGET52、218 DOMAIN52及无K的131账。

## 现成函数及最小接入面

下列文件均在本线`tools/`；准确绝对路径、SHA、四控制全部文件引用见[refs](./20261020_0018_stage263_cash_interface_inventory_refs.json)。

| 原文件 / 函数签名 | 输入与输出 |
| --- | --- |
| `stage131_contract_choice_kernel.py:90`：`run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy='NARROW')` | 信号、缓存market、完整日历、冻结经济快照、base/stress及窗口索引 → fills/daily/budgets/position_days/closed/open、summary、容量与入场未知项；算术不改。 |
| `stage131_contract_choice_cash.py:127`：`organize(signals,mothers,dates)` | → `(potential,references)`；前者用过滤后信号，后者必须由**原完整399252 mothers**生成全canonical；作为`prepared`传入。 |
| `stage132_contract_choice_review.py:744`：`restore_native_cache(cache_binding)`；`stage148_fx_cash.py:85`：`CachedMarket(store)` | → `store,receipt,meta`，恢复原数组/日历并核DB stat，SQL=0；market提供`bar(epoch,k)`、`indicator(epoch,k)`。 |

最小入口是157的`signals_VOLUNTARY_RESELECT.csv.gz`（583263B，SHA `c7546f99…f9732`）：据158验收含全部4365个原选择机会，**不是实际成交子集**，已有u/D、分数、N/20low/容量、anchor及source/K/effective边界。未来仅在私有副本取消“有效S且固定条件不通过”的原u动作；缺S继承原动作，不加动作、不重选、不改分数/手数算法/退出。再`organize`、`run_cash_account`，资金释放后的成交变化由原核处理。156完整161014父行和98产品域仍作身份/覆盖分母。无需重读130模型/child_scores、129 actions或重跑156；完整mothers身份列仍用于canonical。

原157 `make_voluntary_signals(actions,mothers,choices,boundaries,market,dates,economics)`及`apply_boundaries(signals,boundaries)`已输出上述冻结信号，无需重做。其CLI固定155旧授权/输入/目录且比较131旧B，历史metadata KeyError已按158续接；未来只引用157控制，不重启CLI、不修历史源、不沿用旧比较门。

## 原四控制与冻结来源

共同根目录为`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/`。156入口是`stage156_voluntary_choices/actual_run1/manifest.json` → `choices_main.csv.gz`（SHA `cce87a00…6fd9ddd`）/`boundaries.json`；不再调用选择器。四控制在`stage157_voluntary_cash/actual_run1/`下：

| 窗口 / 成本 | 账户目录，内含summary.json、daily.csv.gz及原完整账本 |
| --- | --- |
| 2020连续 / base | `NARROW_VOLUNTARY_RESELECT_primary_2020_base/` |
| 2020连续 / stress | `NARROW_VOLUNTARY_RESELECT_primary_2020_stress/` |
| 2023独立冷启 / base | `NARROW_VOLUNTARY_RESELECT_cold_2023_base/` |
| 2023独立冷启 / stress | `NARROW_VOLUNTARY_RESELECT_cold_2023_stress/` |

窗口分别从2020-01-01、2023-01-01到2026-10-16，沿原日历searchsorted。summary/daily及完整账本只读引用，控制重放=0。157 manifest为`completed_with_metadata_continuation`（`0c27edef…e34c7a4`），158 receipt为`74e052d1…380ec735`；仅核绑定，不重评158。

native价格继承`stage132_contract_choice_review/cash_only1/native_store_cache.json` → 同目录`native_store_cache.npz`（110273488B，SHA `d2976090…b9360b7`），不替换source。完整5587日历继承052绑定的`futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/trading_dates.npy`；经济快照继承041 `economic_projection.json`。配对CI如保留则复用070原indices。100万元、0.25N、family风险0.0025/总0.02、margin cap0.25/buffer1.1及容量、费用/tick、生命周期均继承。

59个相关绑定存在/尺寸均匹配；16个小源码和10个小身份文件SHA匹配。132要求原`stage266_clean_daily/clean_daily.sqlite` stat一致：378552320B、inode28078628、mtime_ns1792236170627661666、无wal/shm；当前**匹配**，只stat，未读DB。大数据未读/重hash，非新内容审计。真正未形成的是未来固定S实体/窗口决策sidecar及薄封装独立协议，不是旧现金链缺依赖；本次不创建。

## 调研、反思与边界

先读AGENTS/registry、251/197、157源码和必需小manifest；外部依据复用251归档的[AKShare维护者实现](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_basis.py)，0新网络。判断：现成接口足够，无须重复fit/选择/控制现金。

开始/结束新增过拟合：**否**，只辨认接口、不看新收益或选参数，同史择题风险仍在。继续价值：**是，本次盘点已完成并避免重复计算**；过滤经济价值未知，不能由闭包推出alpha/PIT/晋级。参数、金融结果新增/修改/删除均0，全部成绩N/A；只新增本stage和refs，不改LINE/registry/他线/生产。
