import re

import pytest

from quietline_install import texts
from quietline_install import screens
from quietline_install.screens import (Checklist, Choice, Item, answer_key, answer_text, choose_answer,
                                         clip, scroll_top)

PLACEHOLDER = re.compile(r'\{(\w+)\}')

SECTION_KEYS = [
    'sectionBrowsers', 'sectionMessengers', 'sectionFiles', 'sectionCode', 'sectionPasswords',
    'sectionVpn', 'sectionRemote', 'sectionDocuments', 'sectionContainers', 'sectionDotnet',
    'sectionNode', 'sectionPython', 'sectionDevTools', 'advanced',
]
STEP_IDS = [
    'system-upgrade', 'repo-packages', 'graphics', 'locales', 'quietline-package', 'services',
    'hyprland-config', 'fish', 'tide', 'micro', 'quickshell-link', 'user-dirs', 'region', 'pins', 'greetd',
    'keyring', 'boot-theme', 'flatpak', 'fnm', 'uv', 'aur', 'default-shell', 'docker-group',
    'amneziavpn', 'snapshot-prepare', 'snapshot',
]


def sample_items():
    return [
        Item('chrome', 'Chrome', checked=False),
        Item('firefox', 'Firefox', checked=False),
        Item('dolphin', 'Dolphin', checked=True, locked=True),
        Item(
            'dotnet', '.NET', checked=False,
            children=[Item('dotnet-8', '.NET 8', checked=False), Item('dotnet-9', '.NET 9', checked=False)],
        ),
    ]


def go_to(checklist, item_id):
    checklist.cursor = 0
    for _ in range(len(checklist.rows())):
        row = checklist.rows()[checklist.cursor]
        if row.item is not None and row.item.id == item_id:
            return
        checklist.move(1)
    raise AssertionError(item_id)


def test_both_languages_have_the_same_keys_and_placeholders():
    assert texts.TEXTS['ru'].keys() == texts.TEXTS['en'].keys()
    for key, ru in texts.TEXTS['ru'].items():
        assert set(PLACEHOLDER.findall(ru)) == set(PLACEHOLDER.findall(texts.TEXTS['en'][key])), key


def test_required_keys_exist():
    for key in SECTION_KEYS + [f'step.{step}' for step in STEP_IDS]:
        assert key in texts.TEXTS['en'], key
        assert texts.TEXTS['en'][key] and texts.TEXTS['ru'][key]


def test_text_fills_values_and_falls_back_to_english(monkeypatch):
    assert texts.text('ru', 'resume.failed', step='fish') == texts.TEXTS['ru']['resume.failed'].format(step='fish')
    assert 'fish' in texts.text('en', 'resume.failed', step='fish')
    monkeypatch.setitem(texts.TEXTS['en'], 'only.en', 'only {x}')
    assert texts.text('ru', 'only.en', x=1) == 'only 1'
    assert texts.text('xx', 'advanced') == texts.TEXTS['en']['advanced']
    with pytest.raises(KeyError):
        texts.text('en', 'no.such.key')


def test_ctx_t_uses_the_context_language(ctx):
    ctx.language = 'ru'
    assert ctx.t('advanced') == texts.TEXTS['ru']['advanced']
    ctx.language = 'en'
    assert ctx.t('advanced') == texts.TEXTS['en']['advanced']


def test_locked_item_cannot_be_unchecked():
    checklist = Checklist(sample_items())
    go_to(checklist, 'dolphin')
    checklist.toggle()
    assert checklist.items[2].checked
    go_to(checklist, 'chrome')
    checklist.toggle()
    assert checklist.items[0].checked
    checklist.toggle()
    assert not checklist.items[0].checked


def test_recommended_selection_checks_only_recommended():
    checklist = Checklist(sample_items())
    go_to(checklist, 'firefox')
    checklist.toggle()
    checklist.apply_recommended({'chrome'})
    assert checklist.selected() == {'chrome'}
    assert checklist.items[2].checked


def test_advanced_children_are_hidden_until_expanded():
    checklist = Checklist(sample_items())
    ids = [row.item.id for row in checklist.rows() if row.item]
    assert 'dotnet-8' not in ids
    go_to(checklist, 'dotnet')
    checklist.expand()
    rows = checklist.rows()
    assert [row.item.id for row in rows if row.item][-2:] == ['dotnet-8', 'dotnet-9']
    assert [row.depth for row in rows if row.item and row.item.id == 'dotnet-8'] == [1]
    checklist.expand()
    assert 'dotnet-8' not in [row.item.id for row in checklist.rows() if row.item]


def test_selected_includes_checked_children():
    checklist = Checklist(sample_items())
    go_to(checklist, 'dotnet')
    checklist.expand()
    go_to(checklist, 'dotnet-8')
    checklist.toggle()
    assert checklist.selected() == {'dotnet-8'}


def test_group_item_is_not_selectable():
    group = Item('browsers', 'Browsers', checked=False, group=True, children=[Item('chrome', 'Chrome', checked=True)])
    checklist = Checklist([group])
    go_to(checklist, 'browsers')
    checklist.toggle()
    assert not group.checked
    assert checklist.selected() == {'chrome'}


def test_recommended_row_comes_first_and_next_row_last():
    checklist = Checklist(sample_items())
    rows = checklist.rows()
    assert rows[0].kind == 'recommended' and rows[-1].kind == 'next'
    assert checklist.current().kind == 'recommended'
    checklist.toggle()
    assert checklist.selected() == set()


def test_moving_past_the_ends_stays_in_range():
    choice = Choice(['a', 'b'])
    choice.move(-1)
    assert choice.index == 0
    choice.move(5)
    assert choice.index == 1
    checklist = Checklist(sample_items())
    checklist.move(-3)
    assert checklist.cursor == 0
    checklist.move(100)
    assert checklist.cursor == len(checklist.rows()) - 1


def test_collapsing_keeps_cursor_in_range():
    checklist = Checklist(sample_items())
    go_to(checklist, 'dotnet')
    checklist.expand()
    go_to(checklist, 'dotnet-9')
    checklist.items[3].expanded = False
    checklist.move(0)
    assert checklist.cursor < len(checklist.rows())


def test_clip_cuts_to_width():
    assert clip('abcdef', 4) == 'abc~'
    assert clip('abc', 4) == 'abc'
    assert clip('abc', 0) == ''


def test_scroll_top_keeps_cursor_visible():
    assert scroll_top(cursor=0, top=0, height=5) == 0
    assert scroll_top(cursor=7, top=0, height=5) == 3
    assert scroll_top(cursor=1, top=3, height=5) == 1
    assert scroll_top(cursor=4, top=0, height=5) == 0


def test_every_hint_fits_two_lines_of_an_80_column_console():
    from quietline_install.screens import FOOTER_LINES, wrap

    hints = [(lang, key) for lang in texts.TEXTS for key in texts.TEXTS[lang] if key.startswith(('hint.', 'final.hint', 'aur.reviewHint'))]
    assert hints
    for lang, key in hints:
        lines = wrap(texts.TEXTS[lang][key], 78)
        assert len(lines) <= FOOTER_LINES, (lang, key)
        assert all(len(line) <= 78 for line in lines), (lang, key)


def test_enter_takes_the_default_answer():
    assert choose_answer(['enter'], default=True) is True
    assert choose_answer(['enter'], default=False) is False


def test_arrows_choose_and_enter_confirms():
    shown = []
    assert choose_answer(['right', 'enter'], default=True, show=shown.append) is False
    assert choose_answer(['left', 'enter'], default=False) is True
    assert choose_answer(['down', 'enter'], default=False) is True
    assert choose_answer(['up', 'up', 'enter'], default=True) is True
    assert choose_answer(['tab', 'enter'], default=True) is False
    assert shown == [True, False, False]


@pytest.mark.parametrize('key, answer', [('y', True), ('Y', True), ('n', False), ('N', False)])
def test_y_and_n_answer_at_once(key, answer):
    assert choose_answer([key, 'enter'], default=not answer) is answer


def test_cyrillic_and_other_keys_change_nothing():
    for key in ('д', 'Д', 'т', 'н', 'Н', 'x', 'esc', ' '):
        assert answer_key(key, True) == (True, False)
        assert answer_key(key, False) == (False, False)


def test_ended_input_means_no():
    assert choose_answer([], default=True) is False


@pytest.mark.parametrize('line, answer', [('', True), ('  ', True), ('y', True), ('Yes', True), ('n', False),
                                          ('no', False), ('да', None), ('нет', None), ('н', None),
                                          ('maybe', None)])
def test_typed_answers(line, answer):
    assert answer_text(line, default=True) is answer


class Pipe:
    """Поток без терминала."""

    def isatty(self):
        return False


def test_without_a_terminal_the_answer_is_typed_and_repeated_until_clear(monkeypatch):
    from quietline_install.runner import Ctx

    ctx = Ctx(system=None, home=None, repo=None, ask=None, language='ru')
    replies = iter(['да', 'y'])
    prompts = []
    monkeypatch.setattr('builtins.input', lambda prompt: prompts.append(prompt) or next(replies))
    assert screens.ask_yes_no(ctx, 'Продолжить?', default=False, stdin=Pipe(), stdout=Pipe()) is True
    assert prompts == ['Продолжить? [y/N] '] * 2

    def closed(prompt):
        raise EOFError

    monkeypatch.setattr('builtins.input', closed)
    assert screens.ask_yes_no(ctx, 'Продолжить?', default=True, stdin=Pipe(), stdout=Pipe()) is False
