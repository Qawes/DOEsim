from PyQt6.QtWidgets import QApplication
from main_window import MainWindow
import sys

if __name__ == "__main__":
    # Simple CLI parsing for a test-friendly switch
    force_single = False
    args = [a for a in sys.argv[1:] if a]
    if "--force-create" in args or "-1w" in args: # Forces a new workspace to be created on startup
        force_single = True
    app = QApplication(sys.argv)
    window = MainWindow(force_single_workspace=force_single)
    window.show()
    sys.exit(app.exec()) 

'''
Compile into exe:

pyinstaller --windowed --onedir --clean --icon fzp_icon.ico main.py

'''
