# KeyToXbox

KeyToXbox transforma teclado y ratón en un mando Xbox 360 virtual para Windows. Permite cambiar las asignaciones, usar teclas o el ratón en cada joystick y consultar los controles en un overlay que deja pasar los clics al juego.

## Requisitos

- Windows 10 u 11, 64 bits.
- Python 3.10 o posterior.
- ViGEmBus instalado y funcionando para crear la salida XInput.

ViGEmBus está archivado y ya no recibe actualizaciones. Consulta su [aviso de fin de vida](https://docs.nefarius.at/projects/ViGEm/End-of-Life/) antes de instalarlo. `vgamepad` puede abrir su instalador durante la instalación; el procedimiento siguiente lo evita para que puedas instalar el controlador por separado.

## Instalación

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
python -m venv .venv
$env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL = 'true'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Después de instalar las dependencias y ViGEmBus, inicia la aplicación con:

```powershell
.\.venv\Scripts\python.exe main.py
```

También puedes abrir `Iniciar.bat` si el entorno `.venv` ya está preparado.

## Uso

Haz clic en una asignación para cambiarla. En la pestaña **Joysticks**, configura **L3 · pulsar stick izq.** y **R3 · pulsar stick der.** como botones pulsables del stick. Pulsa **Esc** para cancelar o **Supr** para borrarla. Los atajos **F8** y **F9** están reservados.

Elige **Teclas** o **Ratón** para cada joystick. Si usas el ratón, F8 lo captura y oculta el cursor; al pausar, restaura su posición. La captura se pausa si cambias a otra ventana. Vuelve al juego y pulsa F8 para capturarlo de nuevo.

Activa **Mostrar interfaz superpuesta** para ver las asignaciones sobre el escritorio. El overlay no tiene controles interactivos y deja pasar los clics. **F9** lo muestra u oculta sin pausar la captura. **F8** pausa el mando y libera el cursor.

Los perfiles se guardan automáticamente y se pueden importar o exportar desde la barra superior. La aplicación debe permanecer abierta mientras juegas.

## Límites conocidos

El juego debe admitir mandos XInput. El ratón mueve el joystick con desplazamiento relativo, por lo que no equivale a un stick analógico físico; si ambos joysticks usan el ratón, comparten el mismo movimiento. El overlay funciona mejor en modo ventana o pantalla completa sin bordes; algunos juegos en pantalla completa exclusiva pueden ocultarlo. La compatibilidad depende también del juego y de sus reglas.

## Referencias

- [vgamepad](https://github.com/yannbouteiller/vgamepad)
- [ViGEmBus y fin de vida](https://docs.nefarius.at/projects/ViGEm/End-of-Life/)
