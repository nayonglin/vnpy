"""Remove the extra count constraint by using the fixed universe capacity."""
from copy import deepcopy
from dataclasses import replace


def universe_capacity_profile(profile, product_count):
    if not isinstance(product_count, int) or product_count < 1:
        raise ValueError('positive_universe_capacity_required')
    spec = profile['spec']
    return {**profile, 'spec': replace(spec,
        capital=replace(spec.capital, max_concurrent_positions=product_count),
        overrides={**spec.overrides, 'max_concurrent_positions': product_count})}


def require_only_position_cap_delta(control, candidate, before, after, paths):
    normalized = deepcopy(candidate)
    for path in paths:
        left, right = control, normalized
        for key in path[:-1]:
            left, right = left[key], right[key]
        key = path[-1]
        if left[key] != before or right[key] != after:
            raise ValueError('position_cap_delta_mismatch:' + '.'.join(path))
        right[key] = left[key]
    if normalized != control:
        raise ValueError('non_position_cap_parameter_changed')
    return True
