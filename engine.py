"""Windows input polling and virtual Xbox output."""
import ctypes
import math
import sys
import threading
import time

DEFAULTS = {
    'A': 32, 'B': 67, 'X': 82, 'Y': 70, 'LB': 81, 'RB': 69,
    'LT': 2, 'RT': 1, 'BACK': 9, 'START': 13, 'LS': 16, 'RS': 86,
    'DU': 38, 'DD': 40, 'DL': 37, 'DR': 39,
    'LU': 87, 'LD': 83, 'LL': 65, 'LR': 68,
    'RU': 73, 'RD': 75, 'RL': 74, 'RR': 76,
}
BUTTONS = {'A':'A', 'B':'B', 'X':'X', 'Y':'Y', 'LB':'LEFT_SHOULDER',
           'RB':'RIGHT_SHOULDER', 'BACK':'BACK', 'START':'START',
           'LS':'LEFT_THUMB', 'RS':'RIGHT_THUMB', 'DU':'DPAD_UP',
           'DD':'DPAD_DOWN', 'DL':'DPAD_LEFT', 'DR':'DPAD_RIGHT'}
SPECIAL = {1:'Ratón izq.', 2:'Ratón der.', 4:'Ratón centro', 5:'Ratón 4', 6:'Ratón 5',
           8:'Retroceso', 9:'Tab', 13:'Intro', 16:'Mayús', 17:'Ctrl', 18:'Alt',
           20:'Bloq Mayús', 32:'Espacio', 33:'Re Pág', 34:'Av Pág', 35:'Fin', 36:'Inicio',
           37:'←', 38:'↑', 39:'→', 40:'↓', 45:'Insert', 46:'Supr'}

def key_name(vk):
    if not vk: return 'Sin asignar'
    if vk in SPECIAL: return SPECIAL[vk]
    if 112 <= vk <= 135: return f'F{vk - 111}'
    if 96 <= vk <= 105: return f'Num {vk - 96}'
    if 48 <= vk <= 90: return chr(vk)
    return f'Tecla {vk}'

class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint32), ('rcMonitor', RECT),
                ('rcWork', RECT), ('dwFlags', ctypes.c_uint32)]

class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint32), ('flags', ctypes.c_uint32),
                ('hCursor', ctypes.c_void_p), ('ptScreenPos', POINT)]

class Engine:
    def __init__(self):
        self.pad = None
        self.vg = None
        self.user32 = ctypes.WinDLL('user32', use_last_error=True) if sys.platform == 'win32' else None
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True) if sys.platform == 'win32' else None
        self.last_f8 = False
        self._hotkeys = {}
        self.mouse_captured = False
        self._cursor_position = None
        self._previous_clip = None
        self._hide_calls = 0
        self._capture_thread = None
        self._attached_thread = None
        self._native_thread = None
        self.mouse_center = (0, 0)
        self._verify_mouse_at = None
        if self.user32:
            self.user32.GetForegroundWindow.argtypes = []
            self.user32.GetForegroundWindow.restype = ctypes.c_void_p
            self.user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            self.user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
            self.user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
            self.user32.GetWindowRect.restype = ctypes.c_int
            self.user32.AttachThreadInput.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int]
            self.user32.AttachThreadInput.restype = ctypes.c_int
            self.user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
            self.user32.GetCursorInfo.restype = ctypes.c_int
            self.user32.ShowCursor.argtypes = [ctypes.c_int]
            self.user32.ShowCursor.restype = ctypes.c_int
            self.kernel32.GetCurrentThreadId.argtypes = []
            self.kernel32.GetCurrentThreadId.restype = ctypes.c_uint32
            self.user32.MonitorFromPoint.argtypes = [POINT, ctypes.c_uint32]
            self.user32.MonitorFromPoint.restype = ctypes.c_void_p
            self.user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
            self.user32.GetMonitorInfoW.restype = ctypes.c_int

    def connect(self):
        if not self.user32: raise RuntimeError('Esta aplicación requiere Windows.')
        try:
            import vgamepad as vg
        except ImportError as exc:
            raise RuntimeError('Falta vgamepad. Instala las dependencias indicadas en el README.') from exc
        except Exception as exc:
            raise RuntimeError('No se pudo acceder a ViGEmBus. Comprueba que el controlador esté instalado y accesible. Detalle: ' + str(exc)) from exc
        try:
            self.pad = vg.VX360Gamepad()
            self.vg = vg
        except Exception as exc:
            raise RuntimeError('No se pudo crear el mando virtual. Comprueba que ViGEmBus esté instalado y funcionando. Detalle: ' + str(exc)) from exc

    def neutral(self):
        """Release all virtual controls without removing the virtual device."""
        if self.pad is not None:
            self.pad.reset()
            self.pad.update()

    def disconnect(self):
        # Cursor restoration must run even when the bus fails during reset.
        try:
            self.neutral()
        finally:
            self.pad = None
            self.vg = None
            self.release_mouse()

    def capture_mouse(self):
        """Capture on the UI thread; release_mouse must run on that same thread."""
        if self.mouse_captured:
            return
        if self._attached_thread is not None or self._previous_clip is not None or self._cursor_position is not None:
            self.release_mouse()
        if not self.user32:
            raise RuntimeError('La captura del ratón requiere Windows.')
        u = self.user32
        point, previous_clip = POINT(), RECT()
        if not u.GetCursorPos(ctypes.byref(point)) or not u.GetClipCursor(ctypes.byref(previous_clip)):
            raise RuntimeError('Windows no permitió leer el estado del cursor.')
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        monitor = u.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor or not u.GetMonitorInfoW(monitor, ctypes.byref(info)):
            raise RuntimeError('No se pudo determinar la pantalla del cursor.')
        bounds = info.rcMonitor
        self.mouse_center = ((bounds.left + bounds.right) // 2,
                             (bounds.top + bounds.bottom) // 2)
        self._cursor_position = (point.x, point.y)
        self._previous_clip = previous_clip
        self._capture_thread = threading.get_ident()
        self.mouse_captured = True
        self._native_thread = self.kernel32.GetCurrentThreadId()
        try:
            hwnd = u.GetForegroundWindow()
            target_thread = u.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
            if not target_thread:
                raise RuntimeError('No se pudo identificar la ventana activa para ocultar el cursor.')
            window_rect = RECT()
            if u.GetWindowRect(hwnd, ctypes.byref(window_rect)):
                intersection = RECT(max(bounds.left, window_rect.left),
                                    max(bounds.top, window_rect.top),
                                    min(bounds.right, window_rect.right),
                                    min(bounds.bottom, window_rect.bottom))
                if intersection.right > intersection.left and intersection.bottom > intersection.top:
                    bounds = intersection
                    self.mouse_center = ((bounds.left + bounds.right) // 2,
                                         (bounds.top + bounds.bottom) // 2)

            if target_thread != self._native_thread:
                if not u.AttachThreadInput(self._native_thread, target_thread, True):
                    raise RuntimeError('Windows no permitió compartir la entrada con la ventana activa. Código: ' + str(ctypes.get_last_error()))
                self._attached_thread = target_thread
            if not u.ClipCursor(ctypes.byref(bounds)):
                raise RuntimeError('Windows no permitió capturar el ratón.')
            if not u.SetCursorPos(*self.mouse_center):
                raise RuntimeError('Windows no permitió centrar el cursor.')
            # ShowCursor maintains a counter. Restore exactly our own decrements,
            # preserving a cursor that was already hidden by another component.
            for _ in range(64):
                count = u.ShowCursor(False)
                self._hide_calls += 1
                if count < 0:
                    break
            else:
                raise RuntimeError('No se pudo ocultar el cursor.')
            # Cross-process cursor visibility updates are asynchronous. The UI
            # timer checks after the compositor/input queue has processed hide.
            self._verify_mouse_at = time.monotonic() + 0.05
        except Exception:
            self.release_mouse()
            raise

    def verify_mouse_capture(self, force=False):
        """Verify the global pointer after a nonblocking visibility grace period."""
        if self._verify_mouse_at is None or not self.mouse_captured:
            return
        if not force and time.monotonic() < self._verify_mouse_at:
            return
        cursor = CURSORINFO()
        cursor.cbSize = ctypes.sizeof(cursor)
        try:
            if not self.user32.GetCursorInfo(ctypes.byref(cursor)):
                raise RuntimeError('Windows no permitió comprobar la visibilidad del cursor.')
            if cursor.flags & 1:  # CURSOR_SHOWING
                raise RuntimeError('La ventana activa mantiene el cursor visible. Se ha cancelado la captura.')
            self._verify_mouse_at = None
        except Exception:
            self.release_mouse()
            raise

    def release_mouse(self):
        """Restore visibility while still attached, then detach the input queues."""
        if not self.mouse_captured and self._attached_thread is None and self._previous_clip is None and self._cursor_position is None:
            return
        if self._capture_thread != threading.get_ident():
            raise RuntimeError('El cursor debe liberarse desde el hilo que lo capturó.')
        u = self.user32
        self._verify_mouse_at = None
        errors = []
        try:
            if self._previous_clip is not None:
                if u.ClipCursor(ctypes.byref(self._previous_clip)):
                    self._previous_clip = None
                else:
                    errors.append('No se pudo restaurar el límite del cursor. Vuelve a pausar para reintentar.')
            # These increments must happen before detaching the foreground queue.
            for _ in range(self._hide_calls):
                u.ShowCursor(True)
            self._hide_calls = 0
            if self._cursor_position is not None:
                # Do not discard the original position while the old clip could
                # still force SetCursorPos into our capture rectangle.
                if self._previous_clip is None and u.SetCursorPos(*self._cursor_position):
                    self._cursor_position = None
                else:
                    errors.append('No se pudo restaurar la posición del cursor. Vuelve a pausar para reintentar.')
        finally:
            self.mouse_captured = False
            if self._attached_thread is not None:
                if u.AttachThreadInput(self._native_thread, self._attached_thread, False):
                    self._attached_thread = None
                else:
                    errors.append('Windows no permitió separar las colas de entrada. Vuelve a pausar para reintentar.')
            if self._attached_thread is None and self._previous_clip is None and self._cursor_position is None:
                self._capture_thread = None
                self._native_thread = None
        if errors:
            raise RuntimeError(' '.join(errors))

    def hotkey_pressed(self, vk):
        now = self.down(vk)
        pressed = now and not self._hotkeys.get(vk, False)
        self._hotkeys[vk] = now
        return pressed

    def down(self, vk):
        return bool(vk and self.user32 and self.user32.GetAsyncKeyState(vk) & 0x8000)

    def f8_pressed(self):
        now = self.down(119)
        pressed = now and not self.last_f8
        self.last_f8 = now
        return pressed

    def tick(self, bindings, left_mode, right_mode, sensitivity, invert_y):
        self.verify_mouse_capture()
        if self.pad is None: return
        p = self.pad
        p.reset()
        for name, enum_name in BUTTONS.items():
            if self.down(bindings.get(name, 0)):
                p.press_button(getattr(self.vg.XUSB_BUTTON, 'XUSB_GAMEPAD_' + enum_name))
        p.left_trigger(value=255 if self.down(bindings.get('LT', 0)) else 0)
        p.right_trigger(value=255 if self.down(bindings.get('RT', 0)) else 0)
        mouse = (0.0, 0.0)
        if self.mouse_captured and (left_mode == 'Ratón' or right_mode == 'Ratón'):
            point = POINT()
            if not self.user32.GetCursorPos(ctypes.byref(point)):
                raise RuntimeError('Se perdió el acceso al cursor.')
            cx, cy = self.mouse_center
            scale = sensitivity / 1000.0
            mouse = (max(-1., min(1., (point.x-cx)*scale)),
                     max(-1., min(1., (point.y-cy)*scale*(1 if invert_y else -1))))
            self.user32.SetCursorPos(cx, cy)
        def stick(prefix, mode):
            if mode == 'Ratón': return mouse
            x = int(self.down(bindings.get(prefix+'R', 0))) - int(self.down(bindings.get(prefix+'L', 0)))
            y = int(self.down(bindings.get(prefix+'U', 0))) - int(self.down(bindings.get(prefix+'D', 0)))
            length = math.hypot(x, y)
            return (x / length, y / length) if length else (0., 0.)
        lx, ly = stick('L', left_mode)
        rx, ry = stick('R', right_mode)
        p.left_joystick_float(x_value_float=lx, y_value_float=ly)
        p.right_joystick_float(x_value_float=rx, y_value_float=ry)
        p.update()
