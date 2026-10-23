"""Allow both existing weekly 3MA short cross cases; all other K rules inherit."""
from stage014_no_macd import no_macd_weekly_strategy_class


def short_case2_weekly_strategy_class(base, weeks):
    wrapped = no_macd_weekly_strategy_class(base, weeks)

    class ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy(wrapped):
        research_short_case2_enabled = True

        def _can_open_short_signal(self, signal):
            return signal in ("short_case1a", "short_case2")

    return ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy
