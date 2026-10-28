"""Ядро установщика: системные команды, состояние с журналом изменений, шаги и их запуск."""

import fcntl
import json
import os
import re
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
                result = subprocess.run(command, cwd=cwd, check=False, env=self._env(env))
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

    @staticmethod
    def _env(extra: dict | None):
        return {**os.environ, **extra} if extra else None

    def ok(self, args: list[str]) -> bool:
        """Команда завершилась с кодом 0; нет программы — False."""
        try:
            return subprocess.run(args, capture_output=True, check=False).returncode == 0
        except OSError:
            return False


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
    failed: str | None = None
    error: str | None = None
    changes: list = field(default_factory=list)
    finished: bool = False

    _TYPES = {'selection': dict, 'done': dict, 'changes': list}

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
                  'changes': raw.get('changes', [])}
        if any(not isinstance(values[name], kind) for name, kind in cls._TYPES.items()):
            return None
        return cls(path=path, version=raw.get('version', 1),
                   installer_language=raw.get('installerLanguage'), system_language=raw.get('systemLanguage'),
                   snapshot=snapshot, failed=raw.get('failed'), error=raw.get('error'),
                   finished=bool(raw.get('finished', False)), **values)

    def to_json(self) -> dict:
        return {'version': self.version, 'installerLanguage': self.installer_language,
                'systemLanguage': self.system_language, 'selection': self.selection, 'snapshot': self.snapshot,
                'done': self.done, 'failed': self.failed, 'error': self.error, 'changes': self.changes,
                'finished': self.finished}

    def save(self) -> None:
        if self.path is not None:
            _write_json_atomic(self.path, self.to_json())


@dataclass
class Ctx:
    """Всё, что нужно шагам: система, пути, диалог, вывод и общее состояние установки."""

    system: object
    home: Path
    repo: Path
    ask: Callable[[str], bool]
    out: Callable[[str], None] = print
    dry_run: bool = False
    root: Path = Path('/')
    language: str = 'en'
    state: State = field(default_factory=State)
    log: Callable[[str], None] = field(default=lambda line: None)

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
        if self.ctx.dry_run:
            return self._run(ids.index(start) if start else 0)
        with self.locked():
            return self._run(ids.index(start) if start else 0)

    def _run(self, begin: int) -> bool:
        state = self.ctx.state
        for step in self.steps[begin:]:
            label = f'{step.id} [{step.source}]'
            if self._done(step):
                self._say(f'{label}: skipped (already done)')
                continue
            if self.ctx.dry_run:
                self._say(f'{label}: will run')
                continue
            self._say(f'{label}: running')
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
                state.failed, state.error, state.finished = step.id, redact(str(exc)), False
                state.save()
                self._say(f'{label}: failed: {exc}. {action} Run ./install.sh again to continue.')
                return False
            state.done[step.id] = time.strftime('%Y-%m-%dT%H:%M:%S')
            state.failed = state.error = None
            state.save()
            self._say(f'{label}: done')
        if not self.ctx.dry_run:
            state.failed = state.error = None
            state.finished = True
            state.save()
        return True

    def status(self) -> list[tuple[str, str]]:
        failed = self.ctx.state.failed
        return [(step.id, 'done' if self._done(step) else 'failed' if step.id == failed else 'pending')
                for step in self.steps]
