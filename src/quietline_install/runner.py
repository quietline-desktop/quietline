"""Ядро установщика: системные команды, состояние с журналом изменений, шаги и их запуск."""

import fcntl
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from quietline_install.texts import text

_WORDS = r'(?:password|passwd|pwd|secret|token|psk)'
_VALUE = r"""("[^"]*"|'[^']*'|\S+)"""
_SECRETS = [
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)', re.S),
     '[private key hidden]'),
    (re.compile(r'(?i)(\bauthorization\s*[=:]\s*(?:basic|bearer)\s+)\S+'), r'\1***'),
    (re.compile(r'(?i)\b(bearer)\s+\S+'), r'\1 ***'),
    # key=value, key: value, "key": "value" с любым префиксом (access_token, GITHUB_TOKEN, wifi-sec.psk)
    (re.compile(r'(?i)([\w.-]*' + _WORDS + r'["\']?\s*[=:]\s*)' + _VALUE), r'\1***'),
    # --password value, wifi-sec.psk value
    (re.compile(r'(?i)((?<![\w-])(?:--?|[\w-]+\.)[\w.-]*' + _WORDS + r'\s+)' + _VALUE), r'\1***'),
    (re.compile(r'\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}'), '***'),
]


def redact(text: str) -> str:
    """Скрывает пароли, токены и закрытые ключи в строке журнала и вывода."""
    for pattern, replacement in _SECRETS:
        text = pattern.sub(replacement, text)
    return text


def _stamp() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


def _write_json_atomic(path: Path, data: dict) -> None:
    """Пишет JSON через временный файл в том же каталоге; права 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


class System:
    """Единственное место, где установщик запускает системные команды (списки аргументов, без оболочки)."""

    def __init__(self, log: Callable[[str], None] = lambda line: None):
        self.log = log

    def run(self, args: list[str], sudo: bool = False, cwd=None, input: str | None = None,
            interactive: bool = False, check: bool = True, env: dict | None = None) -> str:
        """Интерактивная команда сохраняет терминал: видны запросы, sudo и ход работы."""
        command = ['sudo', *args] if sudo else list(args)
        self.log('$ ' + ' '.join(command))
        try:
            if interactive:
                result = self._interactive(command, cwd, env)
                output = ''
            else:
                result = subprocess.run(command, cwd=cwd, input=input, capture_output=True, text=True,
                                        check=False, env=self._env(env))
                output = result.stdout
        except FileNotFoundError:
            # Нет программы — обычная неудачная команда с кодом 127.
            if check:
                raise subprocess.CalledProcessError(127, command, '', f'{command[0]}: command not found')
            return ''
        if check and result.returncode:
            raise subprocess.CalledProcessError(result.returncode, command, output, getattr(result, 'stderr', ''))
        return output

    def _interactive(self, command: list[str], cwd, env):
        """Ctrl+C достаётся только дочерней команде: установщик не убивает pacman посреди транзакции.

        Прерванная пользователем команда (код 130 или SIGINT) останавливает установщик.
        """
        try:
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except ValueError:
            previous = None
        try:
            result = subprocess.run(command, cwd=cwd, check=False, env=self._env(env))
        finally:
            if previous is not None:
                signal.signal(signal.SIGINT, previous)
        if result.returncode in (130, -signal.SIGINT):
            self.log(f'interrupted: {" ".join(command)}')
            raise KeyboardInterrupt
        return result

    @staticmethod
    def _env(extra: dict | None):
        return {**os.environ, **extra} if extra else None

    def ok(self, args: list[str]) -> bool:
        """Команда завершилась с кодом 0; нет программы — False."""
        try:
            return subprocess.run(args, capture_output=True, check=False).returncode == 0
        except OSError:
            return False


def system_path(ctx: 'Ctx', path: str) -> Path:
    """Путь системного файла внутри `ctx.root` (в тестах — временный каталог)."""
    return ctx.root / Path(path).relative_to('/')


def read_system_file(ctx: 'Ctx', path: str) -> str | None:
    try:
        return system_path(ctx, path).read_text(encoding='utf-8')
    except OSError:
        return None


def write_system_file(ctx: 'Ctx', path: str, content: str) -> None:
    """Пишет файл root через `sudo tee` во временный файл рядом и переименовывает его на место."""
    temp = path + '.quietline-new'
    ctx.system.run(['tee', temp], sudo=True, input=content)
    ctx.system.run(['chmod', '0644', temp], sudo=True)
    ctx.system.run(['mv', '-f', temp, path], sudo=True)


def backup_system_file(ctx: 'Ctx', path: str) -> str:
    """Копия файла root рядом (`<файл>.quietline-<время>`), записанная в журнал изменений."""
    backup = f'{path}.quietline-{time.strftime("%Y%m%d-%H%M%S")}'
    ctx.system.run(['cp', '-a', path, backup], sudo=True)
    ctx.record({'kind': 'file', 'path': path, 'backup': backup})
    return backup


class StepFailed(Exception):
    """Шаг остановлен: message — что случилось, action — что делать пользователю."""

    def __init__(self, message: str, action: str = ''):
        super().__init__(message)
        self.action = action


@dataclass
class State:
    """Содержимое `install.json`; без `path` в файл не сохраняется."""

    path: Path | None = None
    version: int = 1
    installer_language: str | None = None
    system_language: str | None = None
    selection: dict = field(default_factory=dict)
    snapshot: dict | None = None
    done: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)
    failed: str | None = None
    error: str | None = None
    changes: list = field(default_factory=list)
    finished: bool = False
    rolled_back: bool = False

    _TYPES = {'selection': dict, 'done': dict, 'skipped': list, 'changes': list}

    @classmethod
    def load(cls, path: Path) -> 'State':
        """Читает состояние; повреждённый файл откладывается в `.broken-<время>`, состояние пустое."""
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return cls(path=path)
        except (OSError, ValueError):
            raw = None
        state = cls._from_json(path, raw) if isinstance(raw, dict) else None
        if state is None:
            try:
                path.rename(path.with_name(f'{path.name}.broken-{time.strftime("%Y%m%d-%H%M%S")}'))
            except OSError:
                pass
            return cls(path=path)
        return state

    @classmethod
    def _from_json(cls, path: Path, raw: dict) -> 'State | None':
        snapshot = raw.get('snapshot')
        if snapshot is not None and not isinstance(snapshot, dict):
            return None
        values = {'selection': raw.get('selection', {}), 'done': raw.get('done', {}),
                  'skipped': raw.get('skipped', []), 'changes': raw.get('changes', [])}
        if any(not isinstance(values[name], kind) for name, kind in cls._TYPES.items()):
            return None
        return cls(path=path, version=raw.get('version', 1),
                   installer_language=raw.get('installerLanguage'), system_language=raw.get('systemLanguage'),
                   snapshot=snapshot, failed=raw.get('failed'), error=raw.get('error'),
                   finished=bool(raw.get('finished', False)),
                   rolled_back=bool(raw.get('rolledBack', False)), **values)

    def to_json(self) -> dict:
        return {'version': self.version, 'installerLanguage': self.installer_language,
                'systemLanguage': self.system_language, 'selection': self.selection, 'snapshot': self.snapshot,
                'done': self.done, 'skipped': self.skipped, 'failed': self.failed, 'error': self.error,
                'changes': self.changes,
                'finished': self.finished, 'rolledBack': self.rolled_back}

    def save(self) -> None:
        if self.path is not None:
            _write_json_atomic(self.path, self.to_json())


@dataclass
class Ctx:
    """Всё, что нужно шагам: система, пути, диалог, вывод и общее состояние установки."""

    system: object
    home: Path
    repo: Path
    # Вопрос «да / нет»: `ask(question, default=False)`; Enter без выбора даёт `default`.
    ask: Callable[..., bool]
    out: Callable[[str], None] = print
    dry_run: bool = False
    root: Path = Path('/')
    language: str = 'en'
    state: State = field(default_factory=State)
    log: Callable[[str], None] = field(default=lambda line: None)
    # Просмотр инструкций пакета AUR: `review(name, lines)` — True, если собирать; None — печать и вопрос.
    review: Callable[[str, list[str]], bool] | None = None

    def t(self, key: str, **values) -> str:
        """Текст экрана на языке установщика."""
        return text(self.language, key, **values)

    def record(self, change: dict) -> None:
        """Дописывает изменение в журнал и сразу сохраняет состояние."""
        self.state.changes.append(change)
        self.state.save()


@dataclass
class Step:
    id: str
    title_key: str
    source: str
    check: Callable[[Ctx], bool]
    run: Callable[[Ctx], None]
    manual: bool = False


class Runner:
    """Запускает шаги по порядку: готовые пропускает, первую неудачу запоминает и останавливается."""

    def __init__(self, steps: list[Step], ctx: Ctx, log_path: Path):
        self.steps, self.ctx, self.log_path = steps, ctx, Path(log_path)
        ctx.log = self.log

    def log(self, line: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, 'a', encoding='utf-8') as handle:
            handle.write(f'{_stamp()} {redact(line)}\n')
        os.chmod(self.log_path, 0o600)

    def _say(self, line: str) -> None:
        self.ctx.out(redact(line))
        self.log(line)

    def _report(self, step: Step, status: str, **values) -> None:
        """Ход шага: на экран — с номером «[7/25]» на языке установщика, в журнал — по-английски с id шага."""
        try:
            title = self.ctx.t(step.title_key)
        except KeyError:
            title = step.id
        number = f'[{self.steps.index(step) + 1}/{len(self.steps)}] '
        self.ctx.out(number + redact(self.ctx.t(f'progress.{status}', step=f'{title} [{step.source}]', **values)))
        self.log(text('en', f'progress.{status}', step=f'{step.id} [{step.source}]', **values))

    def _done(self, step: Step) -> bool:
        """Проверка, которая не может выполниться (нет программы), означает «не сделано», а не падение."""
        try:
            return bool(step.check(self.ctx))
        except Exception as exc:
            self.log(f'{step.id}: check crashed: {exc!r}')
            return False

    @contextmanager
    def locked(self):
        """Замок `install.lock` рядом с состоянием: второй установщик получает StepFailed."""
        path = self.ctx.state.path
        if path is None:
            yield
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path.parent / 'install.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StepFailed('another installer is running',
                                 'Wait for it to finish, or close it, then run ./install.sh again.') from None
            yield
        finally:
            os.close(descriptor)

    def run(self, start: str | None = None) -> bool:
        ids = [step.id for step in self.steps]
        if start is not None and start not in ids:
            raise StepFailed(f'unknown step: {start}', f'Known steps: {", ".join(ids)}.')
        if start in self.ctx.state.skipped and not self.ctx.dry_run:
            # `--from` пропущенного шага возвращает его к выполнению.
            self.ctx.state.skipped.remove(start)
            self.ctx.state.save()
        if self.ctx.dry_run:
            return self._run(ids.index(start) if start else 0)
        with self.locked():
            return self._run(ids.index(start) if start else 0)

    def _run(self, begin: int) -> bool:
        state = self.ctx.state
        for step in self.steps[begin:]:
            if self._done(step):
                self._report(step, 'skipped')
                continue
            if self.ctx.dry_run:
                self._report(step, 'willRun')
                continue
            self._report(step, 'running')
            try:
                step.run(self.ctx)
                if not self._done(step):
                    raise StepFailed('the action finished but the result check failed',
                                     'See the output above and the install log.')
            except Exception as exc:  # любая ошибка останавливает шаг с подсказкой, без traceback
                action = getattr(exc, 'action', '') or 'See the install log.'
                reason = (getattr(exc, 'stderr', '') or '').strip().splitlines()[-3:]
                if reason:
                    action = f'Reason: {" / ".join(reason)}. {action}'
                state.failed, state.error, state.finished = step.id, redact(f'{exc}. {action}'), False
                state.save()
                self._report(step, 'failed', reason=f'{exc}. {action}')
                return False
            state.done[step.id] = time.strftime('%Y-%m-%dT%H:%M:%S')
            state.failed = state.error = None
            state.save()
            self._report(step, 'done')
        if not self.ctx.dry_run:
            state.failed = state.error = None
            state.finished = True
            state.save()
        return True

    def status(self) -> list[tuple[str, str]]:
        failed = self.ctx.state.failed
        skipped = self.ctx.state.skipped
        return [(step.id, 'skipped' if step.id in skipped else 'done' if self._done(step)
                 else 'failed' if step.id == failed else 'pending')
                for step in self.steps]
