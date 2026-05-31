"""
InSAR相位解缠处理系统 - 主入口
"""

import sys
import os

os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', '')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from phase_unwrapping.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setFont(QFont('Microsoft YaHei', 9))

    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
