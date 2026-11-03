"""Экраны установщика: чистые модели выбора, тонкая отрисовка на curses и вопрос «да / нет» в терминале.

Модели (`Choice`, `Checklist`, `Item`, `clip`, `scroll_top`, `answer_key`, `answer_text`, `choose_answer`)
не знают о curses и терминале и проверяются тестами; функции `ask_*`, `show_*`, `choose_*`,
`confirm_*`, `review_*` только рисуют и читают клавиши.

Клавиши: стрелки, Пробел — отметить, Enter — дальше или раскрыть, `r` — рекомендуемый набор,
Esc — назад (`GoBack`), `q` — выход без изменений (`Quit`).
"""

import curses
import os
import select
import sys
import termios
import tty
from dataclasses import dataclass, field
from typing import Callable, Iterable

from quietline_install.texts import TEXTS


class GoBack(Exception):
    """Пользователь нажал Esc: вернуться на предыдущий экран."""


class Quit(Exception):
    """Пользователь нажал q: выйти, ничего не меняя."""


@dataclass
class Choice:
    """Выбор одного варианта из списка."""

    options: list[str]
    index: int = 0

    def move(self, delta: int) -> None:
        self.index = max(0, min(len(self.options) - 1, self.index + delta))

    @property
    def value(self) -> str:
        return self.options[self.index]


@dataclass
class Item:
    """Пункт списка программ.

    `locked` — уже установлено: отмечено и не снимается. `children` — «Расширенные»,
    видны после раскрытия. `group` — заголовок раздела: только раскрывается, сам не выбирается.
    """

    id: str
    label: str
    checked: bool = False
    locked: bool = False
    children: list['Item'] = field(default_factory=list)
    expanded: bool = False
    group: bool = False


@dataclass
class Row:
    """Видимая строка списка: кнопка «Рекомендуемый набор», пункт или кнопка «Далее»."""

    kind: str  # 'recommended' | 'item' | 'next'
    item: Item | None = None
    depth: int = 0


class Checklist:
    """Список пунктов с курсором; первая строка — рекомендуемый набор (если `recommended` задан), последняя — «Далее».

    `recommended` — id рекомендуемого набора для кнопки и клавиши `r`; None — без кнопки.
    """

    def __init__(self, items: list[Item], recommended: frozenset[str] | set[str] | None = frozenset()):
        self.items = items
        self.recommended = recommended
        self.cursor = 0

    def rows(self) -> list[Row]:
        rows = [] if self.recommended is None else [Row('recommended')]

        def walk(items: list[Item], depth: int) -> None:
            for item in items:
                rows.append(Row('item', item, depth))
                if item.expanded:
                    walk(item.children, depth + 1)

        walk(self.items, 0)
        rows.append(Row('next'))
        return rows

    def current(self) -> Row:
        return self.rows()[self.cursor]

    def move(self, delta: int) -> None:
        self.cursor = max(0, min(len(self.rows()) - 1, self.cursor + delta))

    def toggle(self) -> None:
        """Отмечает или снимает пункт под курсором; заблокированный и заголовок не меняются."""
        item = self.current().item
        if item is not None and not item.locked and not item.group:
            item.checked = not item.checked

    def activate(self) -> None:
        """Enter на пункте: раскрывает заголовок и пункт с вложенными, остальные отмечает."""
        item = self.current().item
        if item is not None and (item.group or item.children):
            self.expand()
        else:
            self.toggle()

    def expand(self) -> None:
        """Раскрывает или сворачивает пункт под курсором, если у него есть вложенные."""
        item = self.current().item
        if item is not None and item.children:
            item.expanded = not item.expanded
            self.move(0)

    def selected(self) -> set[str]:
        """Идентификаторы отмеченных новых пунктов (в том числе вложенных); установленные не входят."""
        chosen: set[str] = set()

        def walk(items: list[Item]) -> None:
            for item in items:
                if item.checked and not item.locked and not item.group:
                    chosen.add(item.id)
                walk(item.children)

        walk(self.items)
        return chosen

    def apply_recommended(self, ids: set[str]) -> None:
        """Отмечает ровно рекомендуемые пункты; установленные остаются отмеченными."""

        def walk(items: list[Item]) -> None:
            for item in items:
                if not item.locked and not item.group:
                    item.checked = item.id in ids
                walk(item.children)

        walk(self.items)


@dataclass
class CheckResult:
    """Результат проверки: `id` — ключ `check.<id>`, `blocking` — без неё продолжать нельзя."""

    id: str
    ok: bool
    blocking: bool = True
    detail: str = ''


def clip(line: str, width: int) -> str:
    """Обрезает строку до ширины экрана; обрезанный конец помечается «~»."""
    if width <= 0:
        return ''
    if len(line) <= width:
        return line
    return line[: width - 1] + '~'


def scroll_top(cursor: int, top: int, height: int) -> int:
    """Первая видимая строка так, чтобы курсор оставался в окне высотой `height`."""
    if cursor < top:
        return cursor
    if cursor >= top + height:
        return cursor - height + 1
    return top


def wrap(text: str, width: int) -> list[str]:
    """Разбивает текст по словам на строки не шире `width`."""
    lines: list[str] = []
    for paragraph in text.split('\n'):
        current = ''
        for word in paragraph.split():
            if current and len(current) + 1 + len(word) > width:
                lines.append(current)
                current = word
            else:
                current = f'{current} {word}'.strip()
        lines.append(current)
    return lines


# --- отрисовка ---


def body_room(height: int) -> int:
    """Сколько строк остаётся телу экрана: заголовок, пустая строка и подсказка занимают остальное."""
    return max(1, height - 2 - FOOTER_LINES)

FOOTER_LINES = 2
ENTER_KEYS = (10, 13, curses.KEY_ENTER)
ESC = 27


def _prepare(stdscr) -> None:
    try:
        curses.set_escdelay(25)
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)


def _key(stdscr) -> int:
    """Читает клавишу; q выходит, Esc возвращает на шаг назад."""
    key = stdscr.getch()
    if key == ESC:
        raise GoBack
    if key in (ord('q'), ord('Q')):
        raise Quit
    return key


def _paint(stdscr, title: str, body: list[tuple[str, bool]], footer: str, top: int = 0) -> None:
    """Рисует заголовок, строки (текст, выделена ли) начиная с `top` и подсказку клавиш."""
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    stdscr.addstr(0, 1, clip(title, width - 2), curses.A_BOLD)
    room = body_room(height)
    for row, (line, selected) in enumerate(body[top:top + room]):
        stdscr.addstr(2 + row, 1, clip(line, width - 2), curses.A_REVERSE if selected else curses.A_NORMAL)
    for row, line in enumerate(wrap(footer, width - 2)[:FOOTER_LINES]):
        stdscr.addstr(height - FOOTER_LINES + row, 1, clip(line, width - 2), curses.A_DIM)
    stdscr.refresh()


def _menu(stdscr, title: str, intro: str, options: list[str], footer: str, index: int = 0) -> int:
    """Меню из одного выбора; возвращает индекс по Enter."""
    _prepare(stdscr)
    choice = Choice(options, index)
    top = 0
    while True:
        height, width = stdscr.getmaxyx()
        head = [(line, False) for line in wrap(intro, width - 2)] + [('', False)] if intro else []
        body = head + [(('> ' if i == choice.index else '  ') + option, i == choice.index) for i, option in enumerate(options)]
        top = scroll_top(len(head) + choice.index, top, body_room(height))
        _paint(stdscr, title, body, footer, top)
        key = _key(stdscr)
        if key == curses.KEY_UP:
            choice.move(-1)
        elif key == curses.KEY_DOWN:
            choice.move(1)
        elif key in ENTER_KEYS:
            return choice.index


def _read_text_screen(stdscr, title: str, lines: list[str], footer: str) -> None:
    """Показывает прокручиваемый текст до Enter."""
    _prepare(stdscr)
    top = 0
    while True:
        height, width = stdscr.getmaxyx()
        wrapped = [piece for line in lines for piece in (wrap(line, width - 2) or [''])]
        room = body_room(height)
        top = max(0, min(top, max(0, len(wrapped) - room)))
        _paint(stdscr, title, [(line, False) for line in wrapped], footer, top)
        key = _key(stdscr)
        if key == curses.KEY_UP:
            top -= 1
        elif key == curses.KEY_DOWN:
            top += 1
        elif key == curses.KEY_PPAGE:
            top -= room
        elif key == curses.KEY_NPAGE:
            top += room
        elif key in ENTER_KEYS:
            return


def ask_language(stdscr) -> str:
    """Первый экран, двуязычный: язык установщика ('ru' или 'en'). Esc здесь ничего не делает."""
    while True:
        try:
            index = _menu(stdscr, 'Language / Язык', 'Choose the installer language. Выберите язык установщика.',
                          ['Русский', 'English'], 'Enter - OK   q - quit / выход')
        except GoBack:
            continue
        return ['ru', 'en'][index]


def show_checks(stdscr, ctx, results: list[CheckResult]) -> bool:
    """Показывает проверки; True — можно продолжать. Без Btrfs просит подтверждение (Enter).

    Esc возвращает к выбору языка (`GoBack`).
    """
    lines = []
    for result in results:
        status = 'ok' if result.ok else ('fail' if result.blocking else 'warn')
        detail = f' ({result.detail})' if result.detail else ''
        lines.append(f'[{ctx.t("check.status." + status)}] {ctx.t("check." + result.id)}{detail}')
    if any(not r.ok and r.blocking for r in results):
        lines += ['', ctx.t('checks.failed')]
        _read_text_screen(stdscr, ctx.t('checks.title'), lines, ctx.t('hint.close'))
        return False
    footer = ctx.t('hint.any')
    if any(not r.ok for r in results):
        lines += ['', ctx.t('checks.noBtrfs'), '', ctx.t('checks.noBtrfsConfirm')]
        footer = ctx.t('hint.confirm')
    _read_text_screen(stdscr, ctx.t('checks.title'), lines, footer)
    return True


def ask_system_language(stdscr, ctx, current: str) -> str:
    """Язык установленной системы ('ru' или 'en'); по умолчанию выбран `current`."""
    codes = ['ru', 'en']
    index = _menu(stdscr, ctx.t('systemLanguage.title'), ctx.t('systemLanguage.prompt'),
                  [ctx.t('language.ru'), ctx.t('language.en')], ctx.t('hint.menu'),
                  codes.index(current) if current in codes else 0)
    return codes[index]


def _row_label(ctx, row: Row) -> str:
    if row.kind == 'recommended':
        return f'[ {ctx.t("programs.recommended")} ]'
    if row.kind == 'next':
        return f'[ {ctx.t("programs.next")} ]'
    item = row.item
    indent = '    ' * row.depth
    if item.group:
        return f'{indent}{"-" if item.expanded else "+"} {item.label}'
    mark = '[x]' if item.checked else '[ ]'
    label = f'{indent}{mark} {item.label}'
    if item.locked:
        label += f' ({ctx.t("programs.installed")})'
    if item.children:
        label += f'   {"-" if item.expanded else "+"} {ctx.t("advanced")}'
    return label


def choose_programs(stdscr, ctx, checklist: Checklist):
    """Выбор программ: набор идентификаторов по «Далее» или строка 'recommended' по кнопке набора.

    Клавиша `r` только отмечает рекомендуемый набор и оставляет экран открытым.
    """
    _prepare(stdscr)
    top = 0
    while True:
        height, width = stdscr.getmaxyx()
        head = [(line, False) for line in wrap(ctx.t('programs.base'), width - 2)] + [('', False)]
        rows = checklist.rows()
        body = head + [(_row_label(ctx, row), i == checklist.cursor) for i, row in enumerate(rows)]
        top = scroll_top(len(head) + checklist.cursor, top, body_room(height))
        _paint(stdscr, ctx.t('programs.title'), body, ctx.t('hint.list'), top)
        key = _key(stdscr)
        if key == curses.KEY_UP:
            checklist.move(-1)
        elif key == curses.KEY_DOWN:
            checklist.move(1)
        elif key == ord(' '):
            checklist.toggle()
        elif key in (ord('r'), ord('R')):
            checklist.apply_recommended(set(checklist.recommended or ()))
        elif key in ENTER_KEYS:
            kind = checklist.current().kind
            if kind == 'recommended':
                return 'recommended'
            if kind == 'next':
                return checklist.selected()
            checklist.activate()


def choose_options(stdscr, ctx, checklist: Checklist, intro: str) -> set[str]:
    """Экран «Параметры»: отмеченные id по «Далее»; Пробел или Enter отмечают пункт."""
    _prepare(stdscr)
    top = 0
    while True:
        height, width = stdscr.getmaxyx()
        head = [(line, False) for line in wrap(intro, width - 2)] + [('', False)]
        rows = checklist.rows()
        body = head + [(_row_label(ctx, row), i == checklist.cursor) for i, row in enumerate(rows)]
        top = scroll_top(len(head) + checklist.cursor, top, body_room(height))
        _paint(stdscr, ctx.t('options.title'), body, ctx.t('hint.options'), top)
        key = _key(stdscr)
        if key == curses.KEY_UP:
            checklist.move(-1)
        elif key == curses.KEY_DOWN:
            checklist.move(1)
        elif key == ord(' '):
            checklist.toggle()
        elif key in ENTER_KEYS:
            if checklist.current().kind == 'next':
                return checklist.selected()
            checklist.activate()


def confirm_summary(stdscr, ctx, lines: list[str]) -> bool:
    """Сводка установки; Enter — начать (True), Esc — назад (False)."""
    try:
        _read_text_screen(stdscr, ctx.t('summary.title'), lines + ['', ctx.t('summary.question')], ctx.t('hint.confirm'))
    except GoBack:
        return False
    return True


def show_final(stdscr, ctx, lines: list[str]) -> bool:
    """Итог установки и меню «Перезагрузить сейчас / Позже»; True — перезагрузиться. Esc и q — позже."""
    try:
        index = _menu(stdscr, ctx.t('final.title'), '\n'.join(lines + ['', ctx.t('final.reboot')]),
                      [ctx.t('final.rebootNow'), ctx.t('final.later')], ctx.t('hint.final'))
    except (GoBack, Quit):
        return False
    return index == 0


def review_package(stdscr, ctx, name: str, lines: list[str]) -> bool:
    """Инструкции сборки пакета AUR; Enter — собрать (True), Esc или q — не собирать (False)."""
    try:
        _read_text_screen(stdscr, ctx.t('aur.reviewTitle', name=name),
                          lines + ['', ctx.t('aur.confirm', name=name)], ctx.t('aur.reviewHint'))
    except (GoBack, Quit):
        return False
    return True


def ask_resume(stdscr, ctx, failed_step: str, reason: str = '') -> str:
    """Незавершённая установка: 'continue', 'rollback' или 'quit'; `reason` — причина сбоя шага."""
    title = ctx.t(f'step.{failed_step}') if f'step.{failed_step}' in TEXTS['en'] else failed_step
    options = [ctx.t('resume.continue'), ctx.t('resume.rollback'), ctx.t('resume.quit')]
    intro = ctx.t('resume.failed', step=title)
    if reason:
        intro += ' ' + ctx.t('resume.reason', reason=reason)
    try:
        index = _menu(stdscr, ctx.t('resume.title'), intro, options, ctx.t('hint.menu'))
    except (GoBack, Quit):
        return 'quit'
    return ['continue', 'rollback', 'quit'][index]



# --- вопрос «да / нет» в терминале ---

# Буквами отвечают только `y` и `n` на любом языке установщика; кириллица ответом не считается.
YES_KEYS = ('y', 'Y')
NO_KEYS = ('n', 'N')
YES_WORDS = ('y', 'yes')
NO_WORDS = ('n', 'no')


def answer_key(key: str, answer: bool) -> tuple[bool, bool]:
    """Ответ после клавиши и принят ли он: ←/→ выбирают «Да» / «Нет», ↑/↓ и Tab переключают,
    Enter принимает выбранный, буквы отвечают сразу; прочие клавиши ничего не меняют."""
    if key == 'enter':
        return answer, True
    if key == 'left':
        return True, False
    if key == 'right':
        return False, False
    if key in ('up', 'down', 'tab'):
        return not answer, False
    if key in YES_KEYS:
        return True, True
    if key in NO_KEYS:
        return False, True
    return answer, False


def answer_text(line: str, default: bool) -> bool | None:
    """Ответ строкой: пустая — `default`, `y`/`yes` и `n`/`no`; другая — None."""
    word = line.strip().lower()
    if not word:
        return default
    if word in YES_WORDS:
        return True
    if word in NO_WORDS:
        return False
    return None


def choose_answer(keys: Iterable[str], default: bool, show: Callable[[bool], None] = lambda answer: None) -> bool:
    """Выбор ответа по клавишам, начиная с `default`; `show` рисует выбранный. Клавиши кончились — «нет»."""
    answer = default
    show(answer)
    for key in keys:
        answer, done = answer_key(key, answer)
        show(answer)
        if done:
            return answer
    return False


_ESCAPES = {b'[A': 'up', b'[B': 'down', b'[C': 'right', b'[D': 'left',
            b'OA': 'up', b'OB': 'down', b'OC': 'right', b'OD': 'left'}


def _terminal_keys(fd: int):
    """Клавиши терминала: 'enter', стрелки, 'tab', 'esc' или символ; конец ввода завершает поток."""
    while True:
        byte = os.read(fd, 1)
        if not byte:
            return
        if byte in (b'\r', b'\n'):
            yield 'enter'
        elif byte == b'\t':
            yield 'tab'
        elif byte == b'\x1b':
            sequence = b''
            while len(sequence) < 2 and select.select([fd], [], [], 0.05)[0]:
                sequence += os.read(fd, 1)
            yield _ESCAPES.get(sequence, 'esc')
        else:
            # Ведущий байт UTF-8 задаёт длину символа: кириллица — два байта.
            size = 2 if byte[0] >= 0xC0 else 1
            size = 3 if byte[0] >= 0xE0 else size
            size = 4 if byte[0] >= 0xF0 else size
            while len(byte) < size:
                byte += os.read(fd, 1)
            yield byte.decode('utf-8', errors='replace')


def ask_yes_no(ctx, question: str, default: bool = False, stdin=None, stdout=None) -> bool:
    """Вопрос под выводом шагов: строка «Да / Нет» со стрелками и Enter; без терминала — ответ строкой.

    Нажатое до вопроса (например, Enter во время сборки) сбрасывается и ответом не считается.
    """
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    yes, no = ctx.t('ask.yes'), ctx.t('ask.no')
    if not (stdin.isatty() and stdout.isatty()):
        while True:
            try:
                line = input(f'{question} [{"Y/n" if default else "y/N"}] ')
            except EOFError:
                return False
            answer = answer_text(line, default)
            if answer is not None:
                return answer

    def show(answer: bool, final: bool = False) -> None:
        def button(label: str, on: bool) -> str:
            return f'\x1b[7m {label} \x1b[0m' if on else f' {label} '
        hint = '' if final else f'   \x1b[2m{ctx.t("ask.hint")}\x1b[0m'
        stdout.write(f'\r\x1b[K  {button(yes, answer)} {button(no, not answer)}{hint}')
        stdout.flush()

    fd = stdin.fileno()
    saved = termios.tcgetattr(fd)
    stdout.write(question + '\n')
    try:
        tty.setcbreak(fd)
        termios.tcflush(fd, termios.TCIFLUSH)
        answer = choose_answer(_terminal_keys(fd), default, show)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    show(answer, final=True)
    stdout.write('\n')
    stdout.flush()
    return answer
