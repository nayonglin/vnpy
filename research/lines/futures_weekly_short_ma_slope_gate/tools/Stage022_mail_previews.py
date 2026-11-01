"""Literal, synthetic notification previews; no market replay or transport."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'examples/portfolio_backtesting'), str(ROOT / 'tests')]
from qmt_roll_weekly19_daily_report import build_daily_risk_report
from qmt_roll_weekly19_friday_report import build_friday_report
from test_weekly19_daily_report import inputs, row, DAY
from test_weekly19_friday_report import inputs as friday_inputs

OUTPUT = ROOT / 'research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage022_daily_mail_previews_attempt002'


def main():
    assert not OUTPUT.exists(), 'Preserve earlier preview outputs'
    samples = [
        ('01_无信号', inputs()),
        ('02_风险组压力降仓', inputs(rows=[row()])),
        ('03_保证金降仓_原空头买平', inputs(rows=[row(position_direction='short', reason_code='forced_margin_deleverage')])),
        ('04_以前信号_部分成交待重试', inputs(rows=[row(signal_date='2026-10-30', next_execution_day=DAY,
            filled_volume=1, status='retry_required', intent_ids=['original', 'retry'], fill_trading_dates=[DAY])])),
        ('05_原因未确认', inputs(rows=[row(reason_code='')]))]
    unavailable = inputs()
    unavailable['data_receipt']['status'] = 'not_ready'
    samples.append(('06_数据未就绪', unavailable))
    queued = inputs(rows=[row(signal_date='2026-10-30', next_execution_day=DAY)])
    queued['decision'].update(bars_queued=True, reduce_only=True, blocked_reason='unresolved_execution_lifecycle')
    samples.append(('08_当天策略尚未完成评估', queued))
    OUTPUT.mkdir(parents=True)
    warning = '【合成数据离线样例，不是实际交易信号；未发送邮件，未连接CTP，未运行回测】\n\n'
    summary = []
    for name, arguments in samples:
        report = build_daily_risk_report(**arguments, preview=True)
        (OUTPUT / (name + '.txt')).write_text(warning + '主题：' + report['subject'] + '\n\n' + report['body'])
        summary.append(dict(sample=name, schema=report['schema'], risk_status=report['risk_status'],
                            today_cluster_signal_status=report['today_cluster_signal_status'], report_sha256=report['report_sha256']))
    arguments = friday_inputs()
    arguments['decision']['intents'] = [dict(vt_symbol='rb2701.SHFE', direction='short', offset='close', volume=2,
                                            exit_reason='long_risk_cluster_heat_deleverage')]
    report = build_friday_report(**arguments, preview=True)
    (OUTPUT / '07_周五信号补资邮件_含退出原因.txt').write_text(warning + '主题：' + report['subject'] + '\n\n' + report['body'])
    sources = [Path(__file__), ROOT / 'tests/test_weekly19_daily_report.py', ROOT / 'tests/test_weekly19_friday_report.py',
               ROOT / 'examples/portfolio_backtesting/qmt_roll_weekly19_daily_report.py', ROOT / 'examples/portfolio_backtesting/qmt_roll_weekly19_friday_report.py']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    receipt = dict(schema='Stage022.synthetic-offline-mail-previews.v1', source_kind='literal_unit_test_fixtures_not_market_signals',
                   samples=summary, source_files_sha256={str(p): sha(p) for p in sources},
                   preview_files_sha256={p.name: sha(p) for p in OUTPUT.iterdir()}, financial_replays=0,
                   smtp_sends=0, ctp_connections=0, actual_orders=0, production_qualified=False)
    (OUTPUT / 'preview_manifest.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(dict(output=str(OUTPUT), preview_emails=8), ensure_ascii=False))


if __name__ == '__main__':
    main()
