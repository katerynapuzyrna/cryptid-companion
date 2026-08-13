from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QDialog

from settings.config import QSS_DIR, QSS_FILES


class _DialogStyleFix(QObject):
    """Event filter: apply dialog stylesheet and WA_StyledBackground to QDialog on Windows."""

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self._app = app
        self._dialog_qss: str | None = None

    def _get_dialog_qss(self) -> str:
        if self._dialog_qss is None:
            path = QSS_DIR / "dialog.qss"
            self._dialog_qss = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._dialog_qss

    def eventFilter(self, obj, event):
        # Polish only: Show+unpolish+polish caused visible flicker on QDialog (e.g. message boxes).
        if isinstance(obj, QDialog) and event.type() == QEvent.Type.Polish:
            obj.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            qss = self._get_dialog_qss()
            if qss:
                obj.setStyleSheet(qss)
        return False


def load_qss() -> str:
    parts = []
    for name in QSS_FILES:
        path = QSS_DIR / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
        else:
            print("WARNING: QSS file not found:", path)
    return "\n".join(parts)

def apply_app_style(app: QApplication) -> None:
    qss = load_qss()
    if qss:
        app.setStyleSheet(qss)
    else:
        print("WARNING: no QSS loaded")
    app.installEventFilter(_DialogStyleFix(app, app))