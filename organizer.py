"""Motor independiente de la interfaz. No recorre subcarpetas."""
from pathlib import Path
from datetime import date, datetime
import os
import shutil
import time


class Organizer:
    def __init__(self, source, rules, log=print):
        self.source = Path(source).resolve()
        self.rules = {ext.lower(): Path(folder).resolve() for ext, folder in rules.items()}
        self.log = log
        self.seen = {}
        self.notices = {}
        if not self.source.is_dir():
            raise ValueError('La carpeta de origen no existe.')
        for folder in self.rules.values():
            if folder == self.source:
                raise ValueError('El destino debe ser diferente del origen.')
            folder.mkdir(parents=True, exist_ok=True)

    def scan(self, stop):
        current = set()
        for source in self.source.iterdir():
            if stop.is_set():
                break
            if source.is_symlink() or not source.is_file():
                continue
            destination = self.rules.get(source.suffix.lower())
            if destination is None:
                continue
            current.add(source)
            try:
                stat = source.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
                previous = self.seen.get(source)
                self.seen[source] = signature
                # Firefox conserva un .part mientras descarga. Además, esperamos
                # dos observaciones iguales y al menos diez segundos sin cambios.
                if (previous != signature or time.time() - stat.st_mtime < 10
                        or source.with_name(source.name + '.part').exists()):
                    self.notice(source, f'Archivo detectado: «{source.name}».\n'
                                'Esperando a que deje de cambiar antes de moverlo. No tenés que hacer nada.')
                    continue
                # Se calcula para cada movimiento: cambia de carpeta al pasar
                # la medianoche, aunque la aplicación siga abierta.
                destination = destination / date.today().isoformat()
                destination.mkdir(parents=True, exist_ok=True)
                self.move(source, destination, signature, stop)
            except InterruptedError:
                self.notice(source, f'Movimiento pendiente: «{source.name}».\n'
                            'Se interrumpió por una pausa o porque la descarga sigue en curso. Se revisará cuando la organización esté activa.')
            except OSError as error:
                self.notice(source, f'No se pudo mover «{source.name}».\n'
                            f'Destino: {destination}\n'
                            'Comprobá que la carpeta esté disponible, tenga espacio y permita guardar archivos. '
                            f'Se volverá a intentar mientras la organización esté activa.\nDetalle: {error}')
        self.seen = {p: s for p, s in self.seen.items() if p in current}
        self.notices = {p: s for p, s in self.notices.items() if p in current}

    def notice(self, source, message):
        if self.notices.get(source) != message:
            self.log(message)
            self.notices[source] = message

    def move(self, source, folder, signature, stop):
        number = 0
        while not stop.is_set():
            name = source.name if number == 0 else f'{source.stem} ({number}){source.suffix}'
            target = folder / name
            try:
                output = target.open('xb')
                break
            except FileExistsError:
                number += 1
        else:
            return
        try:
            with output, source.open('rb') as incoming:
                while True:
                    if stop.is_set():
                        raise InterruptedError('Movimiento pausado')
                    data = incoming.read(1024 * 1024)
                    if not data:
                        break
                    output.write(data)
                output.flush()
                os.fsync(output.fileno())
            stat = source.stat()
            if (stat.st_size, stat.st_mtime_ns) != signature:
                raise OSError('El archivo sigue cambiando; se intentará después.')
            if stop.is_set() or source.with_name(source.name + '.part').exists():
                raise InterruptedError('Movimiento pausado o descarga en curso')
            shutil.copystat(source, target)
            source.unlink()
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        message = (f'Archivo {source.suffix.lstrip(".").upper()} organizado: «{source.name}».\n'
                   f'Lo podés encontrar en: {target}\n'
                   'Ya no está en su ubicación anterior.')
        if number:
            message += (f'\nSe guardó como «{target.name}» porque ya había un archivo con ese nombre. '
                        'El archivo anterior se conservó.')
        self.log(message)
        return target


class Reorganizer(Organizer):
    """Reordena una sola vez los destinos existentes; reutiliza la copia segura."""

    def __init__(self, rules, log=print):
        self.rules = {ext.lower(): Path(folder).resolve() for ext, folder in rules.items()}
        self.log = log
        if not self.rules:
            raise ValueError('Elegí al menos una carpeta de destino.')
        for folder in self.rules.values():
            if not folder.is_dir():
                raise ValueError(f'La carpeta de destino no existe: {folder}')
        folders = set(self.rules.values())
        if any(a in b.parents for a in folders for b in folders if a != b):
            raise ValueError('Para reordenar, los destinos no deben estar uno dentro del otro.')

    def run_once(self, stop):
        counts = dict(moved=0, unchanged=0, skipped=0, errors=0)
        candidates = []
        daily_folders = set()

        def walk_error(error):
            counts['errors'] += 1
            self.log(f'No se pudo revisar una carpeta: {error}')

        # Tomar una lista primero evita volver a recorrer archivos recién movidos.
        for ext, folder in self.rules.items():
            for current, dirs, files in os.walk(folder, onerror=walk_error, followlinks=False):
                if stop.is_set():
                    break
                dirs[:] = [name for name in dirs
                           if not (Path(current) / name).is_symlink()
                           and not getattr(os.path, 'isjunction', lambda _: False)(Path(current) / name)]
                for name in dirs:
                    try:
                        if len(name) == 10 and date.fromisoformat(name).isoformat() == name:
                            daily_folders.add(Path(current) / name)
                    except ValueError:
                        pass
                candidates.extend((Path(current) / name, folder) for name in files
                                  if Path(name).suffix.lower() == ext)
            if stop.is_set():
                break

        for source, folder in candidates:
            if stop.is_set():
                break
            try:
                if source.is_symlink() or not source.is_file():
                    counts['skipped'] += 1
                    continue
                stat = source.stat()
                if (time.time() - stat.st_mtime < 10
                        or source.with_name(source.name + '.part').exists()):
                    counts['skipped'] += 1
                    self.log(f'Se dejó «{source.name}» donde está porque es reciente o tiene una descarga pendiente.')
                    continue
                destination = folder / datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m')
                if source.parent == destination:
                    counts['unchanged'] += 1
                    continue
                if destination.is_symlink() or getattr(os.path, 'isjunction', lambda _: False)(destination):
                    raise OSError(f'La carpeta del mes es un enlace: {destination}')
                destination.mkdir(parents=True, exist_ok=True)
                target = self.move(source, destination, (stat.st_size, stat.st_mtime_ns), stop)
                if target is not None:
                    counts['moved'] += 1
            except InterruptedError:
                counts['skipped'] += 1
                self.log(f'Se interrumpió el movimiento de «{source.name}». Podés volver a ejecutar la acción.')
            except (OSError, ValueError, OverflowError) as error:
                counts['errors'] += 1
                self.log(f'No se pudo reordenar «{source}». Detalle: {error}')
        removed = 0
        for folder in sorted(daily_folders, key=lambda path: len(path.parts), reverse=True):
            if stop.is_set():
                break
            try:
                # rmdir solo elimina carpetas vacías; no borra otros documentos.
                if not folder.is_symlink():
                    folder.rmdir()
                    removed += 1
            except OSError:
                pass  # Con contenido o sin permiso: conservar la carpeta.
        result = 'Reordenamiento detenido' if stop.is_set() else 'Reordenamiento terminado'
        self.log(f'{result}. Movidos: {counts["moved"]}; ya estaban en su mes: {counts["unchanged"]}; '
                 f'omitidos: {counts["skipped"]}; errores: {counts["errors"]}.\n'
                 f'Carpetas diarias vacías eliminadas: {removed}.\n'
                 'La organización automática permanece pausada.')
        return counts
