from pathlib import Path

import pytest

from stage003_reversal_recap import LINE, load_bundle, write_recap


def test_frozen_bundle_pairs_all_56_and_links_original_close():
    bundle = load_bundle(LINE / "outputs")
    assert len(bundle.episodes) == 56
    assert bundle.episodes.realized_pnl.sum() == pytest.approx(-35305)
    assert (bundle.decisions.original_position_net < 0).all()
    assert bundle.closed.attrs["residual_open_positions"] == []


def test_incomplete_source_and_existing_destination_fail_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_bundle(tmp_path)
    with pytest.raises(FileExistsError):
        write_recap(None, Path(tmp_path))
