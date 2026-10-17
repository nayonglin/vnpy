"""Single entry point: clean frozen sources, then quarantine disputed prices.

No downloading, source/production database edits, financial backtests or models.
Existing output makes the builder fail closed instead of silently rerunning.
"""
from stage266_clean_daily import main as build
from stage266_finalize_price_conflicts import main as finalize
from stage266_legacy_db_price_overlap import main as compare_legacy
from stage266_finalize_legacy_price_conflicts import main as finalize_legacy


if __name__=='__main__':
    build()
    finalize()
    compare_legacy()
    finalize_legacy()
