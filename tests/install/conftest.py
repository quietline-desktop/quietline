import subprocess
from pathlib import Path

import pytest

from quietline_install.runner import Ctx, State


class FakeSystem:
    """Записывает системные команды; отвечает по самому длинному совпавшему префиксу argv (при равенстве — позднее)."""

    def __init__(self):
        self.answers = []
        self.calls = []

    def answer(self, prefix, stdout='', code=0):
        self.answers.append((list(prefix), stdout, code))

    def run(self, args, sudo=False, cwd=None, input=None, interactive=False, check=True, env=None):
        args = list(args)
        self.calls.append({"args": args, "sudo": sudo, "cwd": cwd, "input": input,
                           "interactive": interactive, "env": env})
        best = None
        for prefix, stdout, code in self.answers:
            if args[:len(prefix)] == prefix and (best is None or len(prefix) >= len(best[0])):
                best = (prefix, stdout, code)
        stdout, code = (best[1], best[2]) if best else ('', 0)
        if code and check:
            raise subprocess.CalledProcessError(code, args, stdout, '')
        return stdout

    def ok(self, args):
        try:
            self.run(args)
            return True
        except subprocess.CalledProcessError:
            return False

    def commands(self):
        return [call['args'] for call in self.calls]


@pytest.fixture
def system():
    return FakeSystem()


@pytest.fixture
def ctx(tmp_path, system):
    answers = []
    lines = []
    questions = []

    def ask(question, default=False):
        questions.append(question)
        context.defaults.append(default)
        return answers.pop(0) if answers else False

    context = Ctx(system=system, home=tmp_path / 'home', repo=Path(__file__).resolve().parents[2],
                  ask=ask, out=lines.append,
                  state=State.load(tmp_path / 'state' / 'install.json'))
    context.home.mkdir()
    context.answers = answers
    context.lines = lines
    context.questions = questions
    context.defaults = []
    return context
