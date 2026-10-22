# Organizador de descargas

Aplicación sencilla para Windows y macOS, escrita en Python con Tkinter.

## Uso

1. Elegí la carpeta donde Firefox descarga los archivos.
2. Elegí el destino de JSON. Dejá PDF vacío si los PDF ya están donde deben estar.
3. Presioná **Iniciar**. Las rutas se guardan automáticamente.
4. Presioná **Pausar** para detener la organización y editar las rutas.

Los archivos se separan por día dentro de cada destino: por ejemplo, `json/2026-10-21/factura.json` y `pdf/2026-10-21/factura.pdf`. Se usa la fecha local de la computadora al organizar el archivo, no la fecha del documento. Las subcarpetas se crean automáticamente y cambian al pasar la medianoche. Los nombres repetidos se numeran dentro de la carpeta del día. Los archivos ya organizados antes de esta función se quedan donde estaban.

Se revisa cada 3 segundos. Se incluyen los archivos que ya estaban en el origen, sin recorrer subcarpetas. Los nombres repetidos reciben un número. Espera dos observaciones estables y diez segundos desde la última modificación; omite archivos con un `.part` asociado. Estas comprobaciones reducen el riesgo de mover una descarga incompleta, pero no constituyen una señal de finalización del navegador: probá primero con descargas de ejemplo del sitio que ella utiliza.

Minimizar mantiene la aplicación funcionando. Cerrar la detiene. Al abrir comienza pausada. Esta versión no tiene icono en la bandeja ni inicio automático con Windows. Usá una sola instancia a la vez. El registro es visible durante la sesión.

Al mover un archivo, el historial de Firefox conserva su ruta anterior: abrí los JSON desde su carpeta de destino.

## Reordenar archivos guardados por fecha de modificación

Con la aplicación pausada, presioná **Reordenar por fecha de modificación…** y revisá los destinos que aparecen antes de confirmar. Se recorren las carpetas de destino configuradas y sus subcarpetas: JSON en el destino JSON, PDF en el destino PDF. Cada archivo se guarda en `AAAA-MM-DD` según su última modificación en la zona horaria local. Esta fecha no necesariamente es la de la factura o la descarga.

Es una acción manual de una sola ejecución. Los archivos ya ubicados en su día se dejan donde están; los nombres repetidos se numeran sin sobrescribir y las carpetas vacías se conservan. Se omiten enlaces y archivos recientes o con un `.part` asociado. El registro muestra el resultado; podés usar **Detener** y ejecutar la acción nuevamente más tarde. La organización automática permanece pausada al terminar y, cuando la iniciés, sigue agrupando por el día actual. Los destinos pueden ser la misma carpeta, pero no estar uno dentro del otro.

## Probar en tu Mac

Abrí **Iniciar.command** con doble clic, o ejecutá `./Iniciar.command` desde esta carpeta. El lanzador busca Python 3.12 o posterior con Tk 8.6 o posterior, incluyendo instalaciones de Homebrew y python.org.

El Python de Apple puede usar Tk 8.5 y mostrar una ventana vacía. La aplicación detecta esa versión y explica cómo abrir el lanzador.

Instalá Python 3.12 o posterior desde https://www.python.org/downloads/ si no tenés una versión con Tkinter. Si tu comando `python3` ya usa una versión compatible, también podés ejecutar:

```sh
python3 app.py
```

## Crear el ejecutable de Windows desde tu Mac

PyInstaller necesita Windows para generar un ejecutable Windows. Podés usar GitHub Actions sin instalar Windows en tu Mac:

1. Creá un repositorio en GitHub y subí el contenido de esta carpeta a su raíz, incluida la carpeta oculta `.github`.
2. En GitHub, abrí **Actions → Crear ejecutable Windows → Run workflow**.
3. Al terminar, descargá el artefacto **OrganizadorDescargas-Windows**.
4. Extraé el ZIP y copiá `OrganizadorDescargas.exe` a la computadora de ella.

El ejecutable incluye Python: ella no necesita instalarlo. El flujo se entrega preparado, pero no ha sido ejecutado desde este proyecto. El ejecutable no está firmado; Windows puede mostrar un aviso de editor desconocido. La disponibilidad y los límites de Actions dependen de tu cuenta.

## Crear el ejecutable en una computadora Windows

Instalá Python 3.12 desde python.org y ejecutá `crear-exe.bat`. El resultado queda en `dist/OrganizadorDescargas.exe`.

## Verificación

```sh
python3 -m unittest -v
```

Antes de usarlo con documentos reales, probá con carpetas de ejemplo: mover JSON, conservar PDF, repetir un nombre, pausar y reanudar. También verificá una descarga real de Firefox. Las pruebas automatizadas cubren las reglas, colisiones, pausa, archivos recientes y cambios durante el movimiento; no sustituyen la prueba de la interfaz y del ejecutable en Windows.
