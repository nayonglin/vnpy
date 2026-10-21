"""Only Stage070 new policy boundaries; all inputs are tiny synthetic arrays."""
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd


TOOLS = Path(__file__).parent


def module(name):
    path = TOOLS / (name + ".py")
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture(kernel, finish=25, missing=(), changes=None):
    changes = changes or {}
    dates = [(date(2020, 1, 1) + timedelta(days=k)).isoformat() for k in range(finish)]
    epoch = "X.A.203001"
    rows, mother = [], []
    for k, day in enumerate(dates):
        O, H, L, C = changes.get(k, (100., 101., 99., 100.) if k < 20 else (102., 103., 101.8, 102.))
        if k not in missing:
            rows.append(dict(contract_epoch_id=epoch, trade_date=day, open=O, high=H,
                             low=L, close=C, volume=10., quality_status="accepted"))
        mother.append(dict(event_id=f"e{k}", product_id="X.A", exchange="X", product="A", u_date=day,
                           reference_epoch=epoch, status="observed_long_research_opportunity",
                           planned_execution_date=dates[k + 1] if k + 1 < finish else "", direction="long"))
    econ = {epoch: dict(economics_status="exact_epoch_metadata_snapshot", contract_multiplier=10., round_lot=1.,
                       tick_size=None, vendor_margin_rate=.2, listed_date="2019-01-01", maturity_date="2030-01-15",
                       known_lifecycle_exit_boundary="2030-01-01", future_info_scope="product_default_snapshot")}
    return pd.DataFrame(mother), kernel.ref.Market.from_records(rows, dates), dates, econ


class Stage070Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = module("stage070_policy_kernel")
        cls.labels = module("stage070_narrow_labels")
        cls.cash = module("stage070_narrow_policy_cash")

    def ready(self):
        self.assertIsNotNone(self.kernel, "new isolated policy kernel is required")
        self.assertIsNotNone(self.labels, "new independently simulated narrow labels are required")

    def test_both_widths_recompute_first_exit_and_own_maturity(self):
        self.ready()
        f = fixture(self.kernel, changes={20: (102., 103., 101.4, 102.), 22: (102., 103., 98.5, 100.)})
        narrow = self.labels.build_labels(*f, policy="NARROW").set_index("event_id")
        wide = self.labels.build_labels(*f, policy="WIDE").set_index("event_id")
        self.assertEqual(len(narrow), 25)
        self.assertEqual(narrow.loc["e19", "exit_index"], 20)
        self.assertEqual(narrow.loc["e19", "SL0"], 101.5)
        self.assertEqual(narrow.loc["e19", "label_known_date"], f[2][20])
        self.assertEqual(wide.loc["e19", "exit_index"], 22)
        self.assertEqual(wide.loc["e19", "exit_reference"], 99.)
        self.assertEqual(wide.loc["e19", "label_known_date"], f[2][22])
        self.assertAlmostEqual(narrow.loc["e19", "net_R_stress"], -17.6105 / 5.)
        self.assertAlmostEqual(narrow.loc["e19", "net_R_common2N_stress"], -17.6105 / 40.)

    def test_narrow_can_close_before_wide_absorbing_unknown_without_common_filter(self):
        self.ready()
        f = fixture(self.kernel, missing=(21,), changes={20: (102., 103., 101.4, 102.)})
        n = self.labels.build_labels(*f, policy="NARROW").set_index("event_id")
        w = self.labels.build_labels(*f, policy="WIDE").set_index("event_id")
        self.assertEqual(n.index.tolist(), w.index.tolist())
        self.assertEqual(n.loc["e19", "label_state"], "closed_complete_bar_model")
        self.assertEqual(w.loc["e19", "label_state"], "path_or_execution_unknown")
        self.assertTrue(pd.isna(w.loc["e19", "net_R_stress"]))
        self.assertTrue(pd.isna(w.loc["e19", "label_known_date"]))

    def test_narrow_gap_loss_not_capped_at_R_and_terminal_open_not_closed(self):
        self.ready()
        f = fixture(self.kernel, changes={21: (90., 91., 89., 90.)})
        n = self.labels.build_labels(*f, policy="NARROW").set_index("event_id")
        self.assertEqual(n.loc["e19", "exit_reason"], "gap_stop")
        self.assertEqual(n.loc["e19", "exit_reference"], 90.)
        self.assertLess(n.loc["e19", "net_R_stress"], -24.)
        self.assertEqual(n.loc["e24", "label_state"], "intent_right_censored")

    def test_proxy_retains_all_mother_rows_and_strict_v_same_real_epoch(self):
        self.ready()
        f = fixture(self.kernel, missing=(22,), changes={20: (102., 105., 101., 102.)})
        p = self.labels.build_proxy(*f).set_index("event_id")
        self.assertEqual(p.index.tolist(), f[0].event_id.tolist())
        self.assertTrue(pd.isna(p.loc["e0", "ohlc_proxy_raw"]))
        self.assertEqual(p.loc["e21", "v_date"], f[2][20])
        self.assertAlmostEqual(p.loc["e21", "ohlc_proxy_raw"], (102. - 308. / 3.) / 2.15)
        self.assertEqual(p.loc["e21", "N_state"], "N_v_ready20")
        self.assertEqual(p.loc["e23", "proxy_state"], "missing_or_invalid_v_bar")

    def test_policy_risk_changes_joint_reserve_D_reduce_and_frozen_holding_risk(self):
        self.ready()
        panel, market, dates, econ = fixture(self.kernel, finish=23)
        e = econ["X.A.203001"]
        n = self.kernel.unit_estimate(100., 2., e, "base", "NARROW")
        w = self.kernel.unit_estimate(100., 2., e, "base", "WIDE")
        self.assertAlmostEqual(n["risk_per_lot"], 9.2)
        self.assertAlmostEqual(w["risk_per_lot"], 44.2)
        candidates = [dict(event_id=str(j), reference_epoch="X.A.203001", N_u=2., u_close=100.) for j in range(20)]
        reservations = self.kernel.reserve_batch(candidates, 1_000_000., 0., 0., econ, "base", "NARROW")
        self.assertAlmostEqual(sum(r["allocated_buffered_margin"] for r in reservations), 250_000.)
        self.assertAlmostEqual(sum(r["allocated_risk"] for r in reservations), 10454.54545454545)
        reservation = reservations[0]
        qty, unit = self.kernel.execution_quantity(reservation, 200., e, "base", "NARROW")
        self.assertLess(qty, reservation["qty_cap"])
        self.assertAlmostEqual(unit["risk_per_lot"], 9.4)
        labels = self.labels.build_labels(panel, market, dates, econ, policy="NARROW")
        signals = labels[self.cash.SIGNAL_FIELDS].copy()
        signals["potential"] = signals.event_id.eq("e19").astype(int)
        book = self.kernel.run_cash_account(signals, market, dates, econ, "base", "synthetic", 20, 22, policy="NARROW")
        buy = [x for x in book["fills"] if x["side"] == "BUY"][0]
        self.assertAlmostEqual(buy["risk_per_lot"], 9.204)
        self.assertTrue(all(abs(p["risk_per_lot"] - 9.204) < 1e-8 for p in book["position_days"]))
        self.assertTrue(all(abs(d["initial_risk"] - 9.204 * p["qty"]) < 1e-8
                            for d, p in zip(book["daily"], book["position_days"])))

    def test_cash_scores_do_not_filter_unknown_future_labels_or_55_rows(self):
        self.ready()
        self.assertIsNotNone(self.cash)
        f = fixture(self.kernel, finish=23, missing=(21,))
        labels = self.labels.build_labels(*f, policy="NARROW")
        predictions = labels[["sequence_index", "event_id", "product_id", "family_id", "u_date", "u_index", "reference_epoch"]].copy()
        predictions["policy"], predictions["arm"], predictions["cutoff"] = "NARROW", "SETTLEMENT", "2020-01-01"
        predictions["score"] = 1.
        predictions["history_ready20"] = labels.label_history_ready20
        predictions["selected"] = labels.label_history_ready20
        signals = self.cash.make_signals(labels, predictions, "NARROW", "SETTLEMENT")
        self.assertEqual(len(signals), 23)
        self.assertEqual(signals.loc[signals.event_id.eq("e19"), "potential"].iloc[0], 1)
        self.assertEqual(labels.loc[labels.event_id.eq("e19"), "label_state"].iloc[0], "path_or_execution_unknown")
        labels.loc[labels.event_id.eq("e0"), "reference_epoch"] = np.nan
        predictions.loc[predictions.event_id.eq("e0"), "reference_epoch"] = np.nan
        signals = self.cash.make_signals(labels, predictions, "NARROW", "SETTLEMENT")
        self.assertEqual(signals.loc[signals.event_id.eq("e0"), "reference_epoch"].iloc[0], "",
                         "CSV missing reference must retain observation-exit semantics")

    def test_empty_reference_DD_is_unidentified_and_all_empty_is_unidentified(self):
        self.assertIsNotNone(self.cash)
        active = dict(total_return_pct=2., max_drawdown_pct=-1., fills=2)
        empty = dict(total_return_pct=0., max_drawdown_pct=0., fills=0)
        pair = self.cash.compare_points(active, empty)
        self.assertIsNone(pair["drawdown_percentage_point_difference"])
        self.assertEqual(pair["dd_comparison_state"], "NA_empty_reference")
        self.assertEqual(self.cash.compare_points(empty, empty)["identification"], "all_empty_unidentified")

    def test_all_empty_information_policy_package_has_no_identification(self):
        self.assertIsNotNone(self.cash)
        protocol = json.loads((TOOLS.parent / "outputs/stage069_settlement_narrow_joint_protocol/protocol.json").read_bytes())
        summaries, daily = {}, {}
        for policy in ("WIDE", "NARROW"):
            for arm in ("COMMON", "SETTLEMENT", "OHLC_PROXY"):
                for w in ("primary_2020", "cold_2023"):
                    for cost in ("base", "stress"):
                        key = (policy, arm, w, cost)
                        summaries[key] = dict(total_return_pct=0., max_drawdown_pct=0., fills=0)
                        daily[key] = pd.DataFrame(dict(date=["2023-01-01", "2023-01-02"], equity=[1_000_000., 1_000_000.]))
        _, gates, _, _ = self.cash.comparisons_and_gates(summaries, daily, protocol)
        self.assertTrue(all(g["status"] == "all_empty_unidentified" for g in gates))

    def test_actual_requires_exact_authorization_and_refuses_existing_output(self):
        self.ready()
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(output=directory, protocol="not-opened", protocol_sha256="invalid", authorization="not-opened")
            with self.assertRaises(FileExistsError):
                self.labels.execute(args)
            args.output = str(Path(directory) / "fresh")
            with self.assertRaises((ValueError, FileNotFoundError)):
                self.labels.execute(args)
            self.assertFalse(Path(args.output).exists(), "reject unauthorized run before materializing actual output")

    def test_modified_source_authorization_rejected_before_native_or_output(self):
        self.ready()
        protocol = TOOLS.parent / "outputs/stage069_settlement_narrow_joint_protocol/protocol.json"
        with tempfile.TemporaryDirectory() as directory:
            output = str((Path(directory) / "never-started").resolve())
            authorization = dict(schema="stage069_exact_root_authorization_v1", authorized_by="root", stage="labels",
                                 exact_source_authorized=True, protocol_sha256=self.kernel.PROTOCOL_SHA,
                                 output=output, source_bundle=self.kernel.source_bundle("labels"), input_bindings={})
            authorization["source_bundle"][0]["sha256"] = "0" * 64
            path = Path(directory) / "bad_authorization.json"
            path.write_text(json.dumps(authorization))
            args = SimpleNamespace(output=output, protocol=str(protocol), protocol_sha256=self.kernel.PROTOCOL_SHA,
                                   authorization=str(path))
            with self.assertRaisesRegex(ValueError, "source_bundle"):
                self.labels.execute(args)
            self.assertEqual(self.labels.ref.NATIVE_QUERIES, 0)
            self.assertFalse(Path(output).exists())

    def test_cash_requires_predictions_to_match_completed071_manifest(self):
        self.assertIsNotNone(self.cash)
        self.assertTrue(hasattr(self.cash, "validate_cash_manifests"), "071 manifest chain must bind actual scores/labels")
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "terminal.json"
            p.write_text(json.dumps(dict(status="completed", exit_code=0, actual_fit_calls_completed=12,
                                         native_source_queries=0, new_cash_accounts=0)))
            binding = self.kernel.ref.file_binding(p)
            labels = dict(path="narrow", bytes=1, sha256="n")
            proxy = dict(path="proxy", bytes=2, sha256="p")
            scores = dict(path="scores", bytes=3, sha256="s")
            narrow = dict(schema="stage070_narrow_labels_v1", status="completed", mode="actual", mother_rows=399252,
                          protocol=dict(sha256=self.kernel.PROTOCOL_SHA), labels_narrow=labels, ohlc_proxy=proxy)
            fit = dict(schema="stage071_settlement_narrow_fit_v1", status="completed", mode="actual",
                       protocol=dict(sha256=self.kernel.PROTOCOL_SHA), actual_fit_calls_completed=12,
                       terminal=binding, predictions=scores, input_bindings=dict(narrow_labels=labels, wide_labels=labels))
            inputs = dict(narrow_labels=labels, wide_labels=labels, predictions=dict(scores, sha256="wrong"))
            with self.assertRaisesRegex(ValueError, "predictions"):
                self.cash.validate_cash_manifests(narrow, fit, inputs)


if __name__ == "__main__":
    unittest.main()
