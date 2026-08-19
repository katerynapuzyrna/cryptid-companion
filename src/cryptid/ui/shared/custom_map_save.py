"""Dialog + JSON append for saving a new custom map from any BoardBuilder."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from settings.config import CUSTOM_MAPS_JSON, CUSTOM_MAPS_EXAMPLE_JSON, DATA_DIR, MAPS_JSON
from settings.strings import (
    MAP_CREATED_BY_DEFAULT,
    MAP_SAVE_DIALOG_TITLE,
    MAP_SAVE_NAME_LABEL,
    MAP_SAVE_NAME_PLACEHOLDER,
)


def ensure_custom_maps_json() -> None:
    """Create ``custom_maps.json`` and merge any bundled starter maps that are missing."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not CUSTOM_MAPS_JSON.exists():
            if CUSTOM_MAPS_EXAMPLE_JSON.is_file():
                CUSTOM_MAPS_JSON.write_text(
                    CUSTOM_MAPS_EXAMPLE_JSON.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            else:
                CUSTOM_MAPS_JSON.write_text(
                    '{"version": 1, "maps": []}\n',
                    encoding="utf-8",
                )
        _merge_bundled_custom_maps()
    except OSError:
        pass


def _merge_bundled_custom_maps() -> None:
    """Append starter maps from the example file when the user file lacks them by name."""
    if not CUSTOM_MAPS_EXAMPLE_JSON.is_file() or not CUSTOM_MAPS_JSON.exists():
        return
    try:
        example = json.loads(CUSTOM_MAPS_EXAMPLE_JSON.read_text(encoding="utf-8"))
        root = json.loads(CUSTOM_MAPS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return
    existing = list(root.get("maps") or [])
    existing_names = {
        str(m.get("name") or "").strip().lower()
        for m in existing
        if isinstance(m, dict)
    }
    next_id = next_custom_map_id()
    added = False
    for starter in example.get("maps") or []:
        if not isinstance(starter, dict):
            continue
        name = str(starter.get("name") or "").strip()
        if not name or name.lower() in existing_names:
            continue
        tagged = dict(starter)
        tagged["id"] = next_id
        next_id += 1
        existing.append(tagged)
        existing_names.add(name.lower())
        added = True
    if not added:
        return
    root["maps"] = existing
    root["version"] = root.get("version", 1)
    CUSTOM_MAPS_JSON.write_text(
        json.dumps(root, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def next_custom_map_id() -> int:
    ids: list[int] = []
    for path in (MAPS_JSON, CUSTOM_MAPS_JSON):
        try:
            with open(path, encoding="utf-8") as f:
                root = json.load(f)
            for m in root.get("maps") or []:
                mid = m.get("id")
                if isinstance(mid, int):
                    ids.append(mid)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return max(ids, default=0) + 1


def prompt_save_map_name(
    parent: QWidget,
    default_name: str | None = None,
    *,
    window_title: str | None = None,
) -> str | None:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import (
        QDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle(window_title or MAP_SAVE_DIALOG_TITLE)
    dlg.setModal(True)
    outer = QVBoxLayout(dlg)
    outer.setSpacing(12)
    outer.addWidget(QLabel(MAP_SAVE_NAME_LABEL))
    edt = QLineEdit()
    edt.setPlaceholderText(MAP_SAVE_NAME_PLACEHOLDER)
    if default_name:
        edt.setText(default_name)
        edt.deselect()
        edt.setCursorPosition(len(edt.text()))
    outer.addWidget(edt)
    row = QHBoxLayout()
    row.addStretch(1)
    btn_cancel = QPushButton("Cancel")
    btn_ok = QPushButton("OK")
    btn_ok.setDefault(True)
    btn_ok.setAutoDefault(True)
    btn_ok.setProperty("primary", True)
    btn_ok.style().unpolish(btn_ok)
    btn_ok.style().polish(btn_ok)
    row.addWidget(btn_cancel)
    row.addWidget(btn_ok)
    outer.addLayout(row)
    dlg.adjustSize()
    base_w = max(dlg.width(), dlg.sizeHint().width())
    dlg.setMinimumWidth(max(1, base_w * 2))
    btn_cancel.clicked.connect(dlg.reject)
    btn_ok.clicked.connect(dlg.accept)
    edt.returnPressed.connect(dlg.accept)
    if default_name:

        def _focus_name_caret_end() -> None:
            edt.setFocus()
            edt.deselect()
            edt.setCursorPosition(len(edt.text()))

        QTimer.singleShot(0, _focus_name_caret_end)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    text = (edt.text() or "").strip()
    return text if text else MAP_SAVE_NAME_PLACEHOLDER


def append_custom_map_to_json(
    name: str,
    board_builder: Any,
    advanced_mode: bool,
    *,
    path: Path | None = None,
) -> bool:
    path = path or CUSTOM_MAPS_JSON
    exported = board_builder.export_board_to_map_data()
    new_map: dict = {
        "id": next_custom_map_id(),
        "name": name,
        "advancedMode": bool(advanced_mode),
        "grid3x2": exported["grid3x2"],
        "structures": exported["structures"],
        "books": {},
        "created_by": MAP_CREATED_BY_DEFAULT,
        "soft_deleted": 0,
    }
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                root = json.load(f)
        else:
            root = {"version": 1, "maps": []}
        maps_list = list(root.get("maps") or [])
        maps_list.append(new_map)
        root["maps"] = maps_list
        root["version"] = root.get("version", 1)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(root, f, indent=2, ensure_ascii=False)
    except (OSError, TypeError, ValueError):
        return False
    return True


def rename_custom_map_in_json(map_id: int, new_name: str, *, path: Path | None = None) -> bool:
    path = path or CUSTOM_MAPS_JSON
    try:
        with open(path, encoding="utf-8") as f:
            root = json.load(f)
        maps_list = list(root.get("maps") or [])
        found = False
        for m in maps_list:
            if m.get("id") == map_id:
                m["name"] = new_name
                found = True
                break
        if not found:
            return False
        root["maps"] = maps_list
        with open(path, "w", encoding="utf-8") as f:
            json.dump(root, f, indent=2, ensure_ascii=False)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
    return True
