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
        self._file.write(text)
        self._file.flush()
        return len(text)

    def flush(self):
        self._stream.flush()
        self._file.flush()

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


def run_logged(fn, args) -> int:
    logs = config.DATA_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    _prune(logs)
    previous = _previous_tail(logs)
    path =logs / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.log"
    with open(path, "a", encoding="utf-8") as file:
        out, err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(out, file), _Tee(err, file)
        faulthandler.enable(file=file)
        old_term = signal.signal(signal.SIGTERM, _on_term)
        code = 1
        try:
            if previous:
                print(previous, flush=True)
            print(f"лог прогона: {path}", flush=True)
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
