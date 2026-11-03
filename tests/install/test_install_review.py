"""Замечания итогового ревью: снимок обязателен, откат не ломает вход, безопасные Ctrl+C и откат."""

import signal
import subprocess
from pathlib import Path

import pytest

import quietline_install.__main__ as main_module
from quietline_install import runner as runner_module
from quietline_install import snapshot
from quietline_install.catalog import load_catalog
from quietline_install.runner import Runner, State, Step, StepFailed, System
from quietline_install.snapshot import RootInfo
from quietline_install.steps import aur, packages, session

REPO = Path(__file__).resolve().parents[2]
BTRFS_RW = RootInfo(fstype='btrfs', device='/dev/nvme0n1p8', subvol='/@', boot_inside=True, systemd_hook=True,
                    overlay=False, swapfile_in_root=False)
OVERLAY = RootInfo(fstype='overlay', device='/dev/nvme0n1p8', subvol=None, boot_inside=True, systemd_hook=False,
                   overlay=True, swapfile_in_root=False)


def btrfs_top(system):
    system.answer(['mktemp', '-d'], '/run/quietline-top.abc123\n')
    system.answer(['ls', '-A', '/run/quietline-top.abc123'], '@\n@home\n@snapshots\n')
    system.answer(['ls', '-A', '/run/quietline-top.abc123/@snapshots'], '')


# Критическое 1: снимок не теряется молча

def test_failed_grub_btrfs_install_is_a_step_failure(ctx, system, monkeypatch):
    monkeypatch.setattr(snapshot, 'inspect_root', lambda ctx: BTRFS_RW)
    system.answer(['pacman', '-Q', 'grub-btrfs'], code=1)
    system.answer(['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'], code=1)
    with pytest.raises(StepFailed, match='grub-btrfs'):
        snapshot.prepare(ctx)


def test_failed_snapshot_command_is_a_step_failure(ctx, system, monkeypatch):
    monkeypatch.setattr(snapshot, 'inspect_root', lambda ctx: BTRFS_RW)
    btrfs_top(system)
    system.answer(['btrfs', 'subvolume', 'snapshot'], code=1)
    with pytest.raises(StepFailed, match='snapshot'):
        snapshot.take(ctx, 'btrfs-rw')
    assert ctx.state.snapshot is None
    assert ['umount', '/run/quietline-top.abc123'] in system.commands()


# Важное 3: снимок для записи тоже попадает в меню GRUB

def test_writable_snapshot_still_installs_grub_btrfs(ctx, system, monkeypatch):
    monkeypatch.setattr(snapshot, 'inspect_root', lambda ctx: BTRFS_RW)
    system.answer(['pacman', '-Q', 'grub-btrfs'], code=1)
    snapshot.prepare(ctx)
    assert ['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'] in system.commands()
    assert not any(command[:1] == ['mkinitcpio'] for command in system.commands())
    assert ctx.state.changes == [{'kind': 'package', 'name': 'grub-btrfs'}]


# Критическое 2: откат без Btrfs возвращает оболочку входа до удаления fish

def test_journal_rollback_restores_login_shell_before_removing_packages(ctx, system, monkeypatch):
    monkeypatch.setattr(session.getpass, 'getuser', lambda: 'kiryl')
    system.answer(['getent', 'passwd'], 'kiryl:x:1000:1000::/home/kiryl:/bin/bash\n')
    ctx.record({'kind': 'package', 'name': 'fish'})
    ctx.answers.append(True)
    session.default_shell_step().run(ctx)
    assert {'kind': 'shell', 'previous': '/bin/bash'} in ctx.state.changes
    system.calls.clear()
    system.answer(['pacman', '-Qq'], 'fish\n')
    snapshot.rollback_journal(ctx)
    commands = system.commands()
    chsh = commands.index(['chsh', '-s', '/bin/bash'])
    removal = next(i for i, command in enumerate(commands) if command[:2] == ['pacman', '-Rns'])
    assert chsh < removal


# Важное 4: из загруженного снимка установка не начинается

def test_booted_snapshot_blocks_installation(ctx, system):
    results = main_module.preflight(ctx, OVERLAY)
    blocking = [result for result in results if not result.ok and result.blocking]
    assert any(result.id == 'booted-snapshot' for result in blocking)
    assert ctx.t('check.booted-snapshot')


# Важное 6: base-devel — часть основы

def test_base_devel_is_core():
    catalog = load_catalog(REPO / 'installer/catalog.toml')
    assert 'base-devel' in catalog.core_packages


# Важное 7: NVIDIA и гибридная графика

def test_nvidia_passes_once_driver_installed_and_hybrids_get_intel_packages(ctx, system, monkeypatch):
    monkeypatch.setattr(packages, 'gpu_vendors', lambda ctx: {'nvidia', 'intel'})
    system.answer(['pacman', '-Q', 'nvidia-utils'], code=1)
    step = packages.graphics_step()
    assert step.check(ctx) is False
    with pytest.raises(StepFailed, match='NVIDIA'):
        step.run(ctx)
    system.answer(['pacman', '-Q', 'nvidia-utils'], 'nvidia-utils 580-1\n')
    system.answer(['pacman', '-Qq'], '')
    step.run(ctx)
    assert system.calls[-1]['args'] == ['pacman', '-S', '--needed', 'mesa', 'vulkan-intel', 'intel-media-driver']
    assert step.check(ctx) is True


def test_gpu_vendors_reads_all_cards(ctx, system, tmp_path):
    for index, vendor in enumerate(['0x8086', '0x10de']):
        card = tmp_path / f'drm/card{index}/device'
        card.mkdir(parents=True)
        (card / 'vendor').write_text(vendor + '\n')
    system.answer(['systemd-detect-virt'], 'none\n', code=1)
    assert packages.gpu_vendors(ctx, tmp_path / 'drm') == {'intel', 'nvidia'}
    system.answer(['systemd-detect-virt'], 'kvm\n')
    assert packages.gpu_vendors(ctx, tmp_path / 'drm') == {'virtual'}


# Важное 8: Ctrl+C не убивает pacman посреди транзакции

def test_interactive_command_ignores_ctrl_c_in_the_installer(monkeypatch):
    seen = []

    def fake_run(command, **kwargs):
        seen.append(signal.getsignal(signal.SIGINT))
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(runner_module.subprocess, 'run', fake_run)
    before = signal.getsignal(signal.SIGINT)
    System().run(['pacman', '-Syu'], sudo=True, interactive=True)
    assert seen == [signal.SIG_IGN]
    assert signal.getsignal(signal.SIGINT) == before


def test_interrupted_interactive_command_stops_the_installer(monkeypatch):
    monkeypatch.setattr(runner_module.subprocess, 'run',
                        lambda command, **kwargs: subprocess.CompletedProcess(command, 130, '', ''))
    with pytest.raises(KeyboardInterrupt):
        System().run(['pacman', '-Syu'], interactive=True)


# Важное 9: ход установки на языке установщика, причина ошибки на экране продолжения

def test_progress_is_shown_in_the_installer_language(ctx, tmp_path):
    ctx.language = 'ru'
    step = Step('fish', 'step.fish', 'Quietline', lambda c: False, lambda c: None)
    done = {'value': False}
    step.check = lambda c: done['value']
    step.run = lambda c: done.update(value=True)
    Runner([step], ctx, tmp_path / 'install.log').run()
    assert '[1/1] ' + ctx.t('progress.done', step=f"{ctx.t('step.fish')} [Quietline]") in ctx.lines
    assert 'fish [Quietline]: done' in (tmp_path / 'install.log').read_text()


# Важное 10: длинные инструкции AUR показываются целиком, вопрос один

def test_long_aur_instructions_are_shown_whole(ctx, system):
    directory = ctx.home / '.cache/quietline/aur/google-chrome'
    directory.mkdir(parents=True)
    (directory / 'PKGBUILD').write_text(''.join(f'line {n}\n' for n in range(100)))
    ctx.answers.append(False)
    with pytest.raises(StepFailed):
        aur.aur_install(ctx, 'google-chrome')
    shown = [line for line in ctx.lines if line.startswith('line ')]
    assert len(shown) == 100 and len(ctx.questions) == 1


# Важное 11: откат подтверждается и не выполняется при --dry-run

def rollback_env(tmp_path, system, monkeypatch):
    home = tmp_path / 'home'
    done = []
    monkeypatch.setattr(main_module.snapshot, 'rollback_btrfs', lambda ctx, name: done.append(name) or '@broken-x')
    state = State(path=home / '.local/state/quietline/install.json', installer_language='en',
                  system_language='en', selection={'ids': [], 'previous': []}, finished=True,
                  snapshot={'kind': 'btrfs-ro', 'name': 'quietline-pre-20261028-120000'})
    state.save()
    return home, done


def test_rollback_refuses_dry_run(tmp_path, system, monkeypatch):
    home, done = rollback_env(tmp_path, system, monkeypatch)
    code = main_module.main(['rollback', '--dry-run'], system=system, home=home, ask=lambda q, default=False: True,
                            out=lambda line: None)
    assert code != 0 and done == []


def test_rollback_command_asks_for_confirmation(tmp_path, system, monkeypatch):
    home, done = rollback_env(tmp_path, system, monkeypatch)
    questions = []
    code = main_module.main(['rollback'], system=system, home=home,
                            ask=lambda q, default=False: questions.append(q) or False, out=lambda line: None)
    assert code != 0 and done == []
    assert any('quietline-pre-20261028-120000' in question for question in questions)
    assert main_module.main(['rollback'], system=system, home=home, ask=lambda q, default=False: True,
                            out=lambda line: None) == 0
    assert done == ['quietline-pre-20261028-120000']


def update_env(tmp_path, system, monkeypatch, installed):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(main_module, 'aur_outdated', lambda ctx, names: [])
    system.answer(['git', '-C'], '')
    system.answer(['git', '-C', str(main_module.REPO), 'rev-list', '--count', 'HEAD'], '200\n')
    system.answer(['git', '-C', str(main_module.REPO), 'rev-parse', '--short', 'HEAD'], 'abc1234\n')
    system.answer(['pacman', '-Q', 'quietline'], f'quietline {installed}-1\n')
    return home


def test_update_rebuilds_quietline_when_clone_is_newer(tmp_path, system, monkeypatch):
    home = update_env(tmp_path, system, monkeypatch, '0.1.0.r150.gdeadbee')
    lines = []
    assert main_module.main(['update'], system=system, home=home, out=lines.append) == 0
    makepkg = [call for call in system.calls if call['args'][0] == 'makepkg']
    assert makepkg and makepkg[0]['args'] == ['makepkg', '-si', '--cleanbuild'] and makepkg[0]['interactive']
    assert makepkg[0]['env'] == {'QUIETLINE_REPO': str(main_module.REPO)}
    assert system.commands()[-1] == ['hyprpm', 'update']
    assert any('rebuilding' in line for line in lines)


def test_update_skips_current_quietline(tmp_path, system, monkeypatch):
    version = main_module.REPO.joinpath('pyproject.toml').read_text().split('version = "')[1].split('"')[0]
    home = update_env(tmp_path, system, monkeypatch, f'{version}.r200.gabc1234')
    lines = []
    assert main_module.main(['update'], system=system, home=home, out=lines.append) == 0
    assert not any(call['args'][0] == 'makepkg' for call in system.calls)
    assert any('matches the current commit' in line for line in lines)


def test_failed_quietline_build_is_reported_and_update_continues(tmp_path, system, monkeypatch):
    home = update_env(tmp_path, system, monkeypatch, '0.1.0.r150.gdeadbee')
    system.answer(['makepkg'], code=4)
    lines = []
    assert main_module.main(['update'], system=system, home=home, out=lines.append) == 1
    assert any('was not rebuilt' in line for line in lines)
    assert system.commands()[-1] == ['hyprpm', 'update']
