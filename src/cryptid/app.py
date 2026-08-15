import sys
import resources_rc  # registers Qt resources
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui.shell.main_window import CryptidApp
from ui.shared.app_icon import load_application_icon
from ui.shared.custom_map_save import ensure_custom_maps_json
from ui.shared.styles import apply_app_style
from settings.config import APP_DISPLAY_NAME


def main():
    # Let QIcon use high-res pixmaps for title bars / dialogs on scaled displays.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    # Non-native dialogs: avoids a brief Windows shell titled "python" (host exe) on some systems.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setStyle("Fusion")  # Required for scrollbar stylesheets to apply on Windows
    app.setWindowIcon(load_application_icon())

    apply_app_style(app)

    ensure_custom_maps_json()

    cryptid_app = CryptidApp()
    cryptid_app.window.setWindowIcon(app.windowIcon())
    cryptid_app.window.show()
    app.processEvents()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
