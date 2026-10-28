import re
import subprocess
from pathlib import Path

import pytest

from quietline_install import snapshot
from quietline_install.runner import State, StepFailed
from quietline_install.texts import TEXTS

TOP = '/run/quietline-top.abc123'
SOURCE = '/dev/nvme0n1p5'
HOOKS = 'base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck'
SWAPS_HEADER = 'Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n'
FSTAB = ('# /dev/nvme0n1p5\n'
         'UUID=x / btrfs rw,noatime,subvolid=256,subvol=/@ 0 0\n'
         '\n'
         'UUID=x /home btrfs rw,noatime,subvolid=257,subvol=/@home 0 0\n'
         'UUID=e /efi vfat rw,relatime 0 2\n')
NAME = 'quietline-pre-20261028-101500'


def make_root(ctx, system, tmp_path, fstype='btrfs', subvol='/@', boot='', hooks=HOOKS, swaps='',
              cmdline='BOOT_IMAGE=/@/boot/vmlinuz-linux root=UUID=abcd rw rootflags=subvol=@\n'):
    """Корень системы: ответы findmnt и файлы /etc, /proc во временном ctx.root."""
    ctx.root = tmp_path / 'root'
    (ctx.root / 'etc').mkdir(parents=True, exist_ok=True)
    (ctx.root / 'proc').mkdir(exist_ok=True)
    (ctx.root / 'usr/lib/initcpio/install').mkdir(parents=True, exist_ok=True)
    (ctx.root / 'usr/lib/initcpio/install/grub-btrfs-overlayfs').write_text('')
    if hooks is not None:
        (ctx.root / 'etc/mkinitcpio.conf').write_text(
            '# vim:set ft=sh\nMODULES=()\n#    HOOKS=(base systemd)\nHOOKS=(' + hooks + ')\nCOMPRESSION="zstd"\n')
    (ctx.root / 'proc/swaps').write_text(SWAPS_HEADER + swaps)
    (ctx.root / 'proc/cmdline').write_text(cmdline)
    if fstype == 'btrfs':
        line = f'btrfs {SOURCE}[{subvol}] rw,noatime,compress=zstd:3,ssd,subvolid=256,subvol={subvol}\n'
    elif fstype == 'overlay':
        line = 'overlay overlay rw,relatime,lowerdir=/run/rootfsbase,upperdir=/run/cow/upper\n'
    else:
        line = f'{fstype} /dev/sda2 rw,relatime\n'
    system.answer(['findmnt', '-no', 'FSTYPE,SOURCE,OPTIONS', '/'], line)
    system.answer(['findmnt', '-no', 'SOURCE', '/boot'], boot, 1 if not boot else 0)
    system.answer(['findmnt', '-no', 'SOURCE', '-T'], line.split()[1] + '\n')
    system.answer(['mktemp'], TOP + '\n')
    system.answer(['ls', '-A', TOP], '@\n@home\n@log\n@pkg\n@snapshots\n')


def index(commands, prefix):
    """Номер первой команды с этим началом; нет — AssertionError."""
    for number, args in enumerate(commands):
        if args[:len(prefix)] == prefix:
            return number
    raise AssertionError(f'{prefix} not in {commands}')


@pytest.mark.parametrize(('layout', 'kind', 'reason'), [
    ({}, 'btrfs-ro', 'snapshot.reason.ready'),
    ({'hooks': 'base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck'},
     'btrfs-rw', 'snapshot.reason.systemdHook'),
    ({'hooks': None}, 'btrfs-rw', 'snapshot.reason.hooksElsewhere'),
    ({'fstype': 'ext4'}, 'none', 'snapshot.reason.notBtrfs'),
    ({'boot': '/dev/nvme0n1p6\n'}, 'none', 'snapshot.reason.bootSeparate'),
    ({'subvol': '/'}, 'none', 'snapshot.reason.subvol'),
    ({'fstype': 'overlay'}, 'none', 'snapshot.reason.overlay'),
    ({'swaps': '/swapfile\t\t\t\tfile\t\t8388604\t\t0\t\t-2\n'}, 'none', 'snapshot.reason.swapfile'),
])
def test_snapshot_plan_follows_root_layout(ctx, system, tmp_path, layout, kind, reason):
    make_root(ctx, system, tmp_path, **layout)
    info = snapshot.inspect_root(ctx)
    assert snapshot.snapshot_plan(info) == (kind, reason)
    assert reason in TEXTS['ru'] and reason in TEXTS['en']


def test_root_info_reads_device_and_layout(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    info = snapshot.inspect_root(ctx)
    assert (info.fstype, info.device, info.subvol, info.boot_inside) == ('btrfs', SOURCE, '/@', True)
    assert not (info.systemd_hook or info.overlay or info.swapfile_in_root)


def test_swap_partition_and_swapfile_in_own_subvolume_do_not_block_snapshot(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, swaps='/dev/nvme0n1p7\t\t\t\tpartition\t8388604\t\t0\t\t-2\n'
                                           '/swap/swapfile\t\t\t\tfile\t\t8388604\t\t0\t\t-3\n')
    system.answer(['findmnt', '-no', 'SOURCE', '-T', '/swap/swapfile'], f'{SOURCE}[/@swap]\n')
    assert snapshot.snapshot_plan(snapshot.inspect_root(ctx))[0] == 'btrfs-ro'


def test_booted_snapshot_takes_device_from_kernel_cmdline(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, fstype='overlay',
              cmdline='BOOT_IMAGE=/@snapshots/x/boot/vmlinuz-linux root=UUID=1234-ab rw rootflags=subvol=@snapshots/x\n')
    info = snapshot.inspect_root(ctx)
    assert info.overlay and info.device == '/dev/disk/by-uuid/1234-ab'


def test_prepare_adds_hook_once_and_never_syncs_databases(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    conf = ctx.root / 'etc/mkinitcpio.conf'
    snapshot.prepare(ctx)
    writes = [call for call in system.calls if call['args'][0] == 'tee']
    assert len(writes) == 1 and writes[0]['sudo']
    new = writes[0]['input']
    assert re.search(r'^HOOKS=\(' + HOOKS + r' grub-btrfs-overlayfs\)$', new, re.M)
    assert '#    HOOKS=(base systemd)' in new
    conf.write_text(new)
    commands = system.commands()
    assert ['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'] in commands
    assert index(commands, ['cp', '-a', '/etc/mkinitcpio.conf']) < index(commands, ['tee'])
    assert index(commands, ['tee']) < index(commands, ['mkinitcpio', '-P'])
    assert [change['path'] for change in ctx.state.changes if change['kind'] == 'file'] == ['/etc/mkinitcpio.conf']

    system.calls.clear()
    snapshot.prepare(ctx)
    assert not [args for args in system.commands() if args[0] in ('tee', 'cp')]
    assert conf.read_text().count('grub-btrfs-overlayfs') == 1
    for args in system.commands():
        if args[0] == 'pacman':
            assert not any(re.fullmatch(r'-[A-Za-z]*y[A-Za-z]*', arg) or arg == '--refresh' for arg in args), args


def test_prepare_refuses_without_hook_support(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, hooks='base systemd autodetect block filesystems fsck')
    with pytest.raises(StepFailed):
        snapshot.prepare(ctx)
    assert not [args for args in system.commands() if args[0] in ('pacman', 'tee', 'mkinitcpio')]


def test_snapshot_commands_use_top_level_and_regenerate_grub(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['ls', '-A', TOP], '@\n@home\n@log\n@pkg\n')
    name = snapshot.take(ctx, 'btrfs-ro')
    assert re.fullmatch(r'quietline-pre-\d{8}-\d{6}', name)
    commands = system.commands()
    assert ['mktemp', '-d', '/run/quietline-top.XXXXXX'] in commands
    order = [index(commands, ['mount', '-o', 'subvolid=5', SOURCE, TOP]),
             index(commands, ['btrfs', 'subvolume', 'create', f'{TOP}/@snapshots']),
             index(commands, ['btrfs', 'subvolume', 'snapshot', '-r', f'{TOP}/@', f'{TOP}/@snapshots/{name}']),
             index(commands, ['umount', TOP]),
             index(commands, ['rmdir', TOP]),
             index(commands, ['grub-mkconfig', '-o', '/boot/grub/grub.cfg'])]
    assert order == sorted(order)
    assert all(call['sudo'] for call in system.calls if call['args'][0] in ('mktemp', 'mount', 'btrfs', 'umount'))
    assert ctx.state.snapshot == {'kind': 'btrfs-ro', 'name': name}
    assert State.load(ctx.state.path).snapshot == {'kind': 'btrfs-ro', 'name': name}


def test_writable_snapshot_and_existing_snapshots_subvolume(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, hooks='base systemd block filesystems fsck')
    name = snapshot.take(ctx, 'btrfs-rw')
    commands = system.commands()
    assert ['btrfs', 'subvolume', 'snapshot', f'{TOP}/@', f'{TOP}/@snapshots/{name}'] in commands
    assert not [args for args in commands if args[:3] == ['btrfs', 'subvolume', 'create']]


def test_snapshot_unmounts_after_failure(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['btrfs', 'subvolume', 'snapshot'], code=1)
    with pytest.raises(subprocess.CalledProcessError):
        snapshot.take(ctx, 'btrfs-ro')
    commands = system.commands()
    assert commands[-2:] == [['umount', TOP], ['rmdir', TOP]]
    assert ctx.state.snapshot is None
    assert not [args for args in commands if args[0] == 'grub-mkconfig']


@pytest.mark.parametrize('layout', [{'fstype': 'ext4'}, {'boot': '/dev/nvme0n1p6\n'}, {'fstype': 'overlay'}])
def test_snapshot_refuses_unsupported_root(ctx, system, tmp_path, layout):
    make_root(ctx, system, tmp_path, **layout)
    with pytest.raises(StepFailed):
        snapshot.take(ctx, 'btrfs-rw')
    assert not [args for args in system.commands() if args[0] in ('mount', 'btrfs', 'mktemp')]


def test_btrfs_rollback_commands(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/@/etc/fstab'], FSTAB)
    snapshot.rollback_btrfs(ctx, NAME)
    commands = system.commands()
    mv = [args for args in commands if args[0] == 'mv' and args[-1].startswith(f'{TOP}/@broken-')]
    assert len(mv) == 1 and mv[0][:3] == ['mv', '-T', f'{TOP}/@']
    assert re.fullmatch(re.escape(TOP) + r'/@broken-\d{8}-\d{6}', mv[0][3])
    order = [index(commands, ['mount', '-o', 'subvolid=5', SOURCE, TOP]),
             index(commands, ['btrfs', 'subvolume', 'show', f'{TOP}/@snapshots/{NAME}']),
             commands.index(mv[0]),
             index(commands, ['btrfs', 'subvolume', 'snapshot', f'{TOP}/@snapshots/{NAME}', f'{TOP}/@']),
             index(commands, ['tee', f'{TOP}/@/etc/fstab.quietline-new']),
             index(commands, ['mv', '-f', f'{TOP}/@/etc/fstab.quietline-new', f'{TOP}/@/etc/fstab']),
             index(commands, ['umount', TOP])]
    assert order == sorted(order)
    written = next(call['input'] for call in system.calls if call['args'][0] == 'tee')
    assert 'UUID=x / btrfs rw,noatime,subvol=/@ 0 0\n' in written
    assert 'UUID=x /home btrfs rw,noatime,subvolid=257,subvol=/@home 0 0\n' in written
    assert written == FSTAB.replace('subvolid=256,', '')
    assert not [args for args in commands if 'set-default' in args or args[:3] == ['btrfs', 'subvolume', 'delete']]
    assert not [args for args in commands if args[0] == 'mv' and not args[-1].startswith(TOP)]


def test_rollback_refuses_missing_snapshot(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['btrfs', 'subvolume', 'show', f'{TOP}/@snapshots/{NAME}'], code=1)
    with pytest.raises(StepFailed):
        snapshot.rollback_btrfs(ctx, NAME)
    commands = system.commands()
    assert not [args for args in commands if args[0] == 'mv' or args[:3] == ['btrfs', 'subvolume', 'snapshot']]
    assert commands[-2:] == [['umount', TOP], ['rmdir', TOP]]


@pytest.mark.parametrize('name', ['../@', '@', 'quietline-pre-x', f'{NAME}/..', ''])
def test_rollback_refuses_foreign_snapshot_names(ctx, system, tmp_path, name):
    make_root(ctx, system, tmp_path)
    with pytest.raises(StepFailed):
        snapshot.rollback_btrfs(ctx, name)
    assert not [args for args in system.commands() if args[0] in ('mount', 'mv', 'btrfs')]


def test_rollback_puts_root_back_when_new_root_fails(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['btrfs', 'subvolume', 'snapshot'], code=1)
    with pytest.raises(subprocess.CalledProcessError):
        snapshot.rollback_btrfs(ctx, NAME)
    moves = [args for args in system.commands() if args[0] == 'mv']
    assert moves[0][2:] == [f'{TOP}/@', moves[0][3]] and moves[-1] == ['mv', '-T', moves[0][3], f'{TOP}/@']
    assert system.commands()[-2:] == [['umount', TOP], ['rmdir', TOP]]


def test_rollback_from_booted_snapshot_uses_cmdline_device(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, fstype='overlay',
              cmdline='root=UUID=1234-ab rw rootflags=subvol=@snapshots/x\n')
    system.answer(['cat', f'{TOP}/@/etc/fstab'], FSTAB)
    snapshot.rollback_btrfs(ctx, NAME)
    assert ['mount', '-o', 'subvolid=5', '/dev/disk/by-uuid/1234-ab', TOP] in system.commands()


def test_rollback_restores_home_files_and_removes_created(ctx, system, tmp_path):
    home = ctx.home
    changed = home / '.config/fish/config.fish'
    changed.parent.mkdir(parents=True)
    changed.write_text('new')
    backup = home / '.config/fish/config.fish.quietline-20261028-101500'
    backup.write_text('old')
    created = home / '.config/quietline/pins.json'
    created.parent.mkdir(parents=True)
    created.write_text('[]')
    link = home / '.config/quickshell/quietline'
    link.parent.mkdir(parents=True)
    link.symlink_to('/usr/share/quietline/shell')
    music = home / 'Music'
    music.mkdir()
    (music / 'song.flac').write_text('data')
    for change in [{'kind': 'file', 'path': str(changed), 'backup': str(backup)},
                   {'kind': 'file', 'path': str(created), 'backup': None},
                   {'kind': 'file', 'path': str(link), 'backup': None},
                   {'kind': 'file', 'path': str(music), 'backup': None},
                   {'kind': 'file', 'path': '/etc/locale.gen', 'backup': '/etc/locale.gen.quietline-1'},
                   {'kind': 'package', 'name': 'fnm'}]:
        ctx.record(change)
    snapshot.rollback_home(ctx)
    assert changed.read_text() == 'old' and not backup.exists()
    assert not created.exists() and not link.is_symlink()
    assert (music / 'song.flac').read_text() == 'data'
    assert system.calls == []
    snapshot.rollback_home(ctx)
    assert changed.read_text() == 'old'


def test_btrfs_rollback_also_restores_home(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/@/etc/fstab'], FSTAB)
    created = ctx.home / '.config/quietline/region.json'
    created.parent.mkdir(parents=True)
    created.write_text('{}')
    ctx.record({'kind': 'file', 'path': str(created), 'backup': None})
    snapshot.rollback_btrfs(ctx, NAME)
    assert not created.exists()


def test_journal_rollback_keeps_preexisting_packages(ctx, system, tmp_path):
    ctx.root = tmp_path / 'root'
    config = ctx.home / '.config/hypr/hyprland.lua'
    config.parent.mkdir(parents=True)
    config.write_text('quietline')
    config.with_name('hyprland.lua.quietline-20261028-101500').write_text('mine')
    for change in [{'kind': 'package', 'name': 'hyprland'},
                   {'kind': 'file', 'path': '/etc/locale.gen', 'backup': '/etc/locale.gen.quietline-20261028-101500'},
                   {'kind': 'file', 'path': '/etc/greetd/quietline.toml', 'backup': None},
                   {'kind': 'service', 'unit': 'greetd.service'},
                   {'kind': 'package', 'name': 'fnm'},
                   {'kind': 'flatpak', 'id': 'com.brave.Browser'},
                   {'kind': 'file', 'path': str(config), 'backup': str(config) + '.quietline-20261028-101500'},
                   {'kind': 'package', 'name': 'slack-desktop'},
                   {'kind': 'package', 'name': 'fnm'}]:
        ctx.record(change)
    system.answer(['pacman', '-Qq'], 'hyprland\nfnm\n', 1)
    snapshot.rollback_journal(ctx)
    commands = system.commands()
    removals = [call for call in system.calls if call['args'][:2] == ['pacman', '-Rns']]
    assert len(removals) == 1 and removals[0]['sudo']
    assert removals[0]['args'][2:] == ['fnm', 'hyprland']
    assert 'git' not in removals[0]['args']
    assert commands.index(removals[0]['args']) == len(commands) - 1
    assert ['flatpak', 'uninstall', '--user', '-y', 'com.brave.Browser'] in commands
    assert ['systemctl', 'disable', 'greetd.service'] in commands
    assert ['mv', '-fT', '/etc/locale.gen.quietline-20261028-101500', '/etc/locale.gen'] in commands
    assert ['rm', '-f', '/etc/greetd/quietline.toml'] in commands
    system_calls = [call for call in system.calls if call['args'][0] in ('mv', 'rm', 'systemctl')]
    assert all(call['sudo'] for call in system_calls)
    flatpak = next(call for call in system.calls if call['args'][0] == 'flatpak')
    assert not flatpak['sudo']
    assert config.read_text() == 'mine'


def test_journal_rollback_without_new_packages_runs_no_pacman(ctx, system):
    ctx.record({'kind': 'service', 'unit': 'bluetooth.service'})
    snapshot.rollback_journal(ctx)
    assert not [args for args in system.commands() if args[0] == 'pacman']


FORBIDDEN = re.compile(r'\b(?:parted|sfdisk|fdisk|mkfs|wipefs|sgdisk|grub-install|bootctl|efibootmgr)\b'
                       r'|set-default|subvolume[\'"]?,?\s*[\'"]?delete')


def test_installer_never_touches_partitions():
    repo = Path(__file__).resolve().parents[2]
    files = sorted((repo / 'src/quietline_install').rglob('*.py'))
    if (repo / 'install.sh').exists():
        files.append(repo / 'install.sh')
    assert repo / 'src/quietline_install/snapshot.py' in files
    for path in files:
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            assert not FORBIDDEN.search(line), f'{path.relative_to(repo)}:{number}: {line.strip()}'
    assert not FORBIDDEN.search('grub-mkconfig -o /boot/grub/grub.cfg')
    assert FORBIDDEN.search("['btrfs', 'subvolume', 'delete', top]")
    assert FORBIDDEN.search('mkfs.btrfs -L arch /dev/x')


def test_snapshot_without_grub_cfg_in_boot_skips_menu(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['test', '-e', '/boot/grub/grub.cfg'], code=1)
    name = snapshot.take(ctx, 'btrfs-ro')
    assert ctx.state.snapshot == {'kind': 'btrfs-ro', 'name': name}
    assert not [args for args in system.commands() if args[0] == 'grub-mkconfig']
