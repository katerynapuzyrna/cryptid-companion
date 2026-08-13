"""Pre-compute rule combinations with exactly one intersection (deduction mode)."""
from __future__ import annotations

import itertools
import random
from typing import Callable, List, Optional, Tuple

import numpy as np

from logic.conditions import compute_all_conditions


def find_rule_combinations_with_exactly_one_intersection(
    current_map: np.ndarray,
    players: int,
    rule_labels: List[str],
    advanced_mode: bool = False,
    fixed_first_rule: str | None = None,
    yield_callback: Callable[[], None] | None = None,
) -> List[Tuple[Tuple[str, ...], Tuple[int, int]]]:
    """
    Find unique sets of N rules with exactly one intersection hex (order doesn't matter),
    then return all permutations of each set with the exact target hex for each.

    Args:
        current_map: Board state from MapBuilder.build_current_map()
        players: Number of players (3, 4, or 5)
        rule_labels: All rule labels from all_condition_labels(advanced_mode)
        advanced_mode: Whether to include advanced rules
        fixed_first_rule: If set, the 1st player's rule is fixed; only other players' rules
            are varied. Used for deduction mode. Returns [] if fixed_first_rule is empty.

    Returns:
        List of ((rule1, rule2, ..., ruleN), (y, x)) where (y, x) is the target hex
        in big-map coordinates. Each valid set appears as all its permutations.
        When fixed_first_rule is set, first column is always fixed_first_rule.
    """
    if players not in (3, 4, 5):
        return []
    all_conds = compute_all_conditions(current_map, advanced_mode=advanced_mode)
    valid_labels = [r for r in rule_labels if r in all_conds]
    if not advanced_mode:
        valid_labels = [r for r in valid_labels if not r.startswith("Not ")]
    if not valid_labels:
        return []

    if fixed_first_rule:
        fixed_first_rule = fixed_first_rule.strip()
        if not fixed_first_rule or fixed_first_rule not in all_conds:
            return []
        # 1st player rule is fixed; vary the other (players-1) rules only
        others_count = players - 1
        other_labels = [r for r in valid_labels if r != fixed_first_rule]
        if len(other_labels) < others_count:
            return []
        # Pairs involving fixed rule (for incompatible check)
        incompatible_pairs: set[frozenset[str]] = set()
        for r in other_labels:
            if all_conds.intersection_count([fixed_first_rule, r]) == 0:
                incompatible_pairs.add(frozenset({fixed_first_rule, r}))
        for r1, r2 in itertools.combinations(other_labels, 2):
            if all_conds.intersection_count([r1, r2]) == 0:
                incompatible_pairs.add(frozenset({r1, r2}))

        result: List[Tuple[Tuple[str, ...], Tuple[int, int]]] = []
        for idx, other_combo in enumerate(itertools.combinations(other_labels, others_count)):
            if yield_callback is not None and idx > 0 and idx % 80 == 0:
                yield_callback()
            if any(frozenset({a, b}) in incompatible_pairs for a, b in itertools.combinations(other_combo, 2)):
                continue
            if any(frozenset({fixed_first_rule, r}) in incompatible_pairs for r in other_combo):
                continue
            combo = (fixed_first_rule,) + other_combo
            try:
                hexes = all_conds.intersection_hexes(list(combo))
            except KeyError:
                continue
            if len(hexes) == 1:
                target_hex = next(iter(hexes))
                for other_perm in itertools.permutations(other_combo):
                    result.append(((fixed_first_rule,) + other_perm, target_hex))
        return result

    # No fixed rule: original behavior
    incompatible_pairs = set()
    for r1, r2 in itertools.combinations(valid_labels, 2):
        if all_conds.intersection_count([r1, r2]) == 0:
            incompatible_pairs.add(frozenset({r1, r2}))

    result: List[Tuple[Tuple[str, ...], Tuple[int, int]]] = []
    for idx, combo in enumerate(itertools.combinations(valid_labels, players)):
        if yield_callback is not None and idx > 0 and idx % 80 == 0:
            yield_callback()
        if any(frozenset({a, b}) in incompatible_pairs for a, b in itertools.combinations(combo, 2)):
            continue
        try:
            hexes = all_conds.intersection_hexes(list(combo))
        except KeyError:
            continue
        if len(hexes) == 1:
            target_hex = next(iter(hexes))
            for perm in itertools.permutations(combo):
                result.append((perm, target_hex))
    return result


def find_first_rule_combination_with_exactly_one_intersection(
    current_map: np.ndarray,
    players: int,
    rule_labels: List[str],
    advanced_mode: bool = False,
    *,
    rng: random.Random | None = None,
) -> Optional[Tuple[Tuple[str, ...], Tuple[int, int]]]:
    """
    Return the first valid (rules, target_hex) for hotseat custom maps.

    Shuffles labels (and player assignment) so successive calls vary without
    enumerating every combination. Stops as soon as one valid set is found.
    """
    if players not in (3, 4, 5):
        return None
    all_conds = compute_all_conditions(current_map, advanced_mode=advanced_mode)
    valid_labels = [r for r in rule_labels if r in all_conds]
    if not advanced_mode:
        valid_labels = [r for r in valid_labels if not r.startswith("Not ")]
    if len(valid_labels) < players:
        return None

    shuffle_rng = rng if rng is not None else random
    labels = list(valid_labels)
    shuffle_rng.shuffle(labels)

    incompatible_pairs: set[frozenset[str]] = set()
    for r1, r2 in itertools.combinations(labels, 2):
        if all_conds.intersection_count([r1, r2]) == 0:
            incompatible_pairs.add(frozenset({r1, r2}))

    for combo in itertools.combinations(labels, players):
        if any(frozenset({a, b}) in incompatible_pairs for a, b in itertools.combinations(combo, 2)):
            continue
        try:
            hexes = all_conds.intersection_hexes(list(combo))
        except KeyError:
            continue
        if len(hexes) == 1:
            target_hex = next(iter(hexes))
            assigned = list(combo)
            shuffle_rng.shuffle(assigned)
            return (tuple(assigned), target_hex)
    return None


def distinct_valid_clues_per_player(
    combos: List[Tuple[Tuple[str, ...], Tuple[int, int]]],
    players: int,
    deactivated_indices: set[int] | None = None,
) -> List[set[str]]:
    """
    Extract distinct rule labels for each player from rule combinations.
    combos: list of ((rule1, rule2, ...), target_hex)
    deactivated_indices: optional set of combo indices to exclude (for chip-based filtering)
    Returns list of N sets: per-player distinct valid clues.
    """
    result: List[set[str]] = [set() for _ in range(players)]
    deactivated = deactivated_indices or set()
    for i, (combo, _) in enumerate(combos):
        if i in deactivated:
            continue
        for p in range(min(players, len(combo))):
            result[p].add(combo[p])
    return result
