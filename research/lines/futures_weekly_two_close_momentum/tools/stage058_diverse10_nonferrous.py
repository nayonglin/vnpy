"""Add admitted aluminium and nickel alternatives to the infeasible S21 selection."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import stage057_diverse10 as core

LINE = core.LINE
DESIGN = LINE / "stages/20261105_1307_stage058_nonferrous_extension_design.md"
CORE_SHA = "be20c0acaf6ebad7e5efdd6862b367aa89b24f531ca78e8cf640f501dbb5b547"
PRIOR = LINE / "outputs/stage057_diverse10_20261104"
CATEGORIES = {**core.CATEGORIES, "有色金属": ["cu.SHFE", "al.SHFE", "ni.SHFE"]}


def run(output):
    parent = core.parent
    if parent.base.portfolio.sha(Path(core.__file__)) != CORE_SHA:
        raise ValueError("original correlation source changed")
    prior = parent.prior.read_json(PRIOR / "selection.json")
    if prior["status"] != "NO_FEASIBLE_SELECTION" or prior["eligible_combinations"] != 0:
        raise ValueError("original infeasibility evidence changed")
    parent.base.verify_manifest(PRIOR, parent.base.portfolio.sha(PRIOR / "SHA256SUMS"))
    loaded = parent.base.load(parent.base.MARKET, control=False)
    selected_universe = sorted({p for values in CATEGORIES.values() for p in values})
    if len(selected_universe) != 23 or not set(selected_universe).issubset(loaded[0]):
        raise ValueError("extension is not the admitted parent pool plus aluminium and nickel")
    market = (selected_universe, *loaded[1:])
    if market[1][-1] != "2026-11-03":
        raise ValueError("common admitted cutoff changed")
    daily, weekly, evidence = core.returns(market)
    pairs = core.pair_statistics(daily, weekly)
    with patch.object(core, "CATEGORIES", CATEGORIES):
        choices = core.candidates(pairs)
    output.mkdir(parents=True)
    daily.to_csv(output / "daily_log_returns.csv")
    weekly.to_csv(output / "weekly_log_returns.csv")
    evidence.to_csv(output / "return_evidence.csv", index=False)
    pairs.to_csv(output / "pairwise.csv", index=False)
    choices.to_csv(output / "candidates.csv", index=False)
    valid = choices.loc[choices.allowed]
    selected = json.loads(valid.iloc[0].products) if not valid.empty else []
    selected_pairs = pairs.loc[pairs.left.isin(selected) & pairs.right.isin(selected)]
    selected_pairs.to_csv(output / "selected_pairs.csv", index=False)
    if selected and (len(selected) != 10 or len(selected_pairs) != 45 or not selected_pairs.allowed.all()):
        raise ValueError("selected universe violates the fixed constraints")
    receipt = dict(
        schema="stage058_diverse10_nonferrous_extension_v1", cutoff=market[1][-1], categories=CATEGORIES,
        selected_by_category={key: next((p for p in values if p in selected), None)
                              for key, values in CATEGORIES.items()}, selected=selected,
        selection_rule=prior["selection_rule"], windows=core.WINDOWS, correlation_limit=core.LIMIT,
        attempted_combinations=len(choices), eligible_combinations=len(valid),
        status="SELECTED_FOR_RESEARCH" if selected else "NO_FEASIBLE_SELECTION",
        maximum_pair_score=float(valid.iloc[0].max_correlation) if selected else None,
        mean_pair_score=float(valid.iloc[0].mean_pair_score) if selected else None,
        data_windows={
            name: dict(first=sample.index[0], last=sample.index[-1], observations=len(sample))
            for name, (length, _) in core.WINDOWS.items()
            for sample in [(weekly if name.startswith("weekly") else daily).iloc[-length:]]
        },
        original_infeasible_manifest_sha256=parent.base.portfolio.sha(PRIOR / "SHA256SUMS"),
        core_entrypoint_sha256=CORE_SHA, design_sha256=parent.base.portfolio.sha(DESIGN),
        entrypoint_sha256=parent.base.portfolio.sha(Path(__file__)),
        loader_sha256=parent.base.portfolio.sha(Path(parent.base.load.__code__.co_filename)),
        market_sha256={str(p): digest for p, digest in market[-1].items()},
    )
    (output / "selection.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    parent.base.write_checksums(output, (p for p in output.rglob("*") if p.is_file()))
    print({k: receipt[k] for k in ("cutoff", "status", "selected_by_category", "eligible_combinations",
                                  "maximum_pair_score", "mean_pair_score")})
    print(selected_pairs.sort_values("score", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
