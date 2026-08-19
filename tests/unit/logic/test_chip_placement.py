"""Unit tests for logic.chip_placement."""
from __future__ import annotations

from logic.chip_placement import (
    OccupiedChip,
    PlaceDecision,
    clue_holds_at_hex,
    evaluate_chip_placement,
    match_clue_to_grid,
    occupied_from_item,
)


class _Grid:
    def __init__(self, labels: list[str], true_at: set[str] | None = None) -> None:
        self.labels = labels
        self._true = set(true_at or [])

    def __contains__(self, label: str) -> bool:
        return label in self.labels

    def rules_true_at_hex(self, y: int, x: int) -> set[str]:
        return set(self._true)


def _square(color: str = "#111111") -> OccupiedChip:
    return OccupiedChip("square", color.lower())


def _circle(color: str = "#222222") -> OccupiedChip:
    return OccupiedChip("circle", color.lower())


RED = "#ff0000"
BLUE = "#0000ff"


def test_match_clue_to_grid_strip_and_case() -> None:
    grid = _Grid(["On forest or desert"])
    assert match_clue_to_grid("On forest or desert", grid) == "On forest or desert"
    assert match_clue_to_grid("  On forest or desert  ", grid) == "On forest or desert"
    assert match_clue_to_grid("on forest or desert", grid) == "On forest or desert"
    assert match_clue_to_grid("missing", grid) is None
    assert match_clue_to_grid("", grid) is None


def test_clue_holds_at_hex() -> None:
    grid = _Grid(["On forest or desert"], true_at={"On forest or desert"})
    assert clue_holds_at_hex("On forest or desert", grid, 0, 0) is True
    grid_false = _Grid(["On forest or desert"], true_at=set())
    assert clue_holds_at_hex("On forest or desert", grid_false, 0, 0) is False
    assert clue_holds_at_hex("unknown", grid, 0, 0) is None


def test_occupied_from_item_question_and_shapes() -> None:
    class _Chip:
        def __init__(self, shape: str, color: str, question: bool = False) -> None:
            self.shape_kind = shape
            self.fill_color = color
            self._question_mark = question

    assert occupied_from_item(_Chip("circle", "#ABC", True)) == OccupiedChip(
        "question", "#abc"
    )
    assert occupied_from_item(_Chip("square", "#FF0000")) == OccupiedChip(
        "square", "#ff0000"
    )
    assert occupied_from_item(_Chip("circle", "#00FF00")) == OccupiedChip(
        "circle", "#00ff00"
    )


def test_square_requires_clue_false() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=(),
            clue_holds=False,
        )
        is PlaceDecision.ALLOW
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=(),
            clue_holds=True,
        )
        is PlaceDecision.REJECT
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=(),
            clue_holds=None,
        )
        is PlaceDecision.REJECT
    )


def test_square_rejects_existing_square() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=(_square(BLUE),),
            clue_holds=False,
        )
        is PlaceDecision.REJECT
    )


def test_square_rejects_own_circle_allows_other_circle() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=(_circle(RED),),
            clue_holds=False,
        )
        is PlaceDecision.REJECT
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=(_circle(BLUE),),
            clue_holds=False,
        )
        is PlaceDecision.ALLOW
    )


def test_question_and_search_reject_hex_with_square() -> None:
    occupied = (_square(BLUE),)
    assert (
        evaluate_chip_placement(
            incoming_shape="question",
            incoming_color="#98a4ac",
            occupied=occupied,
            clue_holds=None,
        )
        is PlaceDecision.REJECT
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=occupied,
            clue_holds=True,
            allow_search_reuse=True,
        )
        is PlaceDecision.REJECT
    )


def test_search_requires_clue_true() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=(),
            clue_holds=True,
        )
        is PlaceDecision.ALLOW
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=(),
            clue_holds=False,
        )
        is PlaceDecision.REJECT
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=(),
            clue_holds=None,
        )
        is PlaceDecision.REJECT
    )


def test_question_has_no_clue_check() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="question",
            incoming_color="#98a4ac",
            occupied=(),
            clue_holds=None,
        )
        is PlaceDecision.ALLOW
    )


def test_search_reuses_own_circle_when_allowed() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=(_circle(RED),),
            clue_holds=True,
            allow_search_reuse=True,
        )
        is PlaceDecision.REUSE_CIRCLE
    )
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=(_circle(RED),),
            clue_holds=True,
            allow_search_reuse=False,
        )
        is PlaceDecision.REJECT
    )


def test_search_reuse_allowed_on_full_hex() -> None:
    occupied = tuple(_circle(f"#00000{i}") for i in range(4))
    # Own color already present as first chip.
    occupied = (_circle(RED),) + occupied[1:]
    assert (
        evaluate_chip_placement(
            incoming_shape="circle",
            incoming_color=RED,
            occupied=occupied,
            clue_holds=True,
            allow_search_reuse=True,
        )
        is PlaceDecision.REUSE_CIRCLE
    )


def test_question_allowed_on_other_player_circle() -> None:
    assert (
        evaluate_chip_placement(
            incoming_shape="question",
            incoming_color="#98a4ac",
            occupied=(_circle(BLUE),),
            clue_holds=None,
        )
        is PlaceDecision.ALLOW
    )


def test_max_chips_blocks_fifth() -> None:
    occupied = tuple(_circle(f"#00000{i}") for i in range(4))
    assert (
        evaluate_chip_placement(
            incoming_shape="square",
            incoming_color=RED,
            occupied=occupied,
            clue_holds=False,
        )
        is PlaceDecision.REJECT
    )
