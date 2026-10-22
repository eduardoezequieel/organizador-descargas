import json
from datetime import datetime
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from organizer import Organizer, Reorganizer


CONFIG = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'Library' / 'Application Support')) / 'OrganizadorDescargas' / 'config.json'


class App:
    def __init__(self, root):
        self.root = root
        self.stop = threading.Event()
        self.worker = None
        self.manual = False
        self.events = queue.Queue()
        root.title('Organizador de descargas')
        root.geometry('820x590')
        root.minsize(760, 510)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='Tus descargas, en su carpeta', font=('', 19, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 8))
        ttk.Label(frame, text='Elegí el origen y los destinos. Dejá un destino vacío para conservar esos archivos.').grid(row=1, column=0, columnspan=3, sticky='w', pady=(0, 18))
        self.values = {}
        self.inputs = []
        for row, (key, label) in enumerate([('source', 'Carpeta de descarga'), ('json', 'Mover JSON a'), ('pdf', 'Mover PDF a')], 2):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=6)
            value = tk.StringVar()
            self.values[key] = value
            entry = ttk.Entry(frame, textvariable=value)
            entry.grid(row=row, column=1, sticky='ew')
            button = ttk.Button(frame, text='Elegir…', command=lambda v=value: self.choose(v))
            button.grid(row=row, column=2, padx=(8, 0))
            self.inputs.extend([entry, button])
        self.status = tk.StringVar(value='Pausado')
        ttk.Label(frame, textvariable=self.status).grid(row=5, column=0, sticky='w', pady=15)
        self.toggle_button = ttk.Button(frame, text='Iniciar', command=self.toggle)
        self.toggle_button.grid(row=5, column=2)
        self.reorder_button = ttk.Button(frame, text='Reordenar por mes de modificación…', command=self.reorder)
        self.reorder_button.grid(row=7, column=0, columnspan=3, sticky='w', pady=(12, 0))
        ttk.Label(frame, text='Incluye los archivos existentes. Se guardan en subcarpetas por día (AAAA-MM-DD).\nMinimizar mantiene la app activa; cerrar detiene la organización.').grid(row=6, column=0, columnspan=3, sticky='w')
        ttk.Label(frame, text='Actividad · lo que está haciendo la aplicación').grid(row=8, column=0, columnspan=3, sticky='w', pady=(15, 5))
        history = ttk.Frame(frame)
        history.grid(row=9, column=0, columnspan=3, sticky='nsew')
        self.log = tk.Text(history, height=10, state='disabled', wrap='word',
                           font=('TkDefaultFont', 12), padx=10, pady=10)
        scrollbar = ttk.Scrollbar(history, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.log.pack(side='left', fill='both', expand=True)
        frame.rowconfigure(9, weight=1)
        try:
            settings = json.loads(CONFIG.read_text(encoding='utf-8'))
            for key, value in self.values.items():
                value.set(settings.get(key, ''))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as error:
            messagebox.showwarning('Configuración', f'No se pudo leer la configuración: {error}')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.record('Lista para comenzar. Revisá las carpetas y presioná Iniciar.\n'
                    'Por ahora no se está moviendo ningún archivo.')
        root.after(150, self.poll)

    def record(self, message):
        self.events.put(f'[{datetime.now():%H:%M:%S}] {message}')

    def choose(self, value):
        folder = filedialog.askdirectory()
        if folder:
            value.set(folder)

    def toggle(self):
        if self.worker and self.worker.is_alive():
            self.stop.set()
            self.status.set('Pausando…')
            self.record('Pausa solicitada. Esperá un momento mientras se detiene la organización.')
            self.toggle_button.configure(state='disabled')
            return
        try:
            settings = {key: value.get().strip() for key, value in self.values.items()}
            if not settings['source']:
                raise ValueError('Elegí la carpeta de descarga.')
            rules = {'.' + ext: settings[ext] for ext in ('json', 'pdf') if settings[ext]}
            if not rules:
                raise ValueError('Elegí al menos un destino.')
            engine = Organizer(settings['source'], rules, self.record)
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix('.tmp')
            temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding='utf-8')
            temporary.replace(CONFIG)
        except (OSError, ValueError) as error:
            self.record(f'No se pudo iniciar. {error}\nRevisá las rutas y volvé a presionar Iniciar.')
            messagebox.showerror('Revisá las carpetas', str(error))
            return
        self.stop.clear()
        self.manual = False
        self.reorder_button.configure(state='disabled')
        for widget in self.inputs:
            widget.configure(state='disabled')
        self.status.set('Activo · revisando cada 3 segundos')
        self.toggle_button.configure(text='Pausar')
        self.record(f'Organización iniciada. Revisando cada 3 segundos:\n{engine.source}\n'
                    'También se organizarán los archivos que ya estaban en esta carpeta.')
        self.record('Dentro de cada destino se creará una carpeta con la fecha del día en que se mueve el archivo '
                    '(año-mes-día), según la fecha local de esta computadora.')
        for ext in ('json', 'pdf'):
            destination = engine.rules.get('.' + ext)
            self.record(f'Archivos {ext.upper()}: se moverán a\n{destination}' if destination
                        else f'Archivos {ext.upper()}: se dejarán en la carpeta de descarga.')
        self.record('Esperando archivos listos para mover. Los recién descargados pueden tardar unos segundos.')
        self.worker = threading.Thread(target=self.run, args=(engine,), daemon=True)
        self.worker.start()

    def reorder(self):
        if self.worker is not None:
            return
        try:
            rules = {'.' + ext: self.values[ext].get().strip()
                     for ext in ('json', 'pdf') if self.values[ext].get().strip()}
            engine = Reorganizer(rules, self.record)
        except (OSError, ValueError) as error:
            messagebox.showerror('Revisá los destinos', str(error))
            return
        destinations = '\n'.join(f'{ext.upper().lstrip(".")}: {folder}' for ext, folder in engine.rules.items())
        if not messagebox.askokcancel('Reordenar archivos guardados',
                'Se revisarán estas carpetas y todas sus subcarpetas:\n\n' + destinations +
                '\n\nCada archivo se moverá a una carpeta AAAA-MM (por ejemplo, 2026-10 para octubre) según su última modificación, '
                'usando la hora local de esta computadora. Esa fecha puede ser distinta de la fecha de la factura. '
                'Los nombres repetidos se numerarán para conservar ambos archivos.\n\n'
                'Esta acción se ejecuta una sola vez. La organización automática seguirá usando el día actual.',
                parent=self.root):
            return
        self.stop.clear()
        self.manual = True
        for widget in self.inputs:
            widget.configure(state='disabled')
        self.reorder_button.configure(state='disabled')
        self.toggle_button.configure(text='Detener', state='normal')
        self.status.set('Reordenando archivos guardados…')
        self.record('Reordenamiento manual iniciado por mes de modificación.\n' + destinations)
        self.worker = threading.Thread(target=engine.run_once, args=(self.stop,), daemon=True)
        self.worker.start()

    def run(self, engine):
        last_error = None
        while not self.stop.is_set():
            try:
                engine.scan(self.stop)
                if last_error is not None:
                    self.record('La carpeta de descarga vuelve a estar disponible. Continuando la organización.')
                last_error = None
            except OSError as error:
                if str(error) != last_error:
                    self.record('No se puede revisar la carpeta de descarga. Comprobá que exista y que tengas permiso para abrirla.\n'
                                f'Se volverá a intentar automáticamente. Detalle: {error}')
                last_error = str(error)
            self.stop.wait(3)

    def poll(self):
        while not self.events.empty():
            at_bottom = self.log.yview()[1] >= 0.99
            self.log.configure(state='normal')
            self.log.insert('end', self.events.get_nowait() + '\n\n')
            excess = int(self.log.index('end-1c').split('.')[0]) - 500
            if excess > 0:
                self.log.delete('1.0', f'{excess + 1}.0')
            if at_bottom:
                self.log.see('end')
            self.log.configure(state='disabled')
        if self.worker and not self.worker.is_alive():
            self.worker = None
            for widget in self.inputs:
                widget.configure(state='normal')
            self.toggle_button.configure(text='Iniciar', state='normal')
            self.reorder_button.configure(state='normal')
            self.status.set('Pausado')
            if not self.manual:
                self.record('Organización detenida. No se moverán más archivos hasta que presionés Iniciar.')
            self.manual = False
        self.root.after(150, self.poll)

    def close(self):
        self.stop.set()
        if self.worker and self.worker.is_alive():
            self.status.set('Terminando…')
            self.root.after(100, self.close)
        else:
            self.root.destroy()


if __name__ == '__main__':
    if sys.platform == 'darwin' and tk.TkVersion < 8.6:
        raise SystemExit(
            'Este Python usa un Tk antiguo que puede mostrar una ventana vacía.\n'
            'Abrí Iniciar.command para usar un Python con Tk actualizado.'
        )
    root = tk.Tk()
    App(root)
    root.mainloop()
