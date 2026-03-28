import sys
from PyQt6.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
label = QLabel("Hello from JettRobin Debugger! If you see this, PyQt6 is working.")
label.resize(400, 100)
label.show()
print("Window shown. Check your taskbar or desktop.")
sys.exit(app.exec())