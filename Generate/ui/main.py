import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication, QIcon
from PyQt5.QtWidgets import QApplication

from styles.fonts import application_font


def _configure_high_dpi() -> None:
    """Configure one predictable Qt scaling policy before QApplication exists."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Qt 5.14+ can avoid rounding 125%/150% scale factors to coarse steps.
    policy_group = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    setter = getattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy", None)
    if policy_group is not None and setter is not None:
        setter(policy_group.PassThrough)


def main():
    _configure_high_dpi()
    app = QApplication(sys.argv)
    app.setApplicationName("MotorAI")
    app.setFont(application_font())

    # Import widget modules only after the application-wide DPI and font
    # policies are active.
    from ui_main import MainWindow
    
    icon_path = os.path.join(os.path.dirname(__file__), '..', 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
