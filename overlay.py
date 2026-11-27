"""Always-expanded, input-transparent desktop control reference."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from engine import key_name


class Overlay(QWidget):
    def __init__(self, owner):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput)
        super().__init__(None, flags)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowTitle('KeyToXbox · Controles en pantalla')

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName('overlayFrame')
        root.addWidget(frame)
        body = QVBoxLayout(frame)
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel('Tus controles')
        title.setObjectName('section')
        header.addWidget(title)
        header.addStretch()
        self.state = QLabel('En pausa')
        self.state.setObjectName('value')
        header.addWidget(self.state)
        body.addLayout(header)

        grid_widget = QWidget()
        grid_widget.setObjectName('overlayGrid')
        self.grid = QGridLayout(grid_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(9)
        self.values = {}
        for i, (name, _) in enumerate(owner.bindings.items()):
            label = QLabel(owner.display_names[name])
            value = QLabel()
            value.setObjectName('value')
            self.grid.addWidget(label, i // 2, (i % 2) * 2)
            self.grid.addWidget(value, i // 2, (i % 2) * 2 + 1)
            self.values[name] = value
        body.addWidget(grid_widget)

        self.modes = QLabel()
        self.modes.setObjectName('muted')
        body.addWidget(self.modes)
        hint = QLabel('F8 conecta / pausa · F9 muestra / oculta')
        hint.setObjectName('muted')
        body.addWidget(hint)

        self.setFixedWidth(470)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 24, screen.top() + 24)
        self.refresh()

    def refresh(self):
        self.state.setText('Activo' if self.owner.active else 'En pausa')
        for name, value in self.values.items():
            value.setText(key_name(self.owner.bindings[name]))
        self.modes.setText(
            f'Stick izq.: {self.owner.left.currentText()}   /   '
            f'Stick der.: {self.owner.right.currentText()}')

    def closeEvent(self, event):
        self.owner.overlay_option.setChecked(False)
        event.accept()
