"""Полный лог каждого прогона — в файл на томе (DATA_DIR/logs/run-<UTC>.log).

Railway отдаёт по развёртыванию только последние 50 строк: 15.11 «Deployment crashed» случился
раньше этих строк, и причину установить не удалось. Теперь всё, что прогон пишет в stdout и stderr,
необработанный traceback, сигнал остановки и аварийный дамп faulthandler дублируются в файл
построчно, так что даже убитый посреди сборки контейнер оставляет лог до последней строки.
В консоль (railway logs) идёт то же, что и раньше.
"""

import faulthandler
import signal
import sys
import traceback
from datetime import datetime, timezone

from . import config

KEEP = 60  # прогонов; один в день по расписанию — это два месяца
TAIL = 12  # строк прошлого лога в начале следующего прогона


class _Tee:
    def __init__(self, stream, file):
        self._stream, self._file = stream, file

    def write(self, text):
        self._stream.write(text)
        self._copy(lambda: (self._file.write(text), self._file.flush()))
        return len(text)

    def flush(self):
        self._stream.flush()
        self._copy(lambda: self._file.flush())

    def _copy(self, action):
        # Том заполнился посреди прогона: дальше пишем только в консоль, ролик важнее лога.
        if self._file is None:
            return
        try:
            action()
        except (OSError, ValueError) as error:
            self._file = None
            self._stream.write(f"ПРЕДУПРЕЖДЕНИЕ: запись лога прогона прекращена: {error}\n")

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _prune(logs) -> None:
    old = sorted(logs.glob("run-*.log"))
    for path in old[: max(0, len(old) - (KEEP - 1))]:
        path.unlink(missing_ok=True)


def _previous_tail(logs) -> str:
    # Том читается только из работающего контейнера, а cron-служба между прогонами стоит,
    # поэтому конец прошлого лога печатается в railway logs следующего прогона.
    old = sorted(logs.glob("run-*.log"))
    if not old:
        return ""
    tail = old[-1].read_text(encoding="utf-8", errors="replace").splitlines()[-TAIL:]
    return "\n".join([f"конец прошлого прогона ({old[-1].name}):"] + [f"  | {line}" for line in tail])


def _on_term(signum, _frame):
    print(f"получен сигнал {signal.Signals(signum).name} — прогон остановлен снаружи",
          file=sys.stderr, flush=True)
    raise SystemExit(128 + signum)


def _open_log():
    logs = config.DATA_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    _prune(logs)
    previous = _previous_tail(logs)
    path = logs / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.log"
    file = open(path, "a", encoding="utf-8")
    if previous:  # только в консоль: в файле прошлого прогона он и так есть
        print(previous, flush=True)
    print(f"лог прогона: {path}", flush=True)
    return file


def run_logged(fn, args) -> int:
    try:
        file = _open_log()
    except OSError as error:
        print(f"ПРЕДУПРЕЖДЕНИЕ: лог прогона в файл не ведётся: {error}", file=sys.stderr, flush=True)
        return fn(args)
    out, err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Tee(out, file), _Tee(err, file)
    try:
        faulthandler.enable(file=file)
    except (OSError, ValueError, AttributeError):  # у файла нет fileno — без аварийного дампа
        pass
    old_term = signal.signal(signal.SIGTERM, _on_term)
    code = 1
    try:
        code = fn(args)
        return code
    except SystemExit as stop:
        code = stop.code if isinstance(stop.code, int) else 1
        raise
    except Exception:
        # Печатаем здесь, а не на верхнем уровне: иначе traceback не попадёт в файл.
        traceback.print_exc()
        return code
    finally:
        print(f"код выхода {code}", file=sys.stderr, flush=True)
        signal.signal(signal.SIGTERM, old_term)
        faulthandler.disable()
        sys.stdout, sys.stderr = out, err
        try:
            file.close()
        except OSError:
            pass
