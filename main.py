import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QFile, QStandardPaths
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout,
    QPushButton, QComboBox, QSlider, QCheckBox, QFileDialog, QMessageBox,
    QScrollArea, QWidget, QSizePolicy, QTabWidget, QGridLayout)
from engine import DEFAULTS, Engine, key_name
from overlay import Overlay

ROOT = Path(__file__).resolve().parent

class BindingButton(QPushButton):
    def __init__(self, name, value, callback):
        super().__init__(key_name(value))
        self.setObjectName('binding')
        self.name, self.callback, self.capturing = name, callback, False
        self.clicked.connect(self.capture)
        self.setToolTip('Haz clic y pulsa una tecla o botón del ratón. Supr elimina la asignación; Esc cancela.')
    def capture(self):
        self.window().owner.stop()
        for button in self.window().owner.buttons.values():
            if button is not self and button.capturing: button.finish(None)
        self.capturing = True
        self.setProperty("capturing", True)
        self.style().unpolish(self); self.style().polish(self)
        self.setText('Pulsa una tecla…')
        self.setFocus()
        self.grabKeyboard()
    def keyPressEvent(self, event):
        if not self.capturing: return super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Escape: self.finish(None); return
        if event.key() == Qt.Key.Key_Delete: self.finish(0); return
        vk = event.nativeVirtualKey()
        if vk in (119,120):
            self.setText('Atajo reservado'); return
        if vk: self.finish(vk)
    def mousePressEvent(self, event):
        if self.capturing:
            mapping = {Qt.MouseButton.LeftButton:1, Qt.MouseButton.RightButton:2,
                       Qt.MouseButton.MiddleButton:4, Qt.MouseButton.BackButton:5, Qt.MouseButton.ForwardButton:6}
            vk = mapping.get(event.button())
            if vk: self.finish(vk)
            return
        super().mousePressEvent(event)
    def finish(self, vk):
        self.releaseKeyboard()
        self.capturing = False
        self.setProperty("capturing", False)
        self.style().unpolish(self); self.style().polish(self)
        if vk is not None: self.callback(self.name, vk)
        self.setText(key_name(self.window().owner.bindings[self.name]))

class ControllerArt(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QPixmap(str(ROOT / 'resources/images/controller.png'))
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def paintEvent(self, event):
        if self.image.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scaled = self.image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((self.width()-scaled.width())//2, (self.height()-scaled.height())//2, scaled)

class App:
    def __init__(self):
        f=QFile(str(ROOT/'resources/ui/main.ui')); f.open(QFile.OpenModeFlag.ReadOnly)
        self.window=QUiLoader().load(f); f.close(); self.window.owner=self
        self.engine=Engine(); self.bindings=DEFAULTS.copy(); self.buttons={}; self.active=False
        self.path=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))/'profile.json'
        self.overlay = None
        self.foreground = None
        self.build(); self.overlay = Overlay(self); self.load_auto()
        self.timer=QTimer(self.window); self.timer.timeout.connect(self.tick); self.timer.start(16)
        self.window.resize(1280,850); self.window.setMinimumSize(1000,740)
        self.window.closeEvent=self.close
    def label(self,text,kind=None):
        l=QLabel(text); l.setWordWrap(True)
        if kind: l.setObjectName(kind)
        return l
    def card(self):
        f=QFrame(); f.setObjectName('card'); lay=QVBoxLayout(f); lay.setContentsMargins(18,16,18,16); lay.setSpacing(10); return f,lay
    def button(self,text,fn,primary=False):
        b=QPushButton(text); b.clicked.connect(fn)
        if primary: b.setObjectName('primary')
        return b
    def build(self):
        root = self.window.findChild(QVBoxLayout,'rootLayout')
        toolbar = QFrame(); toolbar.setObjectName('toolbar'); bar = QHBoxLayout(toolbar); bar.setContentsMargins(28,16,28,16); bar.setSpacing(12)
        bar.addWidget(self.label('KeyToXbox','brand')); bar.addSpacing(16); subtitle = self.label('Teclado + ratón  /  Xbox 360','muted'); subtitle.setWordWrap(False); bar.addWidget(subtitle); bar.addStretch()
        bar.addWidget(self.button('Importar perfil',self.import_profile)); bar.addWidget(self.button('Exportar perfil',self.export_profile)); root.addWidget(toolbar)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); root.addWidget(scroll,1); content = QWidget(); scroll.setWidget(content)
        body = QVBoxLayout(content); body.setContentsMargins(28,24,28,24); body.setSpacing(20)
        top = QHBoxLayout(); titles = QVBoxLayout(); titles.setSpacing(4); titles.addWidget(self.label('Configura tu forma de jugar','title')); titles.addWidget(self.label('Asigna una entrada a cada control. Tu perfil se guarda al instante.','muted')); top.addLayout(titles,1)
        self.connect_button = self.button('Conectar mando  ·  F8',self.toggle,True); top.addWidget(self.connect_button); body.addLayout(top)
        notice = QFrame(); notice.setObjectName('notice'); nl = QHBoxLayout(notice); nl.setContentsMargins(14,10,14,10); self.status = self.label('En pausa · Elige tus controles y conecta el mando.'); nl.addWidget(self.status,1); nl.addWidget(self.label('F8  conectar / pausar','value')); body.addWidget(notice)
        workspace = QHBoxLayout(); workspace.setSpacing(20); body.addLayout(workspace,1)
        editor, el = self.card(); el.setSpacing(10)
        head = QHBoxLayout(); head.addWidget(self.label('Tu mando virtual','section')); head.addStretch(); head.addWidget(self.label('Salida XInput','muted')); el.addLayout(head)
        art = ControllerArt(); art.setMinimumHeight(170); art.setMaximumHeight(190); el.addWidget(art)
        sub = QHBoxLayout(); sub.addWidget(self.label('Asignaciones','section')); sub.addStretch(); sub.addWidget(self.button('Restablecer',self.reset)); el.addLayout(sub)
        el.addWidget(self.label('Haz clic en una tecla para cambiarla. Esc cancela; Supr borra.','muted'))
        groups = [('Acciones',[('A','A'),('B','B'),('X','X'),('Y','Y'),('LB','LB'),('RB','RB'),('LT','LT'),('RT','RT')]),('Navegación',[('Vista','BACK'),('Menú','START'),('Clic izquierdo','LS'),('Clic derecho','RS'),('Cruceta ↑','DU'),('Cruceta ↓','DD'),('Cruceta ←','DL'),('Cruceta →','DR')]),('Joysticks',[('Izquierdo ↑','LU'),('Izquierdo ↓','LD'),('Izquierdo ←','LL'),('Izquierdo →','LR'),('Derecho ↑','RU'),('Derecho ↓','RD'),('Derecho ←','RL'),('Derecho →','RR')])]
        self.display_names = {name:display for _,items in groups for display,name in items}
        self.tabs = QTabWidget()
        for heading,items in groups:
            page = QWidget(); page.setObjectName('tabPage'); grid = QGridLayout(page); grid.setContentsMargins(0,16,0,0); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(9)
            for i,(display,name) in enumerate(items):
                frame = QFrame(); frame.setObjectName('row'); row = QHBoxLayout(frame); row.setContentsMargins(12,4,6,4)
                row.addWidget(self.label(display),1); button = BindingButton(name,self.bindings[name],self.set_binding); button.setAccessibleName('Asignar '+display); self.buttons[name] = button; row.addWidget(button)
                grid.addWidget(frame,i//2,i%2)
            self.tabs.addTab(page,heading)
        el.addWidget(self.tabs); workspace.addWidget(editor,7)
        inspector, il = self.card(); inspector.setMinimumWidth(300); inspector.setMaximumWidth(355); il.setSpacing(10)
        il.addWidget(self.label('Movimiento','section')); il.addWidget(self.label('Elige la entrada de cada joystick.','muted'))
        self.left = QComboBox(); self.right = QComboBox()
        for combo in (self.left,self.right): combo.addItems(['Teclas','Ratón']); combo.currentTextChanged.connect(self.mode_changed)
        il.addWidget(self.label('Joystick izquierdo')); il.addWidget(self.left); il.addWidget(self.label('Joystick derecho')); il.addWidget(self.right)
        row = QHBoxLayout(); row.addWidget(self.label('Sensibilidad del ratón'),1); self.sens_label = self.label('35','value'); row.addWidget(self.sens_label); il.addLayout(row)
        self.sensitivity = QSlider(Qt.Orientation.Horizontal); self.sensitivity.setObjectName('sensitivitySlider'); self.sensitivity.setRange(1,100); self.sensitivity.setValue(35); self.sensitivity.setAccessibleName('Sensibilidad del ratón'); self.sensitivity.valueChanged.connect(self.change_sens); il.addWidget(self.sensitivity)
        self.invert = QCheckBox('Invertir eje vertical'); self.invert.toggled.connect(self.save_auto); il.addWidget(self.invert)
        il.addSpacing(8); il.addWidget(self.label('Captura del ratón','section')); il.addWidget(self.label('El cursor desaparece al usar el ratón como joystick. F8 lo libera y recupera su posición.','muted'))
        il.addSpacing(8); il.addWidget(self.label('Controles en pantalla','section'))
        self.overlay_option = QCheckBox('Mostrar interfaz superpuesta'); self.overlay_option.toggled.connect(self.overlay_changed); il.addWidget(self.overlay_option)
        il.addWidget(self.label('Las asignaciones permanecen visibles sin recibir clics. F9 muestra u oculta el panel.','muted')); il.addStretch()
        workspace.addWidget(inspector,3)
        footer = QHBoxLayout(); footer.addWidget(self.label('Los botones originales también llegan al juego.','muted'),1); footer.addWidget(self.label('F9  mostrar / ocultar overlay','muted')); body.addLayout(footer)
    def mode_changed(self,*args):
        if self.active: self.stop()
        self.save_auto()
    def overlay_changed(self,checked):
        if self.overlay is not None:
            self.overlay.setVisible(checked)
            if checked: self.overlay.refresh()
        self.save_auto()
    def toggle_overlay(self):
        self.overlay_option.setChecked(not self.overlay.isVisible())
    def refresh_overlay(self):
        if self.overlay is not None: self.overlay.refresh()
    def set_binding(self,name,vk): self.bindings[name]=vk; self.save_auto(); self.refresh_overlay()
    def change_sens(self,v): self.sens_label.setText(str(v)); self.save_auto()
    def data(self): return {'version':1,'bindings':self.bindings,'left':self.left.currentText(),'right':self.right.currentText(),'sensitivity':self.sensitivity.value(),'invert_y':self.invert.isChecked(),'overlay':self.overlay_option.isChecked()}
    def apply(self,data):
        if not isinstance(data,dict) or data.get('version') != 1: raise ValueError('Formato de perfil no compatible.')
        bindings=data.get('bindings',{})
        if not isinstance(bindings,dict): raise ValueError('Asignaciones inválidas.')
        if any(k not in DEFAULTS or type(v) is not int or not 0 <= v <= 255 or v in (119,120) for k,v in bindings.items()): raise ValueError('El perfil contiene teclas inválidas o reservadas.')
        if data.get('left','Teclas') not in ('Teclas','Ratón') or data.get('right','Teclas') not in ('Teclas','Ratón'): raise ValueError('Modo de joystick inválido.')
        sensitivity=data.get('sensitivity',35)
        if type(sensitivity) is not int or not 1 <= sensitivity <= 100 or type(data.get('invert_y',False)) is not bool: raise ValueError('Ajustes de ratón inválidos.')
        if type(data.get('overlay',False)) is not bool: raise ValueError('La opción de controles en pantalla debe ser verdadera o falsa.')
        self.bindings=DEFAULTS.copy(); self.bindings.update(bindings)
        for k,b in self.buttons.items(): b.setText(key_name(self.bindings[k]))
        self.stop()
        self.left.setCurrentText(data.get('left','Teclas')); self.right.setCurrentText(data.get('right','Teclas')); self.sensitivity.setValue(sensitivity); self.invert.setChecked(data.get('invert_y',False)); self.overlay_option.setChecked(data.get('overlay',False)); self.save_auto(); self.refresh_overlay()
    def save_auto(self,*args):
        if not hasattr(self,'overlay_option'): return
        try: self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(json.dumps(self.data(),indent=2,ensure_ascii=False),encoding='utf-8')
        except OSError as e: self.status.setText('No se pudo guardar el perfil: '+str(e))
    def load_auto(self):
        if self.path.exists():
            try: self.apply(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError,OSError) as e: self.status.setText('No se pudo cargar el perfil: '+str(e))
    def reset(self): self.apply({'version':1,'bindings':DEFAULTS})
    def import_profile(self):
        path,_=QFileDialog.getOpenFileName(self.window,'Importar perfil','','Perfil JSON (*.json)')
        if path:
            try: self.apply(json.loads(Path(path).read_text(encoding='utf-8')))
            except (ValueError,OSError) as e: QMessageBox.warning(self.window,'Perfil inválido',str(e))
    def export_profile(self):
        path,_=QFileDialog.getSaveFileName(self.window,'Exportar perfil','perfil.json','Perfil JSON (*.json)')
        if path:
            try: Path(path).write_text(json.dumps(self.data(),indent=2,ensure_ascii=False),encoding='utf-8')
            except OSError as e: QMessageBox.warning(self.window,'No se pudo exportar',str(e))
    def toggle(self):
        if any(b.capturing for b in self.buttons.values()): return
        if self.active: self.stop(); return
        try:
            self.engine.connect()
            if self.left.currentText()=='Ratón' or self.right.currentText()=='Ratón':
                self.engine.capture_mouse()
                self.foreground = self.engine.user32.GetForegroundWindow()
            self.active=True
            self.connect_button.setText('Pausar mando  ·  F8')
            self.status.setText('Conectado · Mando Xbox activo. Pulsa F8 para pausar y liberar el ratón.')
            self.refresh_overlay()
        except Exception as e:
            self.stop()
            self.status.setText('No conectado · '+str(e))
    def stop(self):
        error = None
        try: self.engine.disconnect()
        except Exception as e: error = str(e)
        self.active=False; self.foreground=None
        self.connect_button.setText('Conectar mando  ·  F8')
        self.status.setText('Error al liberar el ratón · '+error if error else 'En pausa · Ratón libre y mando desconectado.')
        self.refresh_overlay()
    def tick(self):
        if self.engine.f8_pressed(): self.toggle()
        if self.engine.hotkey_pressed(120) and not any(b.capturing for b in self.buttons.values()): self.toggle_overlay()
        if self.active:
            try:
                if self.engine.mouse_captured and self.engine.user32.GetForegroundWindow() != self.foreground:
                    self.stop(); return
                self.engine.tick(self.bindings,self.left.currentText(),self.right.currentText(),self.sensitivity.value(),self.invert.isChecked())
            except Exception as e: self.stop(); self.status.setText('Error de entrada · '+str(e))
    def close(self,event):
        self.stop()
        if self.overlay: self.overlay.hide(); self.overlay.deleteLater()
        event.accept()

if __name__ == '__main__':
    app=QApplication(sys.argv); app.setApplicationName('KeyToXbox'); app.setStyleSheet((ROOT/'resources/styles/app.qss').read_text(encoding='utf-8-sig'))
    ui=App(); app.aboutToQuit.connect(ui.stop); ui.window.show(); sys.exit(app.exec())
