"""Шаги пакетов: pacman, графика, локали, службы, Flatpak, версии разработки, пакет quietline."""

import re
from pathlib import Path

import pytest

from quietline_install.runner import StepFailed
from quietline_install.steps import packages

REPO = Path(__file__).resolve().parents[2]


def test_missing_package_stops_before_install(ctx, system):
    system.answer(['pacman', '-Q'], code=1)
    system.answer(['pacman', '-Si', 'quickshell'], code=1)
    with pytest.raises(StepFailed, match='quickshell'):
        packages.repo_step(['hyprland', 'quickshell']).run(ctx)
    assert not any(command[:2] == ['pacman', '-S'] for command in system.commands())
    assert ctx.state.changes == []


def test_installed_group_is_skipped(ctx, system):
    system.answer(['pacman', '-Q'], 'fish 4.1-1\nmicro 2.0-1\n')
    assert packages.repo_step(['fish', 'micro']).check(ctx) is True
    system.answer(['pacman', '-Q'], code=1)
    assert packages.repo_step(['fish', 'micro']).check(ctx) is False


def test_repo_packages_install_in_one_transaction_without_sync(ctx, system):
    system.answer(['pacman', '-Qq'], '')
    packages.repo_step(['fish', 'micro', 'git']).run(ctx)
    installs = [call for call in system.calls if call['args'][:2] == ['pacman', '-S']]
    assert len(installs) == 1
    assert installs[0]['args'] == ['pacman', '-S', '--needed', 'fish', 'micro', 'git']
    assert installs[0]['sudo'] and installs[0]['interactive']
    assert not any('-y' in arg or arg.startswith('-Sy') for command in system.commands() for arg in command)


def test_new_packages_are_journaled_but_preexisting_are_not(ctx, system):
    system.answer(['pacman', '-Qq'], 'git\nbase\n')
    packages.repo_step(['fish', 'git']).run(ctx)
    assert ctx.state.changes == [{'kind': 'package', 'name': 'fish'}]


def test_failed_pacman_transaction_is_a_step_failure(ctx, system):
    system.answer(['pacman', '-Qq'], '')
    system.answer(['pacman', '-S', '--needed'], code=1)
    with pytest.raises(StepFailed, match='pacman'):
        packages.repo_step(['fish']).run(ctx)
    assert ctx.state.changes == []


def test_full_upgrade_runs_once(ctx, system):
    step = packages.upgrade_step()
    assert step.id == 'system-upgrade'
    assert step.check(ctx) is False
    step.run(ctx)
    upgrade = system.calls[-1]
    assert upgrade['args'] == ['pacman', '-Syu'] and upgrade['sudo'] and upgrade['interactive']
    assert step.check(ctx) is True
    ctx.state.done['system-upgrade'] = '2026-10-28T12:00:00'
    assert packages.upgrade_step().check(ctx) is True


def test_failed_upgrade_is_not_done(ctx, system):
    system.answer(['pacman', '-Syu'], code=1)
    step = packages.upgrade_step()
    with pytest.raises(Exception):
        step.run(ctx)
    assert step.check(ctx) is False


@pytest.mark.parametrize('vendors, expected', [
    ({'intel'}, ['mesa', 'vulkan-intel', 'intel-media-driver']),
    ({'amd'}, ['mesa', 'vulkan-radeon']),
    ({'virtual'}, ['mesa']),
    ({'unknown'}, ['mesa']),
])
def test_gpu_packages_follow_detected_vendor(ctx, system, monkeypatch, vendors, expected):
    monkeypatch.setattr(packages, 'gpu_vendors', lambda ctx: vendors)
    system.answer(['pacman', '-Q'], code=1)
    system.answer(['pacman', '-Qq'], '')
    packages.graphics_step().run(ctx)
    assert system.calls[-1]['args'] == ['pacman', '-S', '--needed', *expected]


def test_nvidia_stops_with_instructions(ctx, system, monkeypatch):
    monkeypatch.setattr(packages, 'gpu_vendors', lambda ctx: {'nvidia'})
    system.answer(['pacman', '-Q', 'nvidia-utils'], code=1)
    with pytest.raises(StepFailed) as failure:
        packages.graphics_step().run(ctx)
    assert 'NVIDIA' in str(failure.value) and '--from graphics' in failure.value.action
    assert not any(command[:2] == ['pacman', '-S'] for command in system.commands())


LOCALE_GEN = """# Configuration file for locale-gen
#en_GB.UTF-8 UTF-8
#en_US.UTF-8 UTF-8
#en_US ISO-8859-1
#ru_RU.UTF-8 UTF-8
#ru_RU KOI8-R KOI8-R
"""


def write_locale_gen(ctx, text):
    path = ctx.root / 'etc/locale.gen'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_both_locales_are_enabled_once(ctx, system, tmp_path):
    ctx.root = tmp_path / 'root'
    write_locale_gen(ctx, LOCALE_GEN)
    step = packages.locales_step()
    assert step.check(ctx) is False
    step.run(ctx)
    tee = next(call for call in system.calls if call['args'][:1] == ['tee'])
    assert tee['sudo'] and tee['args'] == ['tee', '/etc/locale.gen.quietline-new']
    new = tee['input']
    assert re.search(r'^en_US\.UTF-8 UTF-8$', new, re.M) and re.search(r'^ru_RU\.UTF-8 UTF-8$', new, re.M)
    assert '#en_GB.UTF-8 UTF-8' in new and '#en_US ISO-8859-1' in new and '#ru_RU KOI8-R KOI8-R' in new
    copy = next(call for call in system.calls if call['args'][:2] == ['cp', '-a'])
    assert copy['sudo'] and copy['args'][2] == '/etc/locale.gen'
    assert copy['args'][3].startswith('/etc/locale.gen.quietline-')
    assert ctx.state.changes == [{'kind': 'file', 'path': '/etc/locale.gen', 'backup': copy['args'][3]}]
    assert system.calls[-1]['args'] == ['locale-gen'] and system.calls[-1]['sudo']

    write_locale_gen(ctx, new)
    assert step.check(ctx) is True


def test_missing_locale_lines_are_appended(ctx, system, tmp_path):
    ctx.root = tmp_path / 'root'
    write_locale_gen(ctx, '# empty\n')
    packages.locales_step().run(ctx)
    new = next(call for call in system.calls if call['args'][:1] == ['tee'])['input']
    assert new.endswith('en_US.UTF-8 UTF-8\nru_RU.UTF-8 UTF-8\n')


def test_services_are_enabled_and_journaled_one_by_one(ctx, system):
    system.answer(['systemctl', 'is-enabled', '--quiet', 'docker.socket'], code=1)
    step = packages.services_step(['NetworkManager.service', 'docker.socket'])
    assert step.check(ctx) is False
    step.run(ctx)
    enables = [call for call in system.calls if call['args'][:2] == ['systemctl', 'enable']]
    assert [call['args'] for call in enables] == [['systemctl', 'enable', '--now', 'docker.socket']]
    assert enables[0]['sudo']
    assert ctx.state.changes == [{'kind': 'service', 'unit': 'docker.socket'}]


def test_flatpak_apps_install_per_user(ctx, system):
    system.answer(['flatpak', 'info', '--user', 'org.onlyoffice.desktopeditors'], code=1)
    step = packages.flatpak_step(['com.brave.Browser', 'org.onlyoffice.desktopeditors'])
    assert step.check(ctx) is False
    step.run(ctx)
    commands = system.commands()
    assert ['flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub',
            'https://dl.flathub.org/repo/flathub.flatpakrepo'] in commands
    installs = [command for command in commands if command[:2] == ['flatpak', 'install']]
    assert installs == [['flatpak', 'install', '--user', '-y', 'flathub', 'org.onlyoffice.desktopeditors']]
    assert not any(call['sudo'] for call in system.calls)
    assert ctx.state.changes == [{'kind': 'flatpak', 'id': 'org.onlyoffice.desktopeditors'}]


def test_fnm_installs_versions_and_sets_default(ctx, system):
    step = packages.fnm_step(['lts-latest', '22'])
    system.answer(['fnm', 'list'], '* system\n')
    assert step.check(ctx) is False
    step.run(ctx)
    commands = [command for command in system.commands() if command[:2] != ['fnm', 'list']]
    assert commands == [['fnm', 'install', '--lts'], ['fnm', 'install', '22'], ['fnm', 'default', 'lts-latest']]
    assert not any(call['sudo'] for call in system.calls)
    system.answer(['fnm', 'list'], '* v22.23.4\n* v24.22.1 default, lts-latest\n* system\n')
    assert step.check(ctx) is True


def test_uv_installs_extra_python_versions(ctx, system):
    step = packages.uv_step(['3.12', '3.13'])
    system.answer(['uv', 'python', 'find', '3.13'], code=1)
    assert step.check(ctx) is False
    step.run(ctx)
    assert system.commands()[-1] == ['uv', 'python', 'install', '3.12', '3.13']


def test_package_is_rebuilt_for_new_commits(ctx, system, tmp_path):
    ctx.home.joinpath('.cache').mkdir()
    version = re.search(r'^version = "([^"]+)"', (REPO / 'pyproject.toml').read_text(), re.M).group(1)
    system.answer(['git', '-C', str(ctx.repo), 'rev-list', '--count', 'HEAD'], '42\n')
    system.answer(['git', '-C', str(ctx.repo), 'rev-parse', '--short', 'HEAD'], 'abc1234\n')
    system.answer(['pacman', '-Q', 'quietline'], f'quietline {version}.r41.g0000000-1\n')
    step = packages.quietline_package_step()
    assert step.check(ctx) is False
    system.answer(['pacman', '-Q', 'quietline'], f'quietline {version}.r42.gabc1234-1\n')
    assert step.check(ctx) is True


def test_package_builds_outside_the_checkout(ctx, system):
    system.answer(['pacman', '-Q', 'quietline'], code=1)
    packages.quietline_package_step().run(ctx)
    build = ctx.home / '.cache/quietline/build'
    assert (build / 'PKGBUILD').read_text() == (REPO / 'packaging/arch/PKGBUILD').read_text()
    makepkg = system.calls[-1]
    assert makepkg['args'] == ['makepkg', '-si', '--cleanbuild'] and makepkg['interactive']
    assert makepkg['cwd'] == build and makepkg['env'] == {'QUIETLINE_REPO': str(ctx.repo)}
    assert not makepkg['sudo']
    assert ctx.state.changes == [{'kind': 'package', 'name': 'quietline'}]


def test_pkgbuild_installs_expected_paths():
    text = (REPO / 'packaging/arch/PKGBUILD').read_text()
    assert "license=('GPL-3.0-only')" in text
    assert re.search(r"makedepends=\([^)]*'python-hatchling'", text)
    assert 'python-setuptools' not in text
    depends = re.search(r'^depends=\(([^)]*)\)', text, re.M | re.S).group(1)
    for package in ('python', 'hyprland', 'quickshell', 'networkmanager', 'brightnessctl', 'power-profiles-daemon',
                    'bluez', 'pipewire', 'wireplumber', 'glib2', 'libnotify', 'wl-clipboard', 'cliphist', 'grim',
                    'slurp', 'satty', 'plocate', 'polkit', 'capitaine-cursors'):
        assert f"'{package}'" in depends, package
    for target in ('/usr/share/quietline/shell', '/usr/share/quietline/hyprland/quietline.lua',
                   '/usr/share/quietline/fish/quietline-locale.fish',
                   '/usr/share/polkit-1/rules.d/50-quietline-network.rules', '/usr/share/licenses/$pkgname/LICENSE',
                   '/usr/share/quietline/ghostty/quietline-light'):
        assert target in text, target
    assert 'git -C "$_repo" archive HEAD' in text
    for source in ('config/hyprland/quietline.lua', 'config/fish/quietline-locale.fish',
                   'config/polkit/50-quietline-network.rules', 'config/ghostty/quietline-light', 'shell/quietline/.'):
        assert source in text and (REPO / source.rstrip('/.')).exists(), source
