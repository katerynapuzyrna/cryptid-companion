"""Dataclasses for Deduction mode state and simulation snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModeState:
    """Saved non-simulation state for Build or Select mode to keep them independent."""
    map_data: dict[str, Any] | None = None
    players: int = 3
    advanced: bool = False
    select_custom_maps: bool = False
    rule: str = ""
    names: list[str] = field(default_factory=lambda: [""] * 5)
    colors: list[str] = field(default_factory=lambda: [""] * 5)
    in_simulation: bool = False
    selected_map_data: dict[str, Any] | None = None
    highlight_valid_spaces: bool = True
    freeze_map_checked: bool = False
    freeze_map_enabled: bool = False


@dataclass
class SimulationSession:
    """Full snapshot of a running simulation (map, solver outputs, chips, highlights)."""
    map_data: dict[str, Any]
    players: int
    advanced: bool
    rule: str
    names: list[str]
    colors: list[str]

    rule_combos: list[tuple[tuple[str, ...], tuple[int, int]]]
    deactivated: set[int]
    impossible_per_player: list[set[str]]
    all_conds: Any
    clues_per_player: list[set[str]]
    initial_clues_per_player: list[set[str]]
    simulation_players: int
    first_player_rule: str

    highlight_valid_spaces: bool
    chip_slots: list[tuple[int, int, int, str, str]]
