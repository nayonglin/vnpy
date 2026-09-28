from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage015_development_label_batch.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage015 development label batch is not implemented"
    spec = importlib.util.spec_from_file_location("stage015_development_label_batch", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_shared_builder_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    suffix = str(id(tmp_path))
    origin = ModuleType(f"stage015_test_origin_{suffix}")
    shared_universe = tmp_path / "shared_universe.csv"
    shared_eligibility = tmp_path / "shared_eligibility.csv"
    shared_universe.write_text("product_vt_symbol\nrb.SHFE\n", encoding="utf-8")
    shared_eligibility.write_text("strategy\nformal\n", encoding="utf-8")
    origin.__dict__.update(
        UNIVERSE_PATH=shared_universe,
        AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH=shared_eligibility,
    )
    exec(
        """
def build_static18_plus_fu_universe():
    UNIVERSE_PATH.write_text("mutated universe\\n", encoding="utf-8")
    return UNIVERSE_PATH

def build_ai_satellite_post_signal_eligibility():
    AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH.write_text(
        "mutated eligibility\\n", encoding="utf-8"
    )
    return AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
""",
        origin.__dict__,
    )

    stage78 = ModuleType(f"stage015_test_stage78_{suffix}")
    stage78.__dict__.update(
        build_static18_plus_fu_universe=(
            origin.build_static18_plus_fu_universe
        ),
        build_ai_satellite_post_signal_eligibility=(
            origin.build_ai_satellite_post_signal_eligibility
        ),
    )
    exec(
        """
def build_official_stage78_overrides():
    return {
        "universe": build_static18_plus_fu_universe(),
        "eligibility": build_ai_satellite_post_signal_eligibility(),
    }
""",
        stage78.__dict__,
    )

    stage777 = ModuleType(f"stage015_test_stage777_{suffix}")
    stage777.__dict__.update(
        build_static18_plus_fu_universe=(
            origin.build_static18_plus_fu_universe
        ),
        build_ai_satellite_post_signal_eligibility=(
            origin.build_ai_satellite_post_signal_eligibility
        ),
    )
    s513 = ModuleType(f"stage015_test_s513_{suffix}")
    s513.__dict__["build_official_stage78_overrides"] = (
        stage78.build_official_stage78_overrides
    )
    exec(
        """
def _c3_overrides():
    return build_official_stage78_overrides()

def _metadata():
    return _c3_overrides()
""",
        s513.__dict__,
    )
    for loaded in (origin, stage78, stage777, s513):
        monkeypatch.setitem(sys.modules, loaded.__name__, loaded)

    stage819 = SimpleNamespace(
        stage813_cfg=SimpleNamespace(stage777_cfg=stage777)
    )
    s901 = SimpleNamespace(
        s847=SimpleNamespace(s825=SimpleNamespace(stage819_cfg=stage819))
    )
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    shutil.copyfile(
        shared_universe, campaign / "official_product_universe.csv"
    )
    shutil.copyfile(
        shared_eligibility,
        campaign / "stage819_profile_eligibility.csv",
    )
    return SimpleNamespace(
        origin=origin,
        stage78=stage78,
        stage777=stage777,
        s513=s513,
        s901=s901,
        campaign=campaign,
        shared_universe=shared_universe,
        shared_eligibility=shared_eligibility,
    )


def test_job_plan_is_complete_development_grid_without_holdout() -> None:
    module = load_module()
    panel = pd.read_csv(module.FEATURE_PANEL)

    jobs = module.build_development_jobs(panel)

    assert (jobs["job_type"] == "main").sum() == 351
    assert (jobs["job_type"] == "A2_sentinel").sum() == 4
    assert len(jobs) == 355
    assert jobs["eval_date"].nunique() == 39
    assert not jobs["split"].eq("sealed_holdout").any()
    main = jobs[jobs["job_type"].eq("main")]
    assert main.groupby("eval_date")["candidate_rank"].apply(list).map(
        lambda values: values == list(range(10, 19))
    ).all()


def test_job_plan_rejects_shape_preserving_month_drift() -> None:
    module = load_module()
    panel = pd.read_csv(module.FEATURE_PANEL)
    panel.loc[panel["eval_date"].eq("2022-04-29"), "eval_date"] = "2022-04-28"

    with pytest.raises(RuntimeError, match="feature_panel_months"):
        module.build_development_jobs(panel)


def test_job_products_match_full_ranking() -> None:
    module = load_module()
    jobs = module.build_development_jobs(pd.read_csv(module.FEATURE_PANEL))
    ranking = pd.read_csv(module.FULL_RANKING)

    gate = module.validate_job_ranking_alignment(jobs, ranking)

    assert gate == {"passed": True, "checked_rows": 351, "mismatch_count": 0}
    jobs.loc[jobs["job_id"].eq("20220531_R12"), "product_vt_symbol"] = "bad.TEST"
    with pytest.raises(RuntimeError, match="feature_panel_ranking_product_mismatch"):
        module.validate_job_ranking_alignment(jobs, ranking)


def test_candidate_eligibility_changes_only_target_rank10_row() -> None:
    module = load_module()
    formal = pd.read_csv(module.FORMAL_ELIGIBILITY)
    ranking = pd.read_csv(module.FULL_RANKING)

    baseline = module.build_candidate_eligibility(
        formal, ranking, eval_date="2022-05-31", candidate_rank=10
    )
    candidate = module.build_candidate_eligibility(
        formal, ranking, eval_date="2022-05-31", candidate_rank=12
    )

    pd.testing.assert_frame_equal(baseline, module.canonical_eligibility(formal), check_dtype=False)
    changed = baseline.ne(candidate).any(axis=1)
    assert changed.sum() == 1
    row = candidate[changed].iloc[0]
    assert row["eval_date"] == "2022-05-31"
    assert row["score_rank"] == 10
    assert row["product_vt_symbol"] == "OI.CZCE"


def test_official_overrides_are_frozen_once_then_reused_without_builder_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    universe = tmp_path / "universe.csv"
    universe.write_text("product_vt_symbol,eligible\nrb.SHFE,1\n", encoding="utf-8")
    formal = tmp_path / "formal.csv"
    formal.write_text(
        "strategy,eval_date,product_vt_symbol,score,score_rank,top_n\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FORMAL_ELIGIBILITY", formal)

    class LiveConfig:
        def __init__(self) -> None:
            self.calls = 0

        def build_official_live_strategy_overrides(self) -> dict[str, object]:
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("mutable official builder called after freeze")
            return {
                "product_universe_csv_path": str(universe),
                "ai_product_pool_eligibility_path": str(formal),
                "ai_product_pool_strategy": module.OFFICIAL_STRATEGY,
                "enable_ai_product_pool_filter": True,
                "account_capital": 150_000.0,
                "c3_capital": 150_000.0,
            }

    live_cfg = LiveConfig()
    frozen = module._freeze_official_overrides(tmp_path, live_cfg)
    frozen_universe = tmp_path / module.OFFICIAL_PRODUCT_UNIVERSE_FILENAME
    first_eligibility = tmp_path / "candidate_a.csv"
    second_eligibility = tmp_path / "candidate_b.csv"
    universe.write_text("", encoding="utf-8")

    first = module._candidate_strategy_overrides(tmp_path, first_eligibility)
    second = module._candidate_strategy_overrides(tmp_path, second_eligibility)

    assert live_cfg.calls == 1
    assert frozen["product_universe_csv_path"] == str(frozen_universe.resolve())
    assert first["product_universe_csv_path"] == str(frozen_universe.resolve())
    assert second["product_universe_csv_path"] == str(frozen_universe.resolve())
    assert frozen_universe.read_text(encoding="utf-8") == (
        "product_vt_symbol,eligible\nrb.SHFE,1\n"
    )
    assert first["ai_product_pool_eligibility_path"] == str(first_eligibility.resolve())
    assert second["ai_product_pool_eligibility_path"] == str(second_eligibility.resolve())
    assert first["ai_product_pool_strategy"] == module.OFFICIAL_STRATEGY
    assert json.loads((tmp_path / "official_overrides.json").read_text()) == frozen


def test_aggregate_identity_rebuild_never_calls_mutable_official_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()

    class LiveConfig:
        OFFICIAL_LIVE_MATERIAL_RELEASE_ID = module.FORMAL_RELEASE_ID
        OFFICIAL_LIVE_AI_ELIGIBILITY_PATH = module.FORMAL_ELIGIBILITY

        def build_official_live_strategy_overrides(self) -> dict[str, object]:
            raise AssertionError("aggregate called mutable official builder")

    s901 = object()

    class Stage004:
        @staticmethod
        def _load_production_modules():
            return LiveConfig(), object(), object(), s901

    observed: dict[str, object] = {}

    def campaign_manifest(
        campaign_dir: Path,
        *,
        s901: object,
        frozen_runtime: dict[str, object],
    ) -> dict[str, object]:
        observed.update(
            campaign_dir=campaign_dir,
            s901=s901,
            frozen_runtime=frozen_runtime,
        )
        return {"stable": True}

    monkeypatch.setattr(module, "_load_stage004", lambda: Stage004())
    monkeypatch.setattr(module, "_campaign_manifest", campaign_manifest)

    result = module._aggregate_identity_after(tmp_path, {"runtime": {"python": "3.11"}})

    assert result == {"stable": True}
    assert observed == {
        "campaign_dir": tmp_path,
        "s901": s901,
        "frozen_runtime": {"python": "3.11"},
    }


def test_product_universe_snapshot_rejects_blank_symbols(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.csv"
    source.write_text("product_vt_symbol,eligible\n,1\n", encoding="utf-8")
    campaign = tmp_path / "campaign"
    campaign.mkdir()

    with pytest.raises(RuntimeError, match="frozen_product_universe_symbols_empty"):
        module._snapshot_product_universe(campaign, source)

    assert not (campaign / module.OFFICIAL_PRODUCT_UNIVERSE_FILENAME).exists()


def test_stage819_profile_overrides_are_campaign_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    shared_universe = tmp_path / "shared_universe.csv"
    shared_universe.write_text(
        "product_vt_symbol,eligible\nrb.SHFE,1\n", encoding="utf-8"
    )
    private_universe = campaign / module.OFFICIAL_PRODUCT_UNIVERSE_FILENAME
    shutil.copyfile(shared_universe, private_universe)
    shared_eligibility = tmp_path / "shared_profile_eligibility.csv"
    shared_eligibility.write_text(
        "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
        "profile_strategy,profile,2022-04-29,rb.SHFE,0.5,1,9\n",
        encoding="utf-8",
    )
    calls = 0

    def profile_builder() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "product_universe_csv_path": str(shared_universe),
            "ai_product_pool_eligibility_path": str(shared_eligibility),
            "ai_product_pool_strategy": "profile_strategy",
            "account_capital": 300_000.0,
        }

    s901 = SimpleNamespace(
        s847=SimpleNamespace(
            s825=SimpleNamespace(
                stage819_cfg=SimpleNamespace(
                    build_official_candidate_stage819_30w_overrides=profile_builder
                )
            )
        )
    )

    frozen = module._freeze_stage819_profile_overrides(campaign, s901)
    shared_universe.write_text("", encoding="utf-8")
    shared_eligibility.write_text("", encoding="utf-8")
    loaded = module._load_frozen_stage819_profile_overrides(campaign)

    assert calls == 1
    assert loaded == frozen
    assert loaded["product_universe_csv_path"] == str(private_universe.resolve())
    private_eligibility = campaign / module.STAGE819_PROFILE_ELIGIBILITY_FILENAME
    assert loaded["ai_product_pool_eligibility_path"] == str(
        private_eligibility.resolve()
    )
    assert "rb.SHFE" in private_eligibility.read_text(encoding="utf-8")


def test_full_live_c9_boundary_never_calls_nested_shared_builders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    shared_calls: list[str] = []

    def shared_universe_builder() -> Path:
        shared_calls.append("universe")
        raise AssertionError("shared universe builder called")

    def shared_eligibility_builder() -> Path:
        shared_calls.append("eligibility")
        raise AssertionError("shared eligibility builder called")

    stage777 = SimpleNamespace(
        build_static18_plus_fu_universe=shared_universe_builder,
        build_ai_satellite_post_signal_eligibility=shared_eligibility_builder,
    )

    def original_profile_builder() -> dict[str, object]:
        stage777.build_static18_plus_fu_universe()
        stage777.build_ai_satellite_post_signal_eligibility()
        return {"source": "mutable"}

    stage819 = SimpleNamespace(
        build_official_candidate_stage819_30w_overrides=original_profile_builder,
        stage813_cfg=SimpleNamespace(stage777_cfg=stage777),
    )

    class S901:
        def __init__(self) -> None:
            self.s847 = SimpleNamespace(
                s825=SimpleNamespace(stage819_cfg=stage819)
            )
            self.build_official_live_strategy_overrides = lambda: {
                "source": "mutable_live"
            }

        def _run_live_c9(self, metadata, start, end):
            profile = (
                self.s847.s825.stage819_cfg
                .build_official_candidate_stage819_30w_overrides()
            )
            live = self.build_official_live_strategy_overrides()
            return profile, live, {"start": start, "end": end}

    s901 = S901()
    original_live_builder = s901.build_official_live_strategy_overrides
    monkeypatch.setattr(
        module,
        "_candidate_strategy_overrides",
        lambda *_args: {"source": "campaign_live"},
    )
    monkeypatch.setattr(
        module,
        "_load_frozen_stage819_profile_overrides",
        lambda *_args: {"source": "campaign_profile"},
    )

    result = module._run_live_c9_with_frozen_builders(
        s901=s901,
        metadata={"vt_symbols": []},
        campaign_dir=tmp_path,
        eligibility_path=tmp_path / "candidate.csv",
        analysis_end=pd.Timestamp("2022-05-31"),
    )

    assert result[0] == {"source": "campaign_profile"}
    assert result[1] == {"source": "campaign_live"}
    assert shared_calls == []
    assert s901.build_official_live_strategy_overrides is original_live_builder
    assert (
        stage819.build_official_candidate_stage819_30w_overrides
        is original_profile_builder
    )
    assert stage777.build_static18_plus_fu_universe is shared_universe_builder
    assert (
        stage777.build_ai_satellite_post_signal_eligibility
        is shared_eligibility_builder
    )


def test_real_metadata_stage78_bindings_redirect_without_shared_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    monkeypatch.setenv("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    _live_cfg, s513, _s827, s901 = (
        module._load_stage004()._load_production_modules()
    )
    stage819 = s901.s847.s825.stage819_cfg
    stage777 = stage819.stage813_cfg.stage777_cfg
    original_universe_builder = stage777.build_static18_plus_fu_universe
    original_eligibility_builder = (
        stage777.build_ai_satellite_post_signal_eligibility
    )
    shared_universe = Path(
        original_universe_builder.__globals__["UNIVERSE_PATH"]
    ).resolve()
    shared_eligibility = Path(
        original_eligibility_builder.__globals__[
            "AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH"
        ]
    ).resolve()
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    shutil.copyfile(
        shared_universe,
        campaign / module.OFFICIAL_PRODUCT_UNIVERSE_FILENAME,
    )
    shutil.copyfile(
        shared_eligibility,
        campaign / module.STAGE819_PROFILE_ELIGIBILITY_FILENAME,
    )

    def identity(path: Path) -> tuple[int, int, int, int, str]:
        stat = path.stat()
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            module._sha256(path),
        )

    before = (identity(shared_universe), identity(shared_eligibility))
    with module._redirect_shared_builder_bindings(
        s513=s513,
        s901=s901,
        campaign_dir=campaign,
    ) as audit:
        metadata = s513._metadata()

    after = (identity(shared_universe), identity(shared_eligibility))
    assert metadata["vt_symbols"]
    assert audit["binding_count"] >= 3
    assert audit["universe_redirect_call_count"] >= 1
    assert audit["eligibility_redirect_call_count"] >= 1
    assert before == after
    assert stage777.build_static18_plus_fu_universe is original_universe_builder
    assert (
        stage777.build_ai_satellite_post_signal_eligibility
        is original_eligibility_builder
    )


@pytest.mark.parametrize(
    ("builder_name", "audit_key"),
    [
        (
            "build_static18_plus_fu_universe",
            "original_universe_builder_call_count",
        ),
        (
            "build_ai_satellite_post_signal_eligibility",
            "original_eligibility_builder_call_count",
        ),
    ],
)
def test_unscanned_original_builder_reference_is_counted_and_blocked(
    builder_name: str,
    audit_key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    graph = fake_shared_builder_graph(tmp_path, monkeypatch)
    hidden_original = getattr(graph.origin, builder_name)

    with pytest.raises(RuntimeError, match="stage015_original_shared_builder"):
        with module._redirect_shared_builder_bindings(
            s513=graph.s513,
            s901=graph.s901,
            campaign_dir=graph.campaign,
        ) as audit:
            hidden_original()

    assert audit["original_shared_builder_guard_installed"] is True
    assert audit[audit_key] == 1
    assert audit["original_shared_builder_call_count"] == 1
    assert getattr(graph.origin, builder_name) is hidden_original


def test_shared_source_identity_change_fails_closed_and_restores_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    graph = fake_shared_builder_graph(tmp_path, monkeypatch)
    original_universe = graph.origin.build_static18_plus_fu_universe

    with pytest.raises(
        RuntimeError, match="stage015_shared_builder_source_identity_changed"
    ):
        with module._redirect_shared_builder_bindings(
            s513=graph.s513,
            s901=graph.s901,
            campaign_dir=graph.campaign,
        ) as audit:
            graph.shared_universe.write_text(
                "tampered without builder call\n", encoding="utf-8"
            )

    assert audit["shared_builder_source_identity_pass"] is False
    assert (
        audit["shared_builder_source_identity_before"]
        != audit["shared_builder_source_identity_after"]
    )
    assert graph.origin.build_static18_plus_fu_universe is original_universe


def test_binding_created_inside_context_is_restored_on_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    graph = fake_shared_builder_graph(tmp_path, monkeypatch)
    original_universe = graph.origin.build_static18_plus_fu_universe
    late_module = ModuleType(f"stage015_test_late_import_{id(tmp_path)}")

    with module._redirect_shared_builder_bindings(
        s513=graph.s513,
        s901=graph.s901,
        campaign_dir=graph.campaign,
    ) as audit:
        monkeypatch.setitem(sys.modules, late_module.__name__, late_module)
        late_module.cached_builder = graph.origin.build_static18_plus_fu_universe
        assert late_module.cached_builder is not original_universe

    assert late_module.cached_builder is original_universe
    assert audit["dynamic_binding_restore_count"] == 1


def test_worker_environment_is_unique_per_job() -> None:
    module = load_module()

    a = module.worker_environment({}, Path("/tmp/stage015"), "20220531_R10")
    b = module.worker_environment({}, Path("/tmp/stage015"), "20220531_R12")

    assert a["TMPDIR"] != b["TMPDIR"]
    assert a["MPLCONFIGDIR"] != b["MPLCONFIGDIR"]


def test_worker_environment_is_unique_across_retries() -> None:
    module = load_module()

    a = module.worker_environment(
        {}, Path("/tmp/stage015"), "20220531_R10", run_id="run_a"
    )
    b = module.worker_environment(
        {}, Path("/tmp/stage015"), "20220531_R10", run_id="run_b"
    )

    assert a["TMPDIR"] != b["TMPDIR"]
    assert a["MPLCONFIGDIR"] != b["MPLCONFIGDIR"]


def test_runtime_normalization_removes_only_expected_job_paths() -> None:
    module = load_module()
    base = {
        "python": "3.11",
        "environment": {
            "TMPDIR": "/tmp/A",
            "MPLCONFIGDIR": "/tmp/A/mpl",
            "STAGE015_CAMPAIGN_DIR": "/campaign",
            "STAGE015_JOB_ID": "A",
            "OMP_NUM_THREADS": "1",
        },
    }
    other = {
        "python": "3.11",
        "environment": {
            "TMPDIR": "/tmp/B",
            "MPLCONFIGDIR": "/tmp/B/mpl",
            "STAGE015_CAMPAIGN_DIR": "/campaign",
            "STAGE015_JOB_ID": "B",
            "OMP_NUM_THREADS": "1",
        },
    }

    assert module.normalized_runtime_sha256(base) == module.normalized_runtime_sha256(other)


def test_worker_and_completed_job_manifests_disable_cross_job_identity_cache() -> None:
    module = load_module()

    assert "file_identity_cache" not in inspect.signature(
        module._worker_execution_manifest
    ).parameters
    assert "file_identity_cache" not in inspect.signature(
        module._validate_completed_job
    ).parameters


@pytest.mark.parametrize("replacement", ["BBBB", "LONGER"])
def test_worker_manifest_rejects_common_input_drift_between_jobs(
    replacement: str,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    common = tmp_path / "common"
    common.write_text("common", encoding="utf-8")
    eligibility_a = tmp_path / "a.csv"
    eligibility_a.write_text("a", encoding="utf-8")
    eligibility_b = tmp_path / "b.csv"
    eligibility_b.write_text("b", encoding="utf-8")
    identity_path = tmp_path / "campaign_identity.json"
    identity_path.write_text("{}", encoding="utf-8")

    def file_identity(path: Path) -> dict[str, object]:
        payload = Path(path).read_bytes()
        import hashlib

        return {
            "path": str(Path(path).resolve()),
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    class Stage007:
        _file_identity = staticmethod(file_identity)

    monkeypatch.setattr(module, "_load_stage007", lambda: Stage007())
    common_identity = file_identity(common)
    files = {
        key: {**common_identity, "path": str(common.resolve())}
        for key in module.WORKER_EXECUTION_EXACT_KEYS
        if key not in {"python_pyvenv_cfg", "python_sitecustomize"}
    }
    files["stage015_eligibility/A.csv"] = file_identity(eligibility_a)
    files["stage015_eligibility/B.csv"] = file_identity(eligibility_b)
    campaign_identity = {"files": files}
    module._worker_execution_manifest(
        tmp_path,
        pd.Series({"eligibility_key": "A"}),
        campaign_identity,
    )
    common.write_text(replacement, encoding="utf-8")

    with pytest.raises(RuntimeError, match="worker_execution_input_drift"):
        module._worker_execution_manifest(
            tmp_path,
            pd.Series({"eligibility_key": "B"}),
            campaign_identity,
        )


def test_final_identity_drift_fails_before_any_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    identity = {"runtime": {"python": "3.11"}, "file_contract_sha256": "a" * 64}
    monkeypatch.setattr(
        module,
        "_aggregate_identity_after",
        lambda *_args, **_kwargs: {
            "runtime": {"python": "3.11"},
            "file_contract_sha256": "b" * 64,
        },
    )

    with pytest.raises(RuntimeError, match="campaign_input_identity_drift_before_publish"):
        module._publish_development_label_outputs(
            tmp_path,
            identity,
            passed=True,
            main=pd.DataFrame({"job_id": ["a"]}),
            reconciliation=pd.DataFrame({"job_id": ["a"]}),
        )

    assert not (tmp_path / "development_labels.csv").exists()
    assert not (tmp_path / "decision.json").exists()


def test_reconciliation_closes_equity_and_daily_pnl_delta() -> None:
    module = load_module()
    baseline_label = {
        "base_equity": 100.0,
        "end_equity": 110.0,
        "future_return": 0.10,
        "future_net_pnl": 10.0,
        "future_slippage": 2.0,
        "future_trade_count": 3.0,
    }
    candidate_label = {
        "base_equity": 100.0,
        "end_equity": 106.0,
        "future_return": 0.06,
        "future_net_pnl": 6.0,
        "future_slippage": 1.0,
        "future_trade_count": 2.0,
    }

    row = module.reconcile_label_pair(baseline_label, candidate_label)

    assert row["end_equity_vs_net_pnl_delta_error"] == 0.0
    assert row["return_vs_equity_delta_error"] == 0.0
    assert row["slippage_delta"] == -1.0
    assert row["trade_count_delta"] == -1.0


def test_monetary_reconciliation_quantizes_real_r14_float_ulps() -> None:
    module = load_module()
    base_equity = 5280488.799999999
    end_equity = 5628573.799999996
    future_net_pnl = 348084.9999999986

    assert abs(end_equity - base_equity - future_net_pnl) > 1e-9
    assert (
        module.monetary_reconciliation_error(
            end_equity=end_equity,
            base_equity=base_equity,
            net_pnl=future_net_pnl,
        )
        == 0.0
    )
    one_micro_yuan_error = module.monetary_reconciliation_error(
        end_equity=end_equity + 0.000001,
        base_equity=base_equity,
        net_pnl=future_net_pnl,
    )
    assert one_micro_yuan_error == 0.000001
    assert one_micro_yuan_error > 1e-9


def test_entry_candidate_boundary_uses_execution_date_and_signal_snapshot() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "date": ["2022-05-31", "2022-06-08", "2022-06-30"],
            "ai_product_pool_signal_date": [
                "2022-04-29",
                "2022-05-31",
                "2022-05-31",
            ],
        }
    )
    target = {
        "entry_candidates": module._period_rows(
            frame,
            after=pd.Timestamp("2022-05-31"),
            through=pd.Timestamp("2022-06-30"),
        )
    }

    gate = module._entry_candidate_boundary_gate(
        {"entry_candidates": frame}, target, pd.Timestamp("2022-05-31")
    )

    assert gate["passed"] is True
    assert gate["predecision_signal_dates"] == ["2022-04-29"]
    assert gate["target_signal_dates"] == ["2022-05-31"]
    target["entry_candidates"].loc[
        target["entry_candidates"].index[0], "ai_product_pool_signal_date"
    ] = None
    missing_gate = module._entry_candidate_boundary_gate(
        {"entry_candidates": frame}, target, pd.Timestamp("2022-05-31")
    )
    assert missing_gate["passed"] is False


def test_exclusive_lock_rejects_concurrent_holder(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "campaign.lock"

    with module._exclusive_lock(path):
        with pytest.raises(RuntimeError, match="lock_already_held"):
            with module._exclusive_lock(path):
                pass


def test_completed_job_requires_fixed_outputs_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    campaign_dir = tmp_path / "campaign_a"
    job = pd.Series(
        {
            "job_id": "20220531_R10",
            "job_type": "main",
            "eval_date": "2022-05-31",
            "next_eval_date": "2022-06-30",
            "candidate_rank": 10,
            "eligibility_key": "20220531_R10",
        }
    )
    directory = campaign_dir / "job_outputs/20220531_R10"
    directory.mkdir(parents=True)
    output_hashes = {}
    for name in module.EXPECTED_JOB_OUTPUT_FILES:
        path = directory / name
        path.write_text("x\n", encoding="utf-8")
        output_hashes[name] = module._sha256(path)
    run_root = module.TMP_ROOT / campaign_dir.name / str(job["job_id"]) / "run_test"
    runtime = {
        "environment": {
            "STAGE015_CAMPAIGN_DIR": str(campaign_dir.resolve()),
            "STAGE015_JOB_ID": str(job["job_id"]),
            "TMPDIR": str((run_root / "tmp").resolve()),
            "MPLCONFIGDIR": str((run_root / "mplconfig").resolve()),
        }
    }
    overrides_path = campaign_dir / module.OFFICIAL_OVERRIDES_FILENAME
    overrides_path.write_text("{}\n", encoding="utf-8")
    universe_path = campaign_dir / module.OFFICIAL_PRODUCT_UNIVERSE_FILENAME
    universe_path.write_text("product_vt_symbol\nrb.SHFE\n", encoding="utf-8")
    profile_overrides_path = (
        campaign_dir / module.STAGE819_PROFILE_OVERRIDES_FILENAME
    )
    profile_overrides_path.write_text("{}\n", encoding="utf-8")
    profile_eligibility_path = (
        campaign_dir / module.STAGE819_PROFILE_ELIGIBILITY_FILENAME
    )
    profile_eligibility_path.write_text("x\n", encoding="utf-8")
    (campaign_dir / "campaign_identity.json").write_text(
        json.dumps({"files": {}}), encoding="utf-8"
    )
    execution_manifest_calls: list[str] = []

    def current_execution_manifest(*args, **kwargs):
        execution_manifest_calls.append(str(args[1]["job_id"]))
        return {
            "file_contract_sha256": "a" * 64,
            "unique_physical_file_count": 7,
        }

    monkeypatch.setattr(module, "_worker_execution_manifest", current_execution_manifest)
    shared_source_identity = {
        "universe": {
            "path": "/shared/universe.csv",
            "dev": 1,
            "inode": 2,
            "size": 3,
            "mtime_ns": 4,
            "ctime_ns": 5,
            "sha256": "b" * 64,
        },
        "eligibility": {
            "path": "/shared/eligibility.csv",
            "dev": 1,
            "inode": 6,
            "size": 7,
            "mtime_ns": 8,
            "ctime_ns": 9,
            "sha256": "c" * 64,
        },
    }
    receipt = {
        **job.to_dict(),
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "campaign_file_contract_sha256": "campaign",
        "input_identity_pass": True,
        "execution_file_contract_sha256": "a" * 64,
        "execution_unique_physical_file_count": 7,
        "official_overrides_source": "campaign_snapshot",
        "official_overrides_sha256": module._sha256(overrides_path),
        "product_universe_sha256": module._sha256(universe_path),
        "stage819_profile_overrides_source": "campaign_snapshot",
        "stage819_profile_overrides_sha256": module._sha256(
            profile_overrides_path
        ),
        "stage819_profile_eligibility_sha256": module._sha256(
            profile_eligibility_path
        ),
        "nested_shared_builder_guard_enabled": True,
        "shared_builder_binding_redirect_count": 6,
        "shared_universe_binding_redirect_count": 3,
        "shared_eligibility_binding_redirect_count": 3,
        "shared_universe_redirect_call_count": 2,
        "shared_eligibility_redirect_call_count": 2,
        "original_shared_builder_guard_installed": True,
        "original_universe_builder_call_count": 0,
        "original_eligibility_builder_call_count": 0,
        "original_shared_builder_call_count": 0,
        "shared_builder_source_identity_pass": True,
        "shared_builder_source_identity_before": shared_source_identity,
        "shared_builder_source_identity_after": shared_source_identity,
        "shared_builder_required_binding_coverage_pass": True,
        "shared_builder_required_bindings": list(
            module.REQUIRED_SHARED_BUILDER_BINDINGS
        ),
        "dynamic_binding_restore_count": 0,
        "shared_builder_redirect_bindings": [f"binding_{index}" for index in range(6)],
        "entry_candidate_boundary_gate": {"passed": True},
        "runtime": runtime,
        "normalized_runtime_sha256": module.normalized_runtime_sha256(runtime),
        "tmpdir": runtime["environment"]["TMPDIR"],
        "mplconfigdir": runtime["environment"]["MPLCONFIGDIR"],
        "output_sha256": output_hashes,
    }
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )

    assert module._validate_completed_job(campaign_dir, job, "campaign") is True
    assert execution_manifest_calls == ["20220531_R10"]
    receipt["shared_builder_source_identity_pass"] = False
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert module._validate_completed_job(campaign_dir, job, "campaign") is False
    receipt["shared_builder_source_identity_pass"] = True
    receipt["original_universe_builder_call_count"] = 1
    receipt["original_shared_builder_call_count"] = 1
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert module._validate_completed_job(campaign_dir, job, "campaign") is False
    receipt["original_universe_builder_call_count"] = 0
    receipt["original_shared_builder_call_count"] = 0
    receipt.pop("tmpdir")
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert module._validate_completed_job(campaign_dir, job, "campaign") is False
    receipt["tmpdir"] = runtime["environment"]["TMPDIR"]
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    copied_campaign = tmp_path / "campaign_b"
    shutil.copytree(campaign_dir, copied_campaign)
    assert module._validate_completed_job(copied_campaign, job, "campaign") is False
    receipt.pop("official_overrides_source")
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert module._validate_completed_job(campaign_dir, job, "campaign") is False
    receipt["official_overrides_source"] = "campaign_snapshot"
    receipt["output_sha256"].pop("label.json")
    (directory / "worker_receipt.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert module._validate_completed_job(campaign_dir, job, "campaign") is False


def test_abandoned_campaign_is_explicitly_rejected(tmp_path: Path) -> None:
    module = load_module()
    (tmp_path / "ABANDONED.json").write_text(
        json.dumps({"reuse_forbidden": True, "status": "abandoned"}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="campaign_reuse_forbidden"):
        module._assert_campaign_reusable(tmp_path)


@pytest.mark.parametrize(
    "legacy_gate",
    [
        {"campaign_reuse_allowed": False},
        {"cross_campaign_job_output_reuse_allowed": False},
    ],
)
def test_legacy_failure_receipt_reuse_denials_are_rejected(
    legacy_gate: dict[str, bool], tmp_path: Path
) -> None:
    module = load_module()
    (tmp_path / "failure_receipt.json").write_text(
        json.dumps(legacy_gate), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="campaign_reuse_forbidden"):
        module._assert_campaign_reusable(tmp_path)


def test_prepare_failure_leaves_reuse_forbidden_tombstone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    runtime_database = tmp_path / "database.db"
    runtime_database.write_bytes(b"db")
    review = tmp_path / "review.md"
    review.write_text("PASS_WITH_P2 ALLOW_COVERAGE_STUDY_ONLY", encoding="utf-8")
    feature_contract = tmp_path / "feature_contract.json"
    feature_contract.write_text(
        json.dumps({"decision": "stage014_nine_feature_prelabel_contract_frozen"}),
        encoding="utf-8",
    )
    feature_panel = tmp_path / "feature_panel.csv"
    feature_panel.write_text("eval_date\n2022-04-29\n", encoding="utf-8")
    formal_path = tmp_path / "formal.csv"
    formal = pd.DataFrame(
        {
            "strategy": [module.OFFICIAL_STRATEGY],
            "score_type": ["formal_probability"],
            "eval_date": ["2022-04-29"],
            "product_vt_symbol": ["rb.SHFE"],
            "score": [0.5],
            "score_rank": [10],
            "top_n": [10],
        }
    )
    formal.to_csv(formal_path, index=False)
    ranking_path = tmp_path / "ranking.csv"
    formal.to_csv(ranking_path, index=False)
    base_out = tmp_path / "campaigns"
    jobs = pd.DataFrame(
        {
            "job_id": ["20220429_R10"],
            "job_type": ["main"],
            "split": ["development"],
            "eval_date": ["2022-04-29"],
            "next_eval_date": ["2022-05-31"],
            "candidate_rank": [10],
            "product_vt_symbol": ["rb.SHFE"],
            "eligibility_key": ["20220429_R10"],
        }
    )
    monkeypatch.setattr(module, "RUNTIME_DATABASE", runtime_database)
    monkeypatch.setattr(module, "STAGE012_REVIEW", review)
    monkeypatch.setattr(module, "FEATURE_CONTRACT", feature_contract)
    monkeypatch.setattr(module, "FEATURE_PANEL", feature_panel)
    monkeypatch.setattr(module, "FORMAL_ELIGIBILITY", formal_path)
    monkeypatch.setattr(module, "FULL_RANKING", ranking_path)
    monkeypatch.setattr(module, "BASE_OUT", base_out)
    monkeypatch.setattr(module, "build_development_jobs", lambda _panel: jobs)
    monkeypatch.setattr(
        module,
        "validate_job_ranking_alignment",
        lambda _jobs, _ranking: {"passed": True},
    )
    monkeypatch.setattr(
        module,
        "build_candidate_eligibility",
        lambda *_args, **_kwargs: module.canonical_eligibility(formal),
    )

    with pytest.raises(RuntimeError, match="campaign_eligibility_audit_failed"):
        module._prepare_campaign()

    campaigns = list(base_out.glob("campaign_*"))
    assert len(campaigns) == 1
    tombstone = json.loads(
        (campaigns[0] / "ABANDONED.json").read_text(encoding="utf-8")
    )
    assert tombstone["reuse_forbidden"] is True
    assert tombstone["status"] == "prepare_failed"
