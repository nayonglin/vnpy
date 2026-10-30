"""Seal only Stage014 independent evidence after saved-ledger and delivery review.

No engine, broker, market-data or browser API is imported or invoked. Existing
accepted evidence is read-only; outputs must not already exist.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_weekly_short_ma_slope_gate'
STAGES = LINE / 'stages'
ART = LINE / 'artifacts/stage014_five_starts_R150'
ROOT_STAGE = STAGES / '20261031_0013_stage014_five_annual_starts_R150_results.md'
EXPECTED_ROOT_STAGE_SHA = '1065303b904e351a2a0662bc4be269ff2bccb3f4de9d4a30f9819ddf5b57f862'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    assert not path.exists(), f'Immutable output already exists: {path}'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def markdown_rows(text):
    rows = []
    for line in text.splitlines():
        if line.startswith('|') and not re.match(r'^\|[-:\s|]+$', line):
            rows.append([v.strip() for v in line.strip('|').split('|')])
    return rows


def main():
    outputs = [STAGES / 'stage014_independent_root_stage_review.json',
               STAGES / '20261031_0020_stage014_independent_final_review.md',
               STAGES / 'stage014_independent_final_review.json']
    assert not any(p.exists() for p in outputs), 'Do not overwrite final evidence'
    assert sha(ROOT_STAGE) == EXPECTED_ROOT_STAGE_SHA
    names = ['data_admission', 'code_review', 'runs_review', 'numeric_review',
             'existing23_prefix_review', 'pending_delivery_review', 'delivery_review']
    reviews = {n: load(STAGES / f'stage014_independent_{n}.json') for n in names}
    for n, d in reviews.items():
        assert d['accepted'] and not d['failures'], n
        assert all(d[k] == 0 for k in ('P0', 'P1', 'P2')), n
    numeric = reviews['numeric_review']
    runs = reviews['runs_review']
    prefix = reviews['existing23_prefix_review']
    delivery = reviews['delivery_review']
    freeze = load(STAGES / 'stage014_freeze.json')
    registry = load(LINE / 'outputs/stage014_multistart/registry.json')
    assert registry['counts'] == {'pending': 0, 'running': 0, 'validated': 59, 'failed': 0, 'total': 59}
    assert registry['financial_engine_batch_complete'] and registry['financial_replays_started'] == 59
    assert all(j['status'] == 'validated' and j['method'] == 'fresh_engine' and not j['reused']
               for j in registry['jobs'].values())
    assert sha(STAGES / 'stage014_freeze.json') == numeric['freeze_sha256'] == runs['freeze_sha256']
    assert freeze['source_head'] == '688754057ba1dc07caa9edc537ceec486f678372'
    assert len(freeze['source_files_sha256']) == 71
    assert len(runs['complete_financial_output_files_sha256']) == 4366
    assert runs['output_bytes_rehashed'] == 9849041623
    assert numeric['summary_windows'] == 59 and numeric['daily_points'] == 86049
    assert numeric['mature_windows'] == 54 and numeric['observation_windows'] == 5
    assert numeric['cohort_rows'] == 12 and numeric['new_financial_engine_runs'] == 59
    assert prefix['matching_old_C_windows'] == 23 and prefix['checks'] == 18311
    assert prefix['old29_nonflat_windows'] == 1 and prefix['all_23_economic_prefixes_equal']
    held = [(w['start'], w['old29_held_contracts']) for w in prefix['windows']
            if w['old29_held_contract_count']]
    assert held == [('2025-01-01', ['rb2701.SHFE'])]
    assert delivery['html_rows'] == 59 and delivery['options'] == 60
    assert delivery['embedded_images'] == 5 and delivery['active_external_resources'] == 0
    assert len(delivery['publication_status_only_pixel_proof']) == 5
    assert all(v['all_chart_body_pixels_exact'] and v['changed_bbox'][3] < 80
               for v in delivery['publication_status_only_pixel_proof'].values())
    plot_qa = load(STAGES / 'stage014_plotter_actual_QA.json')
    assert plot_qa['accepted'] and not plot_qa['failures']
    assert sha(STAGES / 'stage014_plotter_actual_QA.json') == '24b7e5d6174f907660dac8e92e27820e670bad126f484aa05fdff9e2c268a8a7'
    assert sha(STAGES / 'stage014_independent_run_hash_cache.json') == reviews['code_review']['source_hash_cache_sha256']

    # Reverify actual bytes once per path, including all 4,366 financial files.
    verified = {}
    def verify_map(mapping):
        for p, h in mapping.items():
            if p not in verified:
                verified[p] = sha(p)
            assert verified[p] == h, p
    for mapping in [freeze['source_files_sha256'], runs['complete_financial_output_files_sha256'],
                    numeric['audited_code_sha256'], numeric['data_files_sha256'],
                    numeric['window_receipts_sha256'], prefix['source_files_sha256'],
                    delivery['report_files_sha256'], delivery['chinese_window_records_sha256']]:
        verify_map(mapping)
    verify_map({p: v['sha256'] for p, v in delivery['figure_files'].items()})

    frame = pd.read_csv(ART / 'summary.csv')
    cohorts = pd.read_csv(ART / 'cohort_summary.csv')
    mature = frame.loc[~frame.observation_only]
    obs = frame.loc[frame.observation_only]
    text = ROOT_STAGE.read_text()
    rows = markdown_rows(text)
    facts = []
    def check(label, condition):
        assert condition, label
        facts.append(label)
    def numeric_value(text_value):
        return float(text_value.replace(',', '').replace('%', ''))
    def equal(label, actual_text, expected, tolerance):
        check(label, math.isclose(numeric_value(actual_text), float(expected),
                                 rel_tol=0, abs_tol=tolerance))
    check('all59 fresh/54mature/5observation', len(frame) == 59 and len(mature) == 54 and len(obs) == 5
          and set(frame.method) == {'fresh_engine'})
    check('mature51positive3negative', (mature.real_trading_net_pnl > 0).sum() == 51
          and (mature.real_trading_net_pnl < 0).sum() == 3)
    check('mature5exhausted37margin0nonpositive', mature.reserve_exhausted.sum() == 5
          and (mature.trading_margin_over100_days > 0).sum() == 37
          and (mature.nonpositive_trading_equity_days > 0).sum() == 0)
    check('observation3positive2negative_not_votes', (obs.real_trading_net_pnl > 0).sum() == 3
          and (obs.real_trading_net_pnl < 0).sum() == 2 and '观察窗不投票' in text)
    f = frame.set_index('start').loc['2015-01-01']
    main = {row[0]: row[1] for row in rows if len(row) == 2}
    for key, field, tolerance in [('期末交易权益E', 'account_end_equity', .51),
                                 ('含入金账户增长', 'account_growth_pct', .0051),
                                 ('真实交易净盈亏', 'real_trading_net_pnl', .51),
                                 ('账户最大回撤', 'balance_max_dd_pct', .0051),
                                 ('账户Sharpe，含入金', 'balance_sharpe', .00000051),
                                 ('轮次胜率', 'round_win_rate_pct', .0051)]:
        equal('full2015_' + key, main[key], f[field], tolerance)
    for key, fields, tolerance in [('累计补资 / 场外余款', ['total_transferred', 'off_account_reserve_end'], .51),
                                  ('总滑点 / 手续费', ['total_slippage', 'total_commission'], .51),
                                  ('建模成交 / 闭合轮次数', ['modeled_fill_count', 'round_count'], 0),
                                  ('平均盈利 / 平均亏损绝对值', ['round_average_win', 'round_average_loss_abs'], .51),
                                  ('盈亏比 / Profit Factor', ['round_payoff_ratio', 'round_profit_factor'], .00000051)]:
        for value, field in zip(main[key].split('/'), fields):
            equal('full2015_' + field, value.strip(), f[field], tolerance)
    for _, c in cohorts[cohorts.scope == 'mature_ge_1y'].iterrows():
        row = next(r for r in rows if len(r) == 11 and r[0] == c.cohort)
        cols = ['windows', 'positive_real_pnl_windows', 'negative_real_pnl_windows',
                'min_real_pnl', 'median_real_pnl', 'worst_E_dd_pct',
                'minimum_defined_E_sharpe', 'reserve_exhausted_windows',
                'nonpositive_E_windows', 'margin_pressure_windows']
        for cell, col, tol in zip(row[1:], cols, [0, 0, 0, .51, .51, .0051, .00000051, 0, 0, 0]):
            equal('cohort_' + c.cohort + '_' + col, cell, c[col], tol)
    for _, f in mature[mature.real_trading_net_pnl < 0].iterrows():
        row = next(r for r in rows if len(r) == 7 and r[0] == f.start)
        cols = ['account_end_equity', 'account_growth_pct', 'real_trading_net_pnl',
                'total_transferred', 'off_account_reserve_end', 'balance_max_dd_pct']
        for cell, col in zip(row[1:], cols):
            equal('loss_' + f.start + '_' + col, cell, f[col], .0001)
    for _, f in obs.iterrows():
        row = next(r for r in rows if len(r) == 7 and r[0] == f.start)
        cols = ['trading_days', 'account_end_equity', 'real_trading_net_pnl',
                'total_transferred', 'balance_max_dd_pct', 'balance_sharpe']
        for cell, col, tol in zip(row[1:], cols, [0, .51, .51, .51, .0051, .00000051]):
            equal('obs_' + f.start + '_' + col, cell, f[col], tol)
    for label, field in [('成熟最小真实PnL', 'real_trading_net_pnl'),
                         ('成熟最大账户DD', 'balance_max_dd_pct'),
                         ('成熟最低有效账户Sharpe', 'balance_sharpe')]:
        f = mature.loc[mature[field].idxmin()]
        row = next(r for r in rows if len(r) == 8 and r[0] == label)
        check(label + '_start', row[1] == f.start)
        cols = ['trading_days', 'account_end_equity', 'real_trading_net_pnl',
                'total_transferred', 'balance_max_dd_pct', 'balance_sharpe']
        for cell, col, tol in zip(row[2:], cols, [0, .51, .51, .51, .0051, .00000051]):
            equal(label + '_' + col, cell, f[col], tol)
    for token in ['59fresh', '54成熟5观察', '2872交易日', '150000−E', '2026-10-30',
                  '189', '185', '143', '1345757', '392197', '591=573', '18结构',
                  'main', '71源', '28项目标测试', '11core+4data+13report/plots',
                  '4366', '9849041623', '13172798', '2662751', '116253', '10007',
                  '10199', '18311', '59summary/86049daily', '12cohorts', '51', '负3',
                  '57,759/43,180', '150000−15120+65140=200020', '284880',
                  '零手续费', 'PIT', '日线next-open', '容量', '54独立OOS',
                  '0闭合', 'N/A', 'NO_PROMOTION', 'file://', '未验收',
                  '不扫描日期/阈值/品种救参', sha(STAGES / 'stage014_independent_delivery_review.json'),
                  sha(STAGES / 'stage014_plotter_actual_QA.json')]:
        check('prose_token_' + token, token in text)
    check('mature_mean_T_rounded', round(mature.total_transferred.mean()) == 57759)
    check('negative_real_PnL_not_account_profit', all(
        math.isclose(r.account_end_equity, 150000 + r.real_trading_net_pnl + r.total_transferred, abs_tol=.000001)
        for _, r in frame.iterrows()))
    check('old29_hold1_not_all_flat', '旧29实际非空仓起点有1组' in text)
    check('onlyfinal_seal_next', '后续归档由最终root_stage/final独审签SHA' in text)

    at = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    root_review = dict(schema='stage014_independent_root_stage_fact_review_v1', created_at=at,
        status='PASS_WITH_LIMITATIONS', accepted=True, P0=0, P1=0, P2=0, failures=[],
        root_stage=str(ROOT_STAGE), root_stage_sha256=sha(ROOT_STAGE), fact_checks=len(facts),
        checked_facts=facts, numeric_review_sha256=sha(STAGES/'stage014_independent_numeric_review.json'),
        prefix_review_sha256=sha(STAGES/'stage014_independent_existing23_prefix_review.json'),
        delivery_review_sha256=sha(STAGES/'stage014_independent_delivery_review.json'),
        plotter_QA_sha256=sha(STAGES/'stage014_plotter_actual_QA.json'),
        data_files_sha256=numeric['data_files_sha256'], auditor_source_sha256=sha(__file__),
        scope='Chinese facts/tables/cashflow/limits verified against accepted saved-ledger independent reviews; no live/production qualification.',
        financial_replays=0, market_downloads=0, production_accesses=0, promotion_decision='NO_PROMOTION')
    write_new(outputs[0], root_review)

    md = f'''# Stage014 最终独立审查（2026-10-31，北京时间）

结论：PASS_WITH_LIMITATIONS，accepted=true；未解决P0/P1/P2均0，NO_PROMOTION。审查者与金融/报告实现者分离，只读真实保存账本，不构造金融引擎、下载或接触生产，不提交。金融59次独立回放全部成功、无复用、无失败或重跑；独审及后处理失败尝试保留，不用改策略参数救结果。

本轮仅扩固定1/3/6/9/11月独立起点和最新完成日2026-10-30，59窗/86049日点/12组统计，54成熟、5观察。新data与71冻结源、全部main导入实际origin及共享资产已准入。原Stage009备用类字节与AST相同，金融Try/Engine/风险/父sizing等规范化相同，差异限定起止范围、映射路径和管理输出；E150000、场外R150000、底部20%过滤和原分档风险不变。

数据独审3066项：旧SQLite1345757行全列及旧physical392197行/映射前缀保持；189个目标均有30日观测，185正量实K准入，4个零/无效SM远月只分类，143形成中/未来条目排除。4合约有历史正量行情，但完整mapping主力次数为0，源码零仓冷启动/新开仓/换月路径证明不可达，59真实成交与非零持仓再验为空。旧591项=573证实零量+18结构缺陷及预热/PIT局限如实保留，无新未知main缺失、无伪造全ready。

逐窗raw库存/FIFO/成交/费用/日MTM/完整合约轮次及资金事件独立复算：raw_core=13172798、funding=2662751、Stage014=116253检查，10007实际entry风险行。E=150000+累计真实PnL+T、R=150000−T、W=300000+累计真实PnL，闭合净盈亏+未平轮次MTM=真实PnL；主NAV=E/150000含入金，不把入金当策略利润。最终4366个金融输出、9849041623字节SHA全部实读，并在最终签封重核，不以hash cache代替金融输出证据。

Canary及全部23个旧同起点C在<=29经济prefix通过（18311检查），包括2025Jan旧29仍持rb2701.SHFE的一组，非全部空仓。fills/anchors按实际执行交易日，不把30执行计入29。不同终点pending_orders只分别绑定SHA，不宣称相同；普通订单完整导出缺失的可观测边界明确记录。新30日核价/MTM/完整周聚合通过。

数字独审10199项；成熟54窗真实PnL51正3负，三亏损起点2024June −8560、September −15120、November −9420。补资使这三窗账户含入金增长仍为正，2024Sep的E=150000−15120+65140=200020、W=284880清楚说明增长不等于盈利。5窗备用耗尽、37窗至少一日静态margin×1.65/E>100%、0非正E；不存在实盘可行性证明。5观察窗3正2负不投票，2026Sep仅3闭合轮次，PF12.071429不能解释为稳定优势。全2015E4219305、真实PnL4025345、T43960、DD−51.0470205%、Sharpe0.916469411；新零收益日改变Sharpe，未抄旧29数值。

五张pending图已逐张目视，正式版全图体逐像素一致，仅顶部y=16..40审核状态标题改变；HTML/MD仅审核状态和已校验PNG载荷变化。最终HTML59行、60选项、5内嵌PNG与实物SHA一致，无主动外部资源；59中文单窗完整，PF/payoff/非正E未定义口径按None/N/A处理，实际59账户Sharpe均可定义。自动file://交互受既有安全限制未验收，无HTTP或绕过。报告作者另做pending/final十图目视与59行数值QA，未代替本独审。

发现与bug：未发现未解决P0/P1/P2。审计适配期间字段名/既有非bar分类/有效配置key边界等失败尝试完整保留；修复只在新Stage014审计工具，未触发金融重跑，既有接受JSON不覆盖。28实现目标测试（11core+4data+13report/plots）、独审scope和反例及实际数据/59结果交叉核验覆盖本冻结范围。零闭合/无胜无亏等未定义指标是合法状态，不以0/Inf伪造，未当作金融失败。

置信度：冻结模型内数据身份、因果执行和会计一致性较高；样本外获利和可部署性证据不足。零手续费、日线next-open、静态margin×1.65、容量、已有PIT/生命周期/主力重建缺陷仍限制结论。成熟54窗相互重叠且持有期不同，不是54独立OOS，月组中位数不能用于选月。运行前后过拟合风险判断均是：同历史反复查看；本阶段无策略/金额寻优。继续价值判断均是：固定五起点反证资本需求和左尾有价值，必须保留负结果；不能据此自动晋级或扫描日期/阈值/品种救参。

冻结金融HEAD：{freeze['source_head']}；freeze SHA：{sha(STAGES/'stage014_freeze.json')}。
源/数据/逐窗/runs/numeric/prefix/delivery/root-stage证据及本记录的SHA由stage014_independent_final_review.json签封，最终delivery manifest另由root封存。root_stage事实检查{len(facts)}项，最终SHA {sha(ROOT_STAGE)}。本审查文件锁定后不再改，后续仅研究manifest和本地提交，不触碰旧链/生产。
'''
    assert not outputs[1].exists()
    outputs[1].write_text(md)
    # Closed evidence only: mutable status/cache/lock excluded; no open seal log.
    excluded = {'stage014_independent_hash_cache.json', 'stage014_independent_stream.lock',
                'stage014_independent_working_state.json'}
    evidence = list((LINE/'tools').glob('stage014_independent*.py'))
    evidence += [p for p in STAGES.glob('stage014_independent*') if p.is_file() and p.name not in excluded]
    evidence += list((STAGES/'stage014_independent_receipts').glob('*.json'))
    evidence += [ROOT_STAGE, STAGES/'stage014_progress.md', STAGES/'stage014_plotter_actual_QA.json',
                 STAGES/'20261031_0017_stage014_actual_report_QA.md', STAGES/'stage014_freeze.json',
                 STAGES/'stage014_canary_independent_review.json',
                 LINE/'outputs/stage014_multistart/registry.json', ART/'delivery_receipt.json', outputs[1]]
    bindings = {str(p): sha(p) for p in sorted(set(evidence))}
    assert len(list((STAGES/'stage014_independent_receipts').glob('*.json'))) == 59
    result = dict(schema='stage014_independent_final_review_v1', created_at=at,
        status='PASS_WITH_LIMITATIONS', accepted=True, P0=0, P1=0, P2=0, failures=[],
        financial_source_head=freeze['source_head'], freeze_sha256=sha(STAGES/'stage014_freeze.json'),
        frozen_source_files=71, fresh_financial_runs=59, reused_candidates=0,
        financial_failed_runs=0, financial_replays=0, market_downloads=0, production_accesses=0,
        summary_windows=59, daily_points=86049, cohort_rows=12, mature_windows=54, observation_windows=5,
        checks=dict(data=3066, raw_core=13172798, funding=2662751, stage014=116253,
                    numeric=10199, old23_prefix=18311, root_stage=len(facts)),
        actual_entry_risk_rows=10007, financial_output_files_reverified=4366,
        financial_output_bytes_reverified=9849041623,
        complete_financial_output_files_sha256_bound_by_runs_review=sha(STAGES/'stage014_independent_runs_review.json'),
        actual_file_graph_paths_reverified=len(verified), root_stage_sha256=sha(ROOT_STAGE),
        root_stage_review_sha256=sha(outputs[0]), numeric_review_sha256=sha(STAGES/'stage014_independent_numeric_review.json'),
        prefix_review_sha256=sha(STAGES/'stage014_independent_existing23_prefix_review.json'),
        delivery_review_sha256=sha(STAGES/'stage014_independent_delivery_review.json'),
        chinese_review=str(outputs[1]), chinese_review_sha256=sha(outputs[1]),
        mature_results=dict(positive_PnL=51, negative_PnL=3, reserve_exhausted=5, margin_over100=37, nonpositive_E=0),
        observation_results=dict(positive_PnL=3, negative_PnL=2, not_votes=True),
        preserved_failed_audit_attempts=True, no_financial_rerun_for_audit=True,
        old29_nonflat_prefix_windows=1, all23_prefixes_equal_through='2026-10-29',
        five_PNG_chart_bodies_pixel_identical=True, publication_title_changed_y_range=[16,40],
        final_html=dict(rows=59, options=60, embedded_PNGs=5, active_external_resources=0),
        browser_interaction_verified=False, automatic_file_URL_limitation_preserved=True,
        evidence_files_sha256=bindings, excluded_mutable_non_evidence=sorted(excluded),
        confidence='High for saved frozen-model identity/causality/accounting; generalization and deployability limited by repeated overlapping history, zero fees, inherited PIT/lifecycle, daily next-open/static margin/capacity.',
        promotion_decision='NO_PROMOTION', evidence_locked=True, auditor_source_sha256=sha(__file__))
    write_new(outputs[2], result)
    # Verify all signed evidence after the final write, including source code itself.
    for p, h in bindings.items():
        assert sha(p) == h, p
    assert sha(ROOT_STAGE) == EXPECTED_ROOT_STAGE_SHA
    print(json.dumps({'status': result['status'], 'accepted': True, 'P0': 0, 'P1': 0, 'P2': 0,
        'fact_checks': len(facts), 'evidence_files_locked': len(bindings),
        'reverified_actual_file_graph_paths': len(verified),
        'outputs': {str(p): sha(p) for p in outputs}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
