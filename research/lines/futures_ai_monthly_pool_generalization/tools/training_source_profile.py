"""Research-only source overrides. No production configuration import."""
from pathlib import Path
import json

PROFILE_PATH = Path(__file__).resolve().parents[1] / "config/training_source_v1.json"


def apply_training_overrides(base):
    profile = json.loads(PROFILE_PATH.read_text())
    if profile["scope"] != "research_training_source_only" or profile["production_change_authorized"]:
        raise ValueError("training source scope violation")
    if profile["strategy_overrides"] != {"enable_stage847_half_r_stop_retry": False}:
        raise ValueError("unexpected training source overrides")
    return {**base, **profile["strategy_overrides"]}
