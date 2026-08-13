import numpy as np
from scipy.ndimage import convolve
from dataclasses import dataclass
from typing import Union

# --------------------------
# Conditions helpers
# --------------------------
def one_of_two_terrains(terrain1, terrain2, current_map):
    T = np.zeros_like(current_map, dtype=int)
    for y in range(current_map.shape[0]):
        for x in range(current_map.shape[1]):
            if terrain1 in current_map[y, x] or terrain2 in current_map[y, x]:
                T[y, x] = 1
    return T

def within_many_spaces_of_entity(num_of_spaces: int, entities: Union[str, list[str]], current_map: np.ndarray):
    rows, cols = current_map.shape
    if isinstance(entities, str):
        entities = [entities]

    entity_mask = np.zeros_like(current_map, dtype=bool)
    for e in entities:
        entity_mask |= (np.char.find(current_map, e) >= 0)
    entity_mask = entity_mask.astype(int)

    if num_of_spaces == 1:
        even_kernel = np.array([[0, 1, 0],
                                [1, 1, 1],
                                [1, 1, 1]])
        odd_kernel = np.array([[1, 1, 1],
                               [1, 1, 1],
                               [0, 1, 0]])
    elif num_of_spaces == 2:
        even_kernel = np.array([[0, 0, 1, 0, 0],
                                [1, 1, 1, 1, 1],
                                [1, 1, 1, 1, 1],
                                [1, 1, 1, 1, 1],
                                [0, 1, 1, 1, 0]])
        odd_kernel = np.array([[0, 1, 1, 1, 0],
                               [1, 1, 1, 1, 1],
                               [1, 1, 1, 1, 1],
                               [1, 1, 1, 1, 1],
                               [0, 0, 1, 0, 0]])
    elif num_of_spaces == 3:
        odd_kernel = np.array([[0, 0, 1, 1, 1, 0, 0],
                                [1, 1, 1, 1, 1, 1, 1],
                                [1, 1, 1, 1, 1, 1, 1],
                                [1, 1, 1, 1, 1, 1, 1],
                                [1, 1, 1, 1, 1, 1, 1],
                                [0, 1, 1, 1, 1, 1, 0],
                                [0, 0, 0, 1, 0, 0, 0]])
        even_kernel = np.array([[0, 0, 0, 1, 0, 0, 0],
                               [0, 1, 1, 1, 1, 1, 0],
                               [1, 1, 1, 1, 1, 1, 1],
                               [1, 1, 1, 1, 1, 1, 1],
                               [1, 1, 1, 1, 1, 1, 1],
                               [1, 1, 1, 1, 1, 1, 1],
                               [0, 0, 1, 1, 1, 0, 0]])
    else:
        raise ValueError("num_of_spaces must be 1, 2, or 3")

    even_result = convolve(entity_mask, even_kernel, mode="constant", cval=0) > 0
    odd_result = convolve(entity_mask, odd_kernel, mode="constant", cval=0) > 0

    result = np.zeros((rows, cols), dtype=int)
    for x in range(cols):
        result[:, x] = (even_result[:, x] if x % 2 == 0 else odd_result[:, x]).astype(int)
    return result

def _negate_mask(mask: np.ndarray) -> np.ndarray:
    """Invert a 0/1 (or boolean) mask to 0/1 int mask."""
    if mask.dtype == bool:
        return (~mask).astype(int)
    return (mask == 0).astype(int)

# --------------------------
# Public API
# --------------------------
def all_condition_labels(advanced_mode: bool = False) -> list[str]:
    """
    Order:
      - all positive rules first
      - then all 'Not ...' rules (only in advanced mode)
    Basic mode excludes:
      - all 'Not ...'
      - all rules containing 'black'
    """
    labels: list[str] = []
    not_labels: list[str] = []

    pairs = [
        ("forest", "desert"), ("forest", "water"), ("forest", "swamp"), ("forest", "mountain"),
        ("desert", "water"), ("desert", "swamp"), ("desert", "mountain"),
        ("water", "swamp"), ("water", "mountain"),
        ("swamp", "mountain"),
    ]
    for a, b in pairs:
        labels.append(f"On {a} or {b}")
        not_labels.append(f"Not on {a} or {b}")

    for t in ["forest", "desert", "swamp", "water", "mountain"]:
        labels.append(f"Within one space of {t}")
        not_labels.append(f"Not within one space of {t}")

    labels.append("Within one space of cougar or bear territory")
    not_labels.append("Not within one space of cougar or bear territory")

    labels.append("Within two spaces of a standing stone")
    not_labels.append("Not within two spaces of a standing stone")

    labels.append("Within two spaces of an abandoned shack")
    not_labels.append("Not within two spaces of an abandoned shack")

    labels.append("Within two spaces of cougar territory")
    not_labels.append("Not within two spaces of cougar territory")

    labels.append("Within two spaces of bear territory")
    not_labels.append("Not within two spaces of bear territory")

    colors = ["white", "blue", "green", "black"] if advanced_mode else ["white", "blue", "green"]
    for c in colors:
        labels.append(f"Within three spaces of a {c} structure")
        not_labels.append(f"Not within three spaces of a {c} structure")

    return labels + (not_labels if advanced_mode else [])


@dataclass
class ConditionsGrid:
    """
    Bitmask representation of all conditions.
    Each hex stores an integer: bit i = 1 iff condition i is satisfied at that hex.
    """

    grid: np.ndarray  # uint64, shape (rows, cols)
    labels: list[str]

    def __post_init__(self) -> None:
        self._label_to_index = {label: i for i, label in enumerate(self.labels)}

    def __contains__(self, label: str) -> bool:
        return label in self._label_to_index

    def selection_mask(self, rule_labels: list[str]) -> int:
        """Build bitmask for the given rules. Raises KeyError if any label unknown."""
        mask = 0
        for label in rule_labels:
            mask |= 1 << self._label_to_index[label]
        return mask

    def intersection_count(self, rule_labels: list[str]) -> int:
        """Count hexes where all selected rules are satisfied."""
        sel = self.selection_mask(rule_labels)
        return int(np.sum((self.grid & sel) == sel))

    def intersection_hexes(self, rule_labels: list[str]) -> set[tuple[int, int]]:
        """Return set of (y, x) hex coordinates where all selected rules are satisfied."""
        sel = self.selection_mask(rule_labels)
        matches = (self.grid & sel) == sel
        return set(map(tuple, np.argwhere(matches)))

    def rules_true_at_hex(self, y: int, x: int) -> set[str]:
        """Return set of rule labels that are true at hex (y, x)."""
        rows, cols = self.grid.shape
        if not (0 <= y < rows and 0 <= x < cols):
            return set()
        bits = int(self.grid[y, x])
        result: set[str] = set()
        for i, label in enumerate(self.labels):
            if (bits >> i) & 1:
                result.add(label)
        return result


def compute_all_conditions(current_map: np.ndarray, advanced_mode: bool = False) -> ConditionsGrid:
    """
    Basic mode computes ONLY:
      - positive rules
      - excludes 'black' rules
      - excludes all 'Not ...' rules

    Advanced mode computes:
      - all positive rules (including 'black')
      - and all 'Not ...' rules (added after positives)

    Returns ConditionsGrid: bitmask array + ordered labels for fast intersection queries.
    """
    labels = all_condition_labels(advanced_mode)
    terrain_pairs = [
        ("forest", "desert"), ("forest", "water"), ("forest", "swamp"), ("forest", "mountain"),
        ("desert", "water"), ("desert", "swamp"), ("desert", "mountain"),
        ("water", "swamp"), ("water", "mountain"),
        ("swamp", "mountain"),
    ]
    conditions: dict[str, np.ndarray] = {}

    # --- positives ---
    for t1, t2 in terrain_pairs:
        key = f"On {t1} or {t2}"
        conditions[key] = one_of_two_terrains(t1, t2, current_map)

    for t in ["forest", "desert", "swamp", "water", "mountain"]:
        key = f"Within one space of {t}"
        conditions[key] = within_many_spaces_of_entity(1, t, current_map)

    conditions["Within one space of cougar or bear territory"] = within_many_spaces_of_entity(
        1, ["cougar", "bear"], current_map
    )

    # Keep keys identical to UI labels (see all_condition_labels)
    conditions["Within two spaces of a standing stone"] = within_many_spaces_of_entity(2, "standingstone", current_map)
    conditions["Within two spaces of an abandoned shack"] = within_many_spaces_of_entity(2, "abandonedshack", current_map)
    conditions["Within two spaces of cougar territory"] = within_many_spaces_of_entity(2, "cougar", current_map)
    conditions["Within two spaces of bear territory"] = within_many_spaces_of_entity(2, "bear", current_map)

    colors = ["white", "blue", "green", "black"] if advanced_mode else ["white", "blue", "green"]
    for color in colors:
        key = f"Within three spaces of a {color} structure"
        conditions[key] = within_many_spaces_of_entity(3, color, current_map)

    # --- NOT rules only in advanced ---
    if advanced_mode:
        not_conditions: dict[str, np.ndarray] = {}

        for t1, t2 in terrain_pairs:
            base = conditions[f"On {t1} or {t2}"]
            not_conditions[f"Not on {t1} or {t2}"] = _negate_mask(base)

        for t in ["forest", "desert", "swamp", "water", "mountain"]:
            base = conditions[f"Within one space of {t}"]
            not_conditions[f"Not within one space of {t}"] = _negate_mask(base)

        base = conditions["Within one space of cougar or bear territory"]
        not_conditions["Not within one space of cougar or bear territory"] = _negate_mask(base)

        base = conditions["Within two spaces of a standing stone"]
        not_conditions["Not within two spaces of a standing stone"] = _negate_mask(base)

        base = conditions["Within two spaces of an abandoned shack"]
        not_conditions["Not within two spaces of an abandoned shack"] = _negate_mask(base)

        base = conditions["Within two spaces of cougar territory"]
        not_conditions["Not within two spaces of cougar territory"] = _negate_mask(base)

        base = conditions["Within two spaces of bear territory"]
        not_conditions["Not within two spaces of bear territory"] = _negate_mask(base)

        for color in colors:
            base = conditions[f"Within three spaces of a {color} structure"]
            not_conditions[f"Not within three spaces of a {color} structure"] = _negate_mask(base)

        # keep insertion order: positives first, then NOTs
        conditions.update(not_conditions)

    # Pack into single uint64 bitmask grid (labels order must match all_condition_labels)
    rows, cols = current_map.shape
    grid = np.zeros((rows, cols), dtype=np.uint64)
    for i, label in enumerate(labels):
        mask = conditions[label]
        grid |= (np.asarray(mask, dtype=np.uint64) & 1) << i

    return ConditionsGrid(grid=grid, labels=labels)
