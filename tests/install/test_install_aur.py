"""Сборка AUR: инструкции показываются и подтверждаются до makepkg."""

import urllib.error

import pytest

from quietline_install.runner import StepFailed
from quietline_install.steps import aur


def clone_with_pkgbuild(ctx, name, text='pkgname=x\nbuild() { :; }\n'):
    directory = ctx.home / '.cache/quietline/aur' / name
    directory.mkdir(parents=True)
    (directory / 'PKGBUILD').write_text(text)
    return directory


def test_pkgbuild_is_shown_and_must_be_confirmed(ctx, system):
    directory = clone_with_pkgbuild(ctx, 'google-chrome', 'pkgname=google-chrome\nsource=(https://dl.google.com/x.deb)\n')
    (directory / 'google-chrome.install').write_text('post_install() { echo hi; }\n')
    ctx.answers.append(False)
    with pytest.raises(StepFailed, match='google-chrome'):
        aur.aur_install(ctx, 'google-chrome')
    assert any('source=(https://dl.google.com/x.deb)' in line for line in ctx.lines)
    assert any('post_install() { echo hi; }' in line for line in ctx.lines)
    assert not any(command[0] == 'makepkg' for command in system.commands())
    assert ctx.state.changes == []


def test_long_pkgbuild_is_shown_whole_and_asked_once(ctx, system):
    clone_with_pkgbuild(ctx, 'google-chrome', ''.join(f'line{index}\n' for index in range(60)))
    ctx.answers.append(True)
    aur.aur_install(ctx, 'google-chrome')
    assert 'line59' in ctx.lines
    assert ctx.questions == [ctx.t('aur.confirm', name='google-chrome')] and ctx.defaults == [True]


def test_review_screen_replaces_terminal_question(ctx, system):
    clone_with_pkgbuild(ctx, 'google-chrome', 'pkgname=google-chrome\n')
    reviewed = []
    ctx.review = lambda name, lines: reviewed.append((name, lines)) or False
    with pytest.raises(StepFailed, match='google-chrome'):
        aur.aur_install(ctx, 'google-chrome')
    assert reviewed == [('google-chrome', ['---- google-chrome/PKGBUILD ----', 'pkgname=google-chrome'])]
    assert ctx.questions == [] and ctx.lines == []
    assert not any(command[0] == 'makepkg' for command in system.commands())


def test_docker_desktop_build_explains_terms_and_contexts(ctx, system):
    clone_with_pkgbuild(ctx, 'docker-desktop')
    ctx.answers.append(True)
    aur.aur_install(ctx, 'docker-desktop')
    assert ctx.lines[-1] == ctx.t('aur.dockerDesktop')
    assert 'desktop-linux' in ctx.lines[-1]


def test_other_files_in_clone_are_listed(ctx, system):
    directory = clone_with_pkgbuild(ctx, 'slack-desktop')
    (directory / 'slack.patch').write_text('--- a\n+++ b\n')
    (directory / 'helper.sh').write_text('rm -rf ~\n')
    (directory / '.git').mkdir()
    (directory / '.git' / 'config').write_text('[core]\n')
    ctx.answers.append(False)
    with pytest.raises(StepFailed):
        aur.aur_install(ctx, 'slack-desktop')
    listing = '\n'.join(ctx.lines)
    assert 'slack.patch' in listing and 'helper.sh' in listing
    assert '.git' not in listing
    assert 'rm -rf ~' not in listing


def test_confirmed_build_runs_makepkg_in_clone(ctx, system):
    directory = clone_with_pkgbuild(ctx, 'visual-studio-code-bin')
    ctx.answers.append(True)
    aur.aur_install(ctx, 'visual-studio-code-bin')
    pull = next(call for call in system.calls if call['args'][:1] == ['git'])
    assert pull['args'] == ['git', '-C', str(directory), 'pull', '--ff-only']
    assert pull['env'] == aur.GIT_TIMEOUT
    build = system.calls[-1]
    assert build['args'] == ['makepkg', '-si', '--cleanbuild']
    assert build['cwd'] == directory and build['interactive'] and not build['sudo']
    assert ctx.state.changes == [{'kind': 'package', 'name': 'visual-studio-code-bin'}]


def test_fresh_package_is_cloned_from_aur(ctx, system):
    ctx.answers.append(False)
    with pytest.raises(StepFailed):
        aur.aur_install(ctx, 'google-chrome')
    clone = system.calls[0]
    assert clone['args'] == ['git', 'clone', 'https://aur.archlinux.org/google-chrome.git',
                             str(ctx.home / '.cache/quietline/aur/google-chrome')]
    assert clone['env'] == aur.GIT_TIMEOUT


def test_failed_clone_is_a_step_failure(ctx, system):
    system.answer(['git', 'clone'], code=128)
    with pytest.raises(StepFailed, match='google-chrome'):
        aur.aur_install(ctx, 'google-chrome')


def test_1password_key_imported_before_build(ctx, system):
    clone_with_pkgbuild(ctx, '1password')
    system.answer(['curl', '-fsS', 'https://downloads.1password.com/linux/keys/1password.asc'], 'KEYDATA')
    ctx.answers.append(True)
    aur.aur_install(ctx, '1password')
    commands = system.commands()
    gpg = next(i for i, c in enumerate(commands) if c[:2] == ['gpg', '--import'])
    build = next(i for i, c in enumerate(commands) if c[0] == 'makepkg')
    assert gpg < build and system.calls[gpg]['input'] == 'KEYDATA'
    assert not any(call['sudo'] for call in system.calls)


def test_failed_makepkg_is_a_step_failure(ctx, system):
    clone_with_pkgbuild(ctx, 'google-chrome')
    system.answer(['makepkg'], code=4)
    ctx.answers.append(True)
    with pytest.raises(StepFailed, match='makepkg'):
        aur.aur_install(ctx, 'google-chrome')
    assert ctx.state.changes == []


def test_update_lists_only_newer_aur_versions(ctx, system):
    system.answer(['pacman', '-Q'], 'google-chrome 140.0-1\n1password 8.11.0-1\n')
    system.answer(['vercmp', '141.0-1', '140.0-1'], '1\n')
    system.answer(['vercmp', '8.11.0-1', '8.11.0-1'], '0\n')
    fetch = lambda names: {'google-chrome': '141.0-1', '1password': '8.11.0-1'}
    assert aur.aur_outdated(ctx, ['google-chrome', '1password'], fetch) == ['google-chrome']


def test_rpc_failure_is_not_a_crash(ctx, system):
    logged = []
    ctx.log = logged.append
    system.answer(['pacman', '-Q'], 'google-chrome 140.0-1\n')

    def fetch(names):
        raise urllib.error.URLError('no network')

    assert aur.aur_outdated(ctx, ['google-chrome'], fetch) == []
    assert any('AUR' in line for line in logged)


def test_aur_step_checks_installed_package(ctx, system):
    step = aur.aur_step('google-chrome')
    assert step.id == 'aur-google-chrome' and step.source == 'AUR: google-chrome'
    assert step.title_key == 'step.aur'
    system.answer(['pacman', '-Q', 'google-chrome'], code=1)
    assert step.check(ctx) is False
    system.answer(['pacman', '-Q', 'google-chrome'], 'google-chrome 1-1\n')
    assert step.check(ctx) is True
