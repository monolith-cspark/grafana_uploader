import sys
import ui_manager

if __name__ == '__main__':
    ui_manager.QApplication
    app = ui_manager.QApplication(sys.argv)

    tool = ui_manager.UI_Tool()
    tool.show()

    sys.exit(app.exec())
