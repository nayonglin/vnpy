# Stage009 已审图纯展示工具：实现与未执行说明

- 仅新增 `tools/stage009_reviewed_visual.py`、`tools/test_stage009_reviewed_visual.py` 与本组日志。未修改 plots、financial、cache、pending报告或独审JSON；未执行真实工具 main、未生成真实已审目录/收据、未 commit。
- CLI：`.py311/bin/python research/lines/futures_weekly_short_ma_slope_gate/tools/stage009_reviewed_visual.py --locked-review-sha <最终SHA>`。必须由根协调者在最终独审锁定后调用。
- 必须独审JSON字节SHA与显式参数相等，状态PASS/PASS_WITH_LIMITATIONS、P0/P1/P2/failures全0；冻结文件SHA与报告/最终独审一致，46新臂窗、46配对、23起点、92汇总、141996逐日点、每臂22成熟+1观察、同30万本金和五名固定图均核对。此处不能沿用Stage008的23配对计数。
- 最终独审 `source_files_sha256` 必须绑定本工具及其测试当前SHA。图表/报告源码及其测试须与 pending报告源绑定相等；最终独审的完整 report_files_sha256、报告delivery manifest与当前全部报告文件的集合和SHA精确一致。金融和原始数据来源按已冻结source map逐文件复核，不调用金融/会计加载器。
- 读取 summary/paired/all_daily CSV采用 pandas `float_precision='round_trip'`，以实际报告参数dpi160、bbox_inches=tight重建pending；五个PNG SHA必须与原pending逐字节相同。随后 reviewed=True 只允许总标题审核状态变化，比较轴范围/尺度/位置、线、热力图矩阵、柱形、散点、表格、图例、页脚等artist完整签名；保存后再次核对。
- 已审图片只保存五个固定名；临时目录准备后atomic rename，收据使用exclusive hardlink最后发布。不覆盖已有目录/收据；异常仅回滚自身已发布新输出。前后反复检查最终JSON锁、全部源SHA及pending文件集合，保持原文件字节不变。
- 收据 mandatory字段：independent_review_sha256；reviewed_figures_sha256（五个绝对路径→SHA）；另含 source_inputs_sha256、freeze/report SHA、五项pending重建及artist等价证明、scope、NO_PROMOTION和 financial_replays/market_downloads/production_accesses全0。

## 验证

- `stage009_reviewed_visual_red.txt`：初始5项因缺工具而RED。
- `stage009_reviewed_visual_green.txt`：5项GREEN；编译通过。覆盖错审核SHA/非PASS/存在发现拒绝、Stage009范围/报告/冻结绑定、精确五名、pending SHA漂移、条形/线/图像/散点/表格变更拒绝、原子发布回滚保留来源。
- `stage009_reviewed_visual_synthetic_smoke.txt`：只用合成92/46/141996结构，所有PNG在内存BytesIO；5张CSV roundtrip重建逐字节一致；全部reviewed图只改审核标题、保存前后artist签名相同。未使用真实报告，不能把此合成检查当真实五图视觉验收。
- 等待根提供最终SHA后才允许真实派生；之后仍需核对真实已审图/收据和最终总manifest。
