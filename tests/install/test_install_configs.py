"""Файлы пользователя: конфигурация Hyprland, fish, micro, ссылка оболочки, папки, язык, закрепления."""

import json
from pathlib import Path

from quietline_install.steps import configs

REPO = Path(__file__).resolve().parents[2]
DOFILE = 'dofile("/usr/share/quietline/hyprland/quietline.lua")'
HYPR_EXAMPLE = '''# Hyprland example
bind = SUPER, M, exit,
bind = SUPER, Q, exec, kitty
'''


def config(ctx, relative):
    return ctx.home / '.config' / relative


def test_new_config_is_created_without_backup(ctx, tmp_path):
    source = tmp_path / 'source'
    source.write_text('new\n')
    target = ctx.home / 'a/b.conf'
    assert configs.install_file(ctx, source, target) == 'created'
    assert target.read_text() == 'new\n'
    assert list(target.parent.glob('b.conf.quietline-*')) == []
    assert ctx.state.changes == [{'kind': 'file', 'path': str(target), 'backup': None}]
    assert configs.install_file(ctx, source, target) == 'unchanged'
    assert len(ctx.state.changes) == 1


def test_existing_user_config_is_backed_up_once(ctx, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.write_text('quietline\n')
    target = ctx.home / 'app.conf'
    target.write_text('mine\n')
    stamps = iter(['20261028-120000', '20261028-120001'])
    monkeypatch.setattr(configs, '_stamp', lambda: next(stamps))
    result = configs.install_file(ctx, source, target)
    backup = ctx.home / 'app.conf.quietline-20261028-120000'
    assert result == f'updated, backup {backup}'
    assert backup.read_text() == 'mine\n' and target.read_text() == 'quietline\n'
    # пользователь вернул своё содержимое — повтор не плодит одинаковую копию
    target.write_text('mine\n')
    configs.install_file(ctx, source, target)
    assert sorted(path.name for path in ctx.home.glob('app.conf.quietline-*')) == ['app.conf.quietline-20261028-120000']
    assert ctx.state.changes[0] == {'kind': 'file', 'path': str(target), 'backup': str(backup)}


def test_example_hyprland_config_is_replaced_with_backup(ctx):
    target = config(ctx, 'hypr/hyprland.lua')
    target.parent.mkdir(parents=True)
    target.write_text(HYPR_EXAMPLE)
    step = configs.hyprland_step()
    assert step.check(ctx) is False
    step.run(ctx)
    assert DOFILE in target.read_text()
    assert 'SUPER, M, exit' not in target.read_text()
    backups = list(target.parent.glob('hyprland.lua.quietline-*'))
    assert len(backups) == 1 and backups[0].read_text() == HYPR_EXAMPLE
    assert step.check(ctx) is True


def test_hyprland_config_with_quietline_line_is_untouched(ctx):
    target = config(ctx, 'hypr/hyprland.lua')
    target.parent.mkdir(parents=True)
    mine = f'-- мои мониторы\n{DOFILE}\nhl.config({{ monitor = "eDP-1,preferred,auto,1.25" }})\n'
    target.write_text(mine)
    step = configs.hyprland_step()
    assert step.check(ctx) is True
    assert target.read_text() == mine


def test_hyprland_template_includes_quietline():
    assert DOFILE in (REPO / 'installer/files/hyprland.lua').read_text()


def test_lua_header_names_the_dofile_line():
    header = (REPO / 'config/hyprland/quietline.lua').read_text().splitlines()[1]
    assert DOFILE in header and 'require' not in header


def prepare_locale_source(ctx, tmp_path):
    ctx.root = tmp_path / 'root'
    source = ctx.root / 'usr/share/quietline/fish/quietline-locale.fish'
    source.parent.mkdir(parents=True)
    source.write_text((REPO / 'config/fish/quietline-locale.fish').read_text())


def test_fish_snippets_include_locale_and_fnm_only_when_node_selected(ctx, tmp_path):
    prepare_locale_source(ctx, tmp_path)
    configs.fish_step(with_fnm=False).run(ctx)
    main = config(ctx, 'fish/conf.d/quietline.fish').read_text()
    assert 'micro' in main and 'starship init fish | source' in main and 'fnm' not in main
    locale = config(ctx, 'fish/conf.d/quietline-locale.fish').read_text()
    assert locale == (REPO / 'config/fish/quietline-locale.fish').read_text()
    assert configs.fish_step(with_fnm=False).check(ctx) is True

    step = configs.fish_step(with_fnm=True)
    assert step.check(ctx) is False
    step.run(ctx)
    assert 'fnm env --use-on-cd --shell fish | source' in config(ctx, 'fish/conf.d/quietline.fish').read_text()


def test_micro_settings_are_merged_not_replaced(ctx):
    target = config(ctx, 'micro/settings.json')
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({'tabsize': 2, 'mouse': False}))
    step = configs.micro_step()
    assert step.check(ctx) is False
    step.run(ctx)
    assert json.loads(target.read_text()) == {'tabsize': 2, 'mouse': True, 'clipboard': 'external'}
    assert len(list(target.parent.glob('settings.json.quietline-*'))) == 1
    assert step.check(ctx) is True


def test_quickshell_link_points_to_package_shell(ctx):
    target = config(ctx, 'quickshell/quietline')
    target.mkdir(parents=True)
    (target / 'shell.qml').write_text('old')
    step = configs.quickshell_link_step()
    assert step.check(ctx) is False
    step.run(ctx)
    assert target.is_symlink() and target.readlink() == Path('/usr/share/quietline/shell')
    kept = list(target.parent.glob('quietline.quietline-*'))
    assert len(kept) == 1 and (kept[0] / 'shell.qml').read_text() == 'old'
    assert ctx.state.changes == [{'kind': 'file', 'path': str(target), 'backup': str(kept[0])}]
    assert step.check(ctx) is True


def test_fresh_user_dirs_are_english_and_rename_is_disabled(ctx):
    step = configs.user_dirs_step()
    assert step.check(ctx) is False
    step.run(ctx)
    dirs = config(ctx, 'user-dirs.dirs').read_text()
    for name in ('DESKTOP', 'DOWNLOAD', 'DOCUMENTS', 'MUSIC', 'PICTURES', 'PUBLICSHARE', 'TEMPLATES', 'VIDEOS'):
        assert f'XDG_{name}_DIR=' in dirs
    assert '"$HOME/Downloads"' in dirs and 'Загрузки' not in dirs
    for folder in ('Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 'Public', 'Templates', 'Videos'):
        assert (ctx.home / folder).is_dir()
    assert 'enabled=False' in config(ctx, 'user-dirs.conf').read_text()
    assert step.check(ctx) is True


def test_existing_user_dirs_are_left_as_is(ctx):
    target = config(ctx, 'user-dirs.dirs')
    target.parent.mkdir(parents=True)
    russian = 'XDG_DOWNLOAD_DIR="$HOME/Загрузки"\n'
    target.write_text(russian)
    (ctx.home / 'Загрузки').mkdir()
    configs.user_dirs_step().run(ctx)
    assert target.read_text() == russian
    assert not (ctx.home / 'Downloads').exists()
    assert any('Загрузки' in line for line in ctx.lines)
    assert 'enabled=False' in config(ctx, 'user-dirs.conf').read_text()


def test_region_is_set_through_quietline_shell(ctx, system):
    ctx.state.system_language = 'ru'
    step = configs.region_step()
    assert step.check(ctx) is False
    step.run(ctx)
    call = system.calls[-1]
    assert call['args'][:3] == ['quietline-shell', 'region', '--set'] and not call['sudo']
    assert json.loads(call['args'][3]) == {'language': 'ru', 'clock': '24h', 'date': 'dmy'}
    kinds = {change['path'] for change in ctx.state.changes}
    assert str(config(ctx, 'locale.conf')) in kinds and str(config(ctx, 'quietline/region.json')) in kinds

    region = config(ctx, 'quietline/region.json')
    region.parent.mkdir(parents=True, exist_ok=True)
    region.write_text(json.dumps({'version': 1, 'language': 'ru', 'clock': '12h', 'date': 'ymd',
                                  'layouts': ['us', 'ru'], 'toggle': 'grp:lalt_lshift_toggle'}))
    assert step.check(ctx) is True
    ctx.state.system_language = 'en'
    assert step.check(ctx) is False
    step.run(ctx)
    assert json.loads(system.calls[-1]['args'][3]) == {'language': 'en'}


def test_english_region_defaults(ctx, system):
    ctx.state.system_language = 'en'
    configs.region_step().run(ctx)
    assert json.loads(system.calls[-1]['args'][3]) == {'language': 'en', 'clock': '12h', 'date': 'mdy'}


def test_pins_are_written_once_through_quietline_shell(ctx, system):
    step = configs.pins_step(['org.kde.dolphin', 'firefox', 'com.mitchellh.ghostty'])
    assert step.check(ctx) is False
    step.run(ctx)
    call = system.calls[-1]
    assert call['args'][:3] == ['quietline-shell', 'pins', '--set']
    assert json.loads(call['args'][3]) == ['org.kde.dolphin', 'firefox', 'com.mitchellh.ghostty']
    assert ctx.state.changes == [{'kind': 'file', 'path': str(config(ctx, 'quietline/pins.json')), 'backup': None}]


def test_existing_pins_are_not_overwritten(ctx, system):
    pins = config(ctx, 'quietline/pins.json')
    pins.parent.mkdir(parents=True)
    pins.write_text('{"version": 1, "pinned": ["code"]}')
    assert configs.pins_step(['firefox']).check(ctx) is True
    assert system.calls == []
