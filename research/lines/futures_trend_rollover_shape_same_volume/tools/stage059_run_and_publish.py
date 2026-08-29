"""Single reproducible entrypoint for Stage059 calculation and reviewed publication."""

from __future__ import annotations

import stage059_multicycle_review_annotation as annotation
import stage059_stage056_vs_stage037_multicycle as runner


def main() -> None:
    runner.main()
    annotation.main()


if __name__ == "__main__":
    main()
