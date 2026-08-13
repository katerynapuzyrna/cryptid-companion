"""Undo stack for board tiles, structures, and chips (single shared pattern)."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtWidgets import QToolButton

from board.undo_state import (
    capture_board_state,
    restore_board_state,
    strip_advanced_only_markers_from_snapshot,
)

if TYPE_CHECKING:
    from board.board_builder import BoardBuilder

    from ui.shared.widgets import HoverTooltipManager


class BoardUndoController:
    """Push snapshots on user edits; undo restores previous snapshot."""

    _max_undo = 50

    def __init__(
        self,
        board_builder: BoardBuilder,
        buttons: list[QToolButton],
        tooltip_manager: HoverTooltipManager,
        tooltip_text: str,
        *,
        after_undo: Optional[Callable[[], None]] = None,
    ) -> None:
        self.bb = board_builder
        self._buttons = buttons
        self._tooltip = tooltip_manager
        self._tooltip_text = tooltip_text
        self._after_undo = after_undo
        self._undo_stack: list[tuple[Any, ...]] = []
        self._ref: tuple[Any, ...] = ()
        self._tracking = False
        self._suppress = False

        for btn in self._buttons:
            btn.setEnabled(False)
            btn.hide()
            btn.clicked.connect(self._on_undo_clicked)
            self._tooltip.add(btn, tooltip_text, only_when_disabled=False)

    def set_board(self, board_builder: BoardBuilder) -> None:
        """Point at a new BoardBuilder (same buttons)."""
        was = self._tracking
        self.set_tracking(False)
        self.bb = board_builder
        if was:
            self.set_tracking(True)

    def set_tracking(self, on: bool) -> None:
        """Enable/disable recording. Only ``reset()`` when turning tracking on (fresh baseline);
        repeated ``set_tracking(True)`` must not clear the stack (e.g. Maps Library refresh)."""
        was_tracking = self._tracking
        self._tracking = on
        c = self.bb.canvas if self.bb else None
        if c is not None:
            if on:
                c._on_undo_checkpoint = self.notify_edit
                if not was_tracking:
                    self.reset()
                else:
                    self._sync_buttons()
            else:
                if was_tracking and getattr(c, "_on_undo_checkpoint", None) == self.notify_edit:
                    c._on_undo_checkpoint = None
                if was_tracking:
                    self._undo_stack.clear()
                    self._ref = ()
                self._sync_buttons()
        else:
            if not on and was_tracking:
                self._undo_stack.clear()
                self._ref = ()
            self._sync_buttons()

    def reset(self) -> None:
        """Drop history; baseline = current board (after load/reset/programmatic change)."""
        self._undo_stack.clear()
        if self.bb is not None and self.bb.canvas is not None:
            self._ref = capture_board_state(self.bb)
        else:
            self._ref = ()
        self._sync_buttons()

    def rewrite_snapshots_strip_advanced_markers(self) -> None:
        """After advanced mode is turned off: align history with markers no longer on canvas."""
        if self.bb is None or not self._tracking:
            return
        stripped = [
            strip_advanced_only_markers_from_snapshot(self.bb, s) for s in self._undo_stack
        ]
        # Blue → blue+black → blue+green becomes blue → blue → blue+green in snapshots once
        # black is stripped; consecutive duplicates would make an undo a no-op.
        self._undo_stack = []
        for s in stripped:
            if not self._undo_stack or self._undo_stack[-1] != s:
                self._undo_stack.append(s)
        if self._ref:
            self._ref = strip_advanced_only_markers_from_snapshot(self.bb, self._ref)
        # After "undo green" then advanced off: stripped ref (blue only) can equal
        # stripped stack[-1] (state before black was also blue only once black is
        # stripped from snapshots). The next undo would otherwise pop that duplicate
        # and restore the same board — no visible change. Drop trailing duplicates.
        while self._undo_stack and self._ref == self._undo_stack[-1]:
            self._undo_stack.pop()
        self._sync_buttons()

    def notify_edit(self) -> None:
        if not self._tracking or self._suppress:
            return
        # Flush immediately: QTimer.singleShot(0) can run after other queued work
        # (e.g. layout/status) that calls set_tracking/reset in the same turn, making
        # new == _ref and skipping the first undo step.
        self._flush()

    def _flush(self) -> None:
        if not self._tracking or self._suppress or self.bb is None or self.bb.canvas is None:
            return
        new = capture_board_state(self.bb)
        if new == self._ref:
            return
        self._undo_stack.append(self._ref)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._ref = new
        self._sync_buttons()

    def _on_undo_clicked(self) -> None:
        if not self._undo_stack or self.bb is None or self.bb.canvas is None:
            return
        self._suppress = True
        prev = self._undo_stack.pop()
        # Chips simulation: after_undo will recompute highlights from combos — skip an
        # intermediate full overlay refresh so undo does not flash empty then redraw.
        skip_hl = bool(
            getattr(self.bb, "_chips_mode", False) and self._after_undo is not None
        )
        restore_board_state(self.bb, prev, skip_highlight_overlay_update=skip_hl)
        self._ref = capture_board_state(self.bb)
        self._suppress = False
        self._sync_buttons()
        if self._after_undo is not None:
            self._after_undo()

    def _sync_buttons(self) -> None:
        can_undo = bool(self._tracking and self._undo_stack)
        for b in self._buttons:
            b.setVisible(can_undo)
            b.setEnabled(can_undo)
        if can_undo and self.bb is not None:
            for name in ("_proxy_freeze", "_proxy_hl"):
                proxy = getattr(self.bb, name, None)
                if proxy is not None:
                    proxy.update()
