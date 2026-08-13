"""Full-board snapshots for undo (tiles, structures, chips)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF

from board.markers import MARKER_SCALE_HOME, MARKER_Z_BANK

if TYPE_CHECKING:
    from board.board_builder import BoardBuilder


def strip_advanced_only_markers_from_snapshot(
    bb: "BoardBuilder", state: tuple[Any, ...]
) -> tuple[Any, ...]:
    """Rewrite a snapshot so advanced-only markers are off-canvas (home).

    When advanced mode is turned off, those markers are released from the board but
    older undo entries still recorded them on-canvas; the next undo would otherwise
    restore black before blue/green. Call from BoardUndoController when advanced=False.
    """
    if not state or len(state) < 3:
        return state
    piece_rows, marker_rows, chip_rows = state[0], state[1], state[2]
    chips_mode = state[3] if len(state) > 3 else False
    new_markers: list[tuple[Any, ...]] = []
    for row in marker_rows:
        if not row or row[0] != "m":
            new_markers.append(row)
            continue
        i = row[1]
        if i < 0 or i >= len(bb.markers):
            new_markers.append(row)
            continue
        m = bb.markers[i]
        if not getattr(m, "advanced_only", False):
            new_markers.append(row)
            continue
        r = row[2]
        if r < 0:
            new_markers.append(row)
            continue
        pos = m._home_pos
        new_markers.append(
            (
                "m",
                i,
                -1,
                -1,
                -1,
                MARKER_Z_BANK,
                MARKER_SCALE_HOME,
                pos.x(),
                pos.y(),
            )
        )
    return (piece_rows, tuple(new_markers), chip_rows, chips_mode)


def capture_board_state(bb: BoardBuilder) -> tuple[Any, ...]:
    """Immutable snapshot: pieces, markers, chips (positions, slots, highlights)."""
    c = bb.canvas
    if c is None:
        return ()

    piece_rows: list[tuple[Any, ...]] = []
    for i, p in enumerate(bb.pieces):
        slot = c.item_slot.get(p)
        rot = round(p.rotation()) % 360
        z = p.zValue()
        hl = frozenset(p.highlighted)
        if slot is not None:
            piece_rows.append(("p", i, slot[0], slot[1], rot, z, hl))
        else:
            pos = p.pos()
            piece_rows.append(("p", i, -1, -1, rot, z, hl, pos.x(), pos.y()))

    marker_rows: list[tuple[Any, ...]] = []
    for i, m in enumerate(bb.markers):
        slot = c.marker_slot.get(m)
        z = m.zValue()
        sc = m.scale()
        pos = m.pos()
        if slot is not None:
            marker_rows.append(("m", i, slot[0], slot[1], slot[2], z, sc))
        else:
            marker_rows.append(("m", i, -1, -1, -1, z, sc, pos.x(), pos.y()))

    chip_rows: list[tuple[Any, ...]] = []
    for i, ch in enumerate(bb.chips):
        slot = c.chip_slot.get(ch)
        z = ch.zValue()
        sc = ch.scale()
        pos = ch.pos()
        if slot is not None:
            chip_rows.append(("c", i, slot[0], slot[1], slot[2], z, sc))
        else:
            chip_rows.append(("c", i, -1, -1, -1, z, sc, pos.x(), pos.y()))

    return (
        tuple(piece_rows),
        tuple(marker_rows),
        tuple(chip_rows),
        bool(getattr(bb, "_chips_mode", False)),
    )


def restore_board_state(
    bb: BoardBuilder,
    state: tuple[Any, ...],
    *,
    skip_highlight_overlay_update: bool = False,
) -> None:
    """Restore board from ``capture_board_state`` output."""
    if not state or bb.canvas is None:
        return
    c = bb.canvas
    piece_rows, marker_rows, chip_rows, _chips_mode_snap = state

    for ch in bb.chips:
        c.release_chip(ch)
    for m in bb.markers:
        c.release_marker(m)
    for p in bb.pieces:
        c.release_item(p)

    for row in piece_rows:
        if row[0] != "p":
            continue
        i = row[1]
        r, col = row[2], row[3]
        rot, z, hl = row[4], row[5], row[6]
        p = bb.pieces[i]
        p.clear_highlight()
        p.highlighted.update(hl)
        p.setRotation(rot)
        p.setZValue(z)
        if r >= 0:
            pos = c.snap_pos_for_item_to_slot(p, r, col)
            p.setPos(pos)
            c.assign_item(p, r, col)
        else:
            px, py = row[7], row[8]
            p.setPos(QPointF(px, py))

    for row in marker_rows:
        if row[0] != "m":
            continue
        i = row[1]
        m = bb.markers[i]
        r, col, idx = row[2], row[3], row[4]
        if r >= 0:
            piece = c.occupied.get((r, col))
            if piece is None:
                m.setZValue(MARKER_Z_BANK)
                m.setScale(MARKER_SCALE_HOME)
                m.setPos(m._home_pos)
                continue
            c.assign_marker(m, r, col, idx)
        else:
            z, sc = row[5], row[6]
            px, py = row[7], row[8]
            m.setPos(QPointF(px, py))
            m.setZValue(z)
            m.setScale(sc)

    for row in chip_rows:
        if row[0] != "c":
            continue
        i = row[1]
        ch = bb.chips[i]
        r, col, idx = row[2], row[3], row[4]
        if r >= 0:
            piece = c.occupied.get((r, col))
            if piece is None:
                ch.setZValue(MARKER_Z_BANK)
                ch.setScale(MARKER_SCALE_HOME)
                ch.setPos(ch._home_pos)
                continue
            c.assign_chip(ch, r, col, idx)
        else:
            z, sc = row[5], row[6]
            px, py = row[7], row[8]
            ch.setPos(QPointF(px, py))
            ch.setZValue(z)
            ch.setScale(sc)

    for p in bb.pieces:
        p.update()
    for m in bb.markers:
        m.update()
    for ch in bb.chips:
        ch.update()
    if bb.highlight_overlay is not None and not skip_highlight_overlay_update:
        bb.highlight_overlay.update_highlights()
