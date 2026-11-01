"""Экран входа, оболочка fish, группа docker, ручные шаги, проверка готовности и порядок шагов."""

import pytest

from quietline_install.catalog import Plan
from quietline_install.runner import StepFailed
from quietline_install.steps import build_steps, checks, session


@pytest.fixture
def root(ctx, tmp_path):
    ctx.root = tmp_path / 'root'
    (ctx.root / 'etc/greetd').mkdir(parents=True)
    return ctx.root


def test_greetd_config_launches_wayland_sessions(ctx, system, root):
    template = session.GREETD_TEMPLATE.read_text()
    assert 'tuigreet --time --remember --remember-session --sessions /usr/share/wayland-sessions' in template
    assert 'user = "greeter"' in template
    (root / 'etc/greetd/config.toml').write_text('[default_session]\ncommand = "agreety --cmd /bin/sh"\n')
    session.greetd_step().run(ctx)
    copy = next(call for call in system.calls if call['args'][:2] == ['cp', '-a'])
    assert copy['sudo'] and copy['args'][2] == '/etc/greetd/config.toml'
    assert copy['args'][3].startswith('/etc/greetd/config.toml.quietline-')
    tee = next(call for call in system.calls if call['args'][:1] == ['tee'])
    assert tee['sudo'] and tee['input'] == template
    assert {'kind': 'file', 'path': '/etc/greetd/config.toml', 'backup': copy['args'][3]} in ctx.state.changes


def test_greetd_is_enabled_not_started(ctx, system, root):
    system.answer(['systemctl', 'is-enabled', '--quiet', 'greetd.service'], code=1)
    session.greetd_step().run(ctx)
    enable = system.calls[-1]
    assert enable['args'] == ['systemctl', 'enable', 'greetd.service'] and enable['sudo']
    assert {'kind': 'service', 'unit': 'greetd.service'} in ctx.state.changes


def test_user_greetd_config_with_tuigreet_is_kept(ctx, system, root):
    mine = '[default_session]\ncommand = "tuigreet --cmd Hyprland --asterisks"\nuser = "greeter"\n'
    (root / 'etc/greetd/config.toml').write_text(mine)
    step = session.greetd_step()
    assert step.check(ctx) is True
    step.run(ctx)
    assert not any(call['args'][:1] in (['tee'], ['cp']) for call in system.calls)


def test_manual_steps_wait_for_confirmation_and_verify(ctx, system):
    step = session.docker_desktop_step()
    assert step.manual
    system.answer(['pacman', '-Q', 'docker-desktop'], code=1)
    ctx.answers.append(False)
    with pytest.raises(StepFailed) as failure:
        step.run(ctx)
    shown = '\n'.join(ctx.lines)
    assert 'https://docs.docker.com/desktop/setup/install/linux/archlinux/' in shown
    assert 'sudo pacman -U ./docker-desktop-x86_64.pkg.tar.zst' in shown and 'desktop-linux' in shown
    assert failure.value.action
    ctx.answers.append(True)
    with pytest.raises(StepFailed, match='Docker Desktop'):
        step.run(ctx)
    system.answer(['pacman', '-Q', 'docker-desktop'], 'docker-desktop 4.97.0-1\n')
    assert step.check(ctx) is True


@pytest.mark.parametrize('installed_answer', [False, True])
def test_manual_step_can_be_skipped(ctx, system, installed_answer):
    system.answer(['pacman', '-Q', 'docker-desktop'], code=1)
    step = session.docker_desktop_step()
    ctx.answers.extend([installed_answer, True])
    step.run(ctx)
    assert ctx.state.skipped == ['docker-desktop']
    assert step.check(ctx) is True
    assert any('./install.sh --from docker-desktop' in line for line in ctx.questions)


def test_amneziavpn_is_a_guided_manual_step(ctx, root, monkeypatch):
    monkeypatch.setattr(session.shutil, 'which', lambda name: None)
    step = session.amneziavpn_step()
    assert step.manual and step.check(ctx) is False
    ctx.answers.append(False)
    with pytest.raises(StepFailed):
        step.run(ctx)
    shown = '\n'.join(ctx.lines)
    assert 'https://github.com/amnezia-vpn/amnezia-client/releases' in shown
    assert 'https://amnezia.org/en/downloads' in shown
    (root / 'opt/AmneziaVPN').mkdir(parents=True)
    assert step.check(ctx) is True


def test_docker_group_asks_and_explains_root_equivalence(ctx, system, monkeypatch):
    monkeypatch.setattr(session.getpass, 'getuser', lambda: 'kiryl')
    system.answer(['getent', 'group', 'docker'], 'docker:x:968:\n')
    system.answer(['docker', 'context', 'show'], 'default\n')
    step = session.docker_group_step()
    assert step.check(ctx) is False
    ctx.answers.append(True)
    step.run(ctx)
    assert any(ctx.t('session.dockerRoot') in line for line in ctx.lines)
    usermod = next(call for call in system.calls if call['args'][:2] == ['usermod', '-aG'])
    assert usermod['sudo'] and usermod['args'] == ['usermod', '-aG', 'docker', 'kiryl']
    assert any(ctx.t('session.dockerContext', context='default') in line for line in ctx.lines)


def test_declined_optional_step_is_not_asked_again(ctx, system):
    system.answer(['getent', 'group', 'docker'], 'docker:x:968:\n')
    step = session.docker_group_step()
    ctx.answers.append(False)
    step.run(ctx)
    assert step.check(ctx) is True
    assert not any(call['args'][:2] == ['usermod', '-aG'] for call in system.calls)


def test_default_shell_changes_only_with_consent(ctx, system):
    system.answer(['getent', 'passwd'], 'kiryl:x:1000:1000::/home/kiryl:/bin/bash\n')
    step = session.default_shell_step()
    assert step.check(ctx) is False
    ctx.answers.append(False)
    step.run(ctx)
    assert not any(call['args'][:1] == ['chsh'] for call in system.calls)
    assert step.check(ctx) is True
    session._marker(ctx, 'default-shell').unlink()
    ctx.answers.append(True)
    step.run(ctx)
    chsh = system.calls[-1]
    assert chsh['args'] == ['chsh', '-s', '/usr/bin/fish'] and chsh['interactive']


def ready_system(ctx, system, root):
    hypr = ctx.home / '.config/hypr/hyprland.lua'
    hypr.parent.mkdir(parents=True)
    hypr.write_text('dofile("/usr/share/quietline/hyprland/quietline.lua")\n')
    lock = ctx.home / '.config/quickshell/quietline/LockScreen.qml'
    lock.parent.mkdir(parents=True)
    lock.write_text('')
    region = ctx.home / '.config/quietline/region.json'
    region.parent.mkdir(parents=True)
    region.write_text('{}')
    system.answer(['locale', '-a'], 'C\nen_US.utf8\nru_RU.utf8\n')


def test_check_reports_each_item_and_fails_on_missing(ctx, system, root):
    ready_system(ctx, system, root)
    plan = Plan(repo=['fish', 'firefox'], flatpak=['com.brave.Browser'], services=['docker.socket'])
    lines, ok = checks.run_checks(ctx, plan, which=lambda name: f'/usr/bin/{name}')
    assert ok, lines
    assert any('firefox' in line for line in lines) and any('com.brave.Browser' in line for line in lines)

    system.answer(['pacman', '-Q', 'firefox'], code=1)
    system.answer(['flatpak', 'info', '--user', 'com.brave.Browser'], code=1)
    lines, ok = checks.run_checks(ctx, plan, which=lambda name: None if name == 'ghostty' else f'/usr/bin/{name}')
    assert not ok
    missing = ctx.t('ready.missing')
    for name in ('firefox', 'com.brave.Browser', 'ghostty'):
        assert any(name in line and missing in line for line in lines), name


def test_check_needs_both_locales_and_lock_screen(ctx, system, root):
    ready_system(ctx, system, root)
    system.answer(['locale', '-a'], 'C\nen_US.utf8\n')
    (ctx.home / '.config/quickshell/quietline/LockScreen.qml').unlink()
    lines, ok = checks.run_checks(ctx, Plan(), which=lambda name: f'/usr/bin/{name}')
    assert not ok
    missing = ctx.t('ready.missing')
    assert any('ru_RU' in line and missing in line for line in lines)
    assert any('LockScreen.qml' in line and missing in line for line in lines)


FULL = Plan(repo=['fish', 'docker'], flatpak=['com.brave.Browser'], aur=['google-chrome', '1password'],
            manual=['docker-desktop', 'amneziavpn'], fnm=['lts-latest'], uv=['3.12'],
            services=['NetworkManager.service', 'docker.socket'], pins=['org.kde.dolphin'])


def test_login_session_comes_before_aur_and_manual_steps_last():
    ids = [step.id for step in build_steps(FULL)]
    assert ids == ['system-upgrade', 'repo-packages', 'graphics', 'locales', 'quietline-package', 'services',
                   'hyprland-config', 'fish', 'micro', 'quickshell-link', 'user-dirs', 'region', 'pins', 'greetd',
                   'flatpak', 'fnm', 'uv', 'aur-google-chrome', 'aur-1password', 'default-shell', 'hyprbars', 'docker-group',
                   'docker-desktop', 'amneziavpn']
    steps = {step.id: step for step in build_steps(FULL)}
    assert all(steps[name].manual for name in ('docker-desktop', 'amneziavpn'))


def test_unselected_programs_have_no_steps():
    ids = [step.id for step in build_steps(Plan(repo=['fish'], services=['NetworkManager.service']))]
    for absent in ('flatpak', 'fnm', 'uv', 'docker-group', 'docker-desktop', 'amneziavpn'):
        assert absent not in ids
    assert not any(name.startswith('aur-') for name in ids)
    assert 'greetd' in ids and 'default-shell' in ids and 'hyprbars' in ids


LISTING_ENABLED = """→ Repository hyprland-plugins (by quietline-desktop):
  │ Plugin hyprbars
  └─ enabled: true
"""
LISTING_DISABLED = """→ Repository hyprland-plugins (by quietline-desktop):
  │ Plugin hyprbars
  └─ enabled: false
"""
LISTING_OFFICIAL = """→ Repository hyprland-plugins (by hyprwm):
  │ Plugin hyprbars
  └─ enabled: true
"""


def test_hyprbars_enabled_reads_hyprpm_list():
    # Вывод hyprpm 0.57 с цветами: hyprbars выключен, соседний плагин включён.
    colored = ("\x1b[0m→\x1b[0m Repository hyprland-plugins (by hyprwm):\n  │ Plugin hyprbars\n"
               "  └─ enabled: \x1b[31mfalse\n\x1b[0m\n  │ Plugin hyprfocus\n  └─ enabled: \x1b[32mtrue\n\x1b[0m\n")
    assert not session.hyprbars_enabled(colored)
    assert session.hyprbars_enabled(colored.replace("\x1b[31mfalse", "\x1b[32mtrue", 1))
    assert session.hyprbars_enabled(LISTING_ENABLED)
    assert not session.hyprbars_enabled(LISTING_DISABLED)
    assert not session.hyprbars_enabled('')
    assert session.plugins_author(colored) == 'hyprwm'
    assert session.plugins_author(LISTING_ENABLED) == 'quietline-desktop'
    assert session.plugins_author('') is None


def test_hyprbars_step_adds_repository_once_and_enables_plugin(ctx, system):
    step = session.hyprbars_step()
    assert not step.check(ctx)
    step.run(ctx)
    assert system.commands() == [['hyprpm', 'list'], ['hyprpm', 'update'], ['hyprpm', 'list'],
                                 ['hyprpm', 'add', session.HYPRLAND_PLUGINS], ['hyprpm', 'enable', 'hyprbars']]
    assert all(call['interactive'] for call in system.calls if call['args'][1] != 'list')
    system.calls.clear()
    system.answer(['hyprpm', 'list'], LISTING_DISABLED)
    step.run(ctx)
    assert ['hyprpm', 'add', session.HYPRLAND_PLUGINS] not in system.commands()
    system.answer(['hyprpm', 'list'], LISTING_ENABLED)
    assert step.check(ctx)


def test_hyprbars_step_replaces_official_repository_with_fork(ctx, system):
    step = session.hyprbars_step()
    system.answer(['hyprpm', 'list'], LISTING_OFFICIAL)
    # Включённый hyprbars из официального репозитория — шаг не выполнен.
    assert not step.check(ctx)
    system.calls.clear()
    step.run(ctx)
    assert system.commands() == [['hyprpm', 'update'], ['hyprpm', 'list'], ['hyprpm', 'remove', 'hyprland-plugins'],
                                 ['hyprpm', 'add', session.HYPRLAND_PLUGINS], ['hyprpm', 'enable', 'hyprbars']]
    assert all(call['interactive'] for call in system.calls if call['args'][1] != 'list')
