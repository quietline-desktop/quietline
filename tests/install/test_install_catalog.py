import subprocess
import sys
from pathlib import Path

import pytest

from quietline_install.catalog import Catalog, Item, Section, load_catalog
from quietline_install.texts import TEXTS

CATALOG_PATH = Path(__file__).resolve().parents[2] / 'installer' / 'catalog.toml'

RECOMMENDED = {
    'chrome', 'telegram', 'dolphin', 'vscode', '1password', 'amneziavpn', 'remmina', 'onlyoffice',
    'docker', 'dotnet-latest', 'node-lts', 'python-system', 'devtools',
}


@pytest.fixture(scope='module')
def catalog():
    return load_catalog(CATALOG_PATH)


def write_catalog(tmp_path, body):
    path = tmp_path / 'catalog.toml'
    path.write_text('[core]\npackages = ["git"]\nservices = []\n\n' + body)
    return path


def test_catalog_is_valid(catalog):
    catalog.validate()
    assert catalog.sections
    assert all(isinstance(section, Section) for section in catalog.sections)


def test_every_title_key_has_a_text(catalog):
    for section in catalog.sections:
        for language in TEXTS:
            assert section.title_key in TEXTS[language], section.id


def test_recommended_set_matches_the_spec(catalog):
    assert catalog.recommended() == RECOMMENDED


def test_plan_always_contains_core(catalog):
    for selection in (set(), {'firefox'}, catalog.recommended()):
        plan = catalog.plan(selection)
        for package in catalog.core_packages:
            assert package in plan.repo
        assert plan.services[:len(catalog.core_services)] == catalog.core_services


def test_empty_selection_installs_only_core(catalog):
    plan = catalog.plan(set())
    assert plan.repo == catalog.core_packages
    assert plan.flatpak == plan.aur == plan.manual == plan.fnm == plan.uv == []


def test_plan_splits_sources(catalog):
    plan = catalog.plan({'brave', 'slack', 'docker-desktop'})
    assert plan.flatpak == ['com.brave.Browser']
    assert plan.aur == ['slack-desktop']
    assert plan.manual == ['docker-desktop']
    assert 'slack-desktop' not in plan.repo and 'com.brave.Browser' not in plan.repo


def test_mixed_sources_in_one_item(catalog):
    plan = catalog.plan({'onlyoffice'})
    assert plan.flatpak == ['org.onlyoffice.desktopeditors']
    for package in ('ttf-carlito', 'ttf-caladea', 'ttf-liberation'):
        assert package in plan.repo


def test_services_come_from_selected_items(catalog):
    assert 'docker.socket' in catalog.plan({'docker'}).services
    assert 'docker.socket' not in catalog.plan(set()).services
    assert 'docker.socket' not in catalog.plan({'docker-desktop'}).services


def test_plan_has_no_duplicates_and_stable_order(catalog):
    everything = {item.id for section in catalog.sections for item in section.items}
    plan = catalog.plan(everything)
    for field in (plan.repo, plan.flatpak, plan.aur, plan.manual, plan.fnm, plan.uv, plan.services, plan.pins):
        assert len(field) == len(set(field))
    assert plan == catalog.plan(set(reversed(sorted(everything))))


def test_advanced_items_are_children_of_their_section(catalog):
    by_id = {section.id: section for section in catalog.sections}
    assert [item.id for item in by_id['dotnet'].advanced_items] == ['dotnet-8', 'dotnet-9']
    assert [item.id for item in by_id['node'].advanced_items] == ['node-22', 'node-24', 'node-26']
    assert [item.id for item in by_id['python'].advanced_items] == ['python-3.12', 'python-3.13']
    assert [item.id for item in by_id['dotnet'].basic_items] == ['dotnet-latest']
    assert by_id['browsers'].advanced_items == []


def test_dotnet_versions_are_packages(catalog):
    plan = catalog.plan({'dotnet-latest', 'dotnet-8', 'dotnet-9'})
    for package in ('dotnet-sdk', 'aspnet-runtime', 'aspnet-targeting-pack', 'dotnet-sdk-8.0',
                    'aspnet-runtime-8.0', 'dotnet-sdk-9.0', 'aspnet-runtime-9.0'):
        assert package in plan.repo


def test_node_goes_through_fnm(catalog):
    plan = catalog.plan({'node-lts'})
    assert plan.fnm == ['lts-latest']
    assert 'fnm' in plan.repo and 'pnpm' in plan.repo
    plan = catalog.plan({'node-22', 'node-26'})
    assert plan.fnm == ['22', '26']
    assert 'fnm' in plan.repo and 'pnpm' not in plan.repo
    assert not any(package.startswith('nodejs') for package in catalog.plan({'node-lts', 'node-24'}).repo)


def test_python_versions_go_through_uv(catalog):
    plan = catalog.plan({'python-system'})
    assert plan.uv == []
    assert {'python', 'python-pip', 'uv'} <= set(plan.repo)
    plan = catalog.plan({'python-3.12', 'python-3.13'})
    assert plan.uv == ['3.12', '3.13']
    assert 'uv' in plan.repo


def test_pins_follow_selection_order(catalog):
    plan = catalog.plan({'firefox', 'brave', 'dolphin', 'telegram'})
    assert plan.pins == ['org.kde.dolphin', 'firefox', 'com.mitchellh.ghostty', 'org.telegram.desktop']


def test_pins_full_recommended_set(catalog):
    plan = catalog.plan(catalog.recommended())
    assert plan.pins == ['org.kde.dolphin', 'google-chrome', 'code', 'com.mitchellh.ghostty',
                         'org.telegram.desktop']


def test_pins_skip_unselected(catalog):
    assert catalog.plan(set()).pins == ['com.mitchellh.ghostty']


def test_unknown_selection_is_rejected(catalog):
    with pytest.raises(ValueError, match='nonesuch'):
        catalog.plan({'nonesuch'})


def test_unknown_source_is_rejected(tmp_path):
    path = write_catalog(tmp_path, '''
[[section]]
id = "s"
title_key = "sectionFiles"
multiple = false

[[section.item]]
id = "bad-item"
name = "Bad"
source = "snap"
packages = ["x"]
''')
    with pytest.raises(ValueError, match='bad-item'):
        load_catalog(path)


def test_duplicate_ids_are_rejected(tmp_path):
    path = write_catalog(tmp_path, '''
[[section]]
id = "s"
title_key = "sectionFiles"
multiple = true

[[section.item]]
id = "twin"
name = "A"
source = "repo"
packages = ["a"]

[[section.item]]
id = "twin"
name = "B"
source = "repo"
packages = ["b"]
''')
    with pytest.raises(ValueError, match='twin'):
        load_catalog(path)


def test_flatpak_needs_exactly_one_app_id(tmp_path):
    path = write_catalog(tmp_path, '''
[[section]]
id = "s"
title_key = "sectionFiles"
multiple = false

[[section.item]]
id = "two-apps"
name = "Two"
source = "flatpak"
packages = ["a.b.C", "d.e.F"]
''')
    with pytest.raises(ValueError, match='two-apps'):
        load_catalog(path)


def test_pin_needs_desktop_id(tmp_path):
    path = write_catalog(tmp_path, '''
[[section]]
id = "s"
title_key = "sectionFiles"
multiple = false

[[section.item]]
id = "no-desktop"
name = "No desktop"
source = "repo"
packages = ["a"]
pin = "files"
''')
    with pytest.raises(ValueError, match='no-desktop'):
        load_catalog(path)


def test_unknown_pin_kind_is_rejected(tmp_path):
    path = write_catalog(tmp_path, '''
[[section]]
id = "s"
title_key = "sectionFiles"
multiple = false

[[section.item]]
id = "odd-pin"
name = "Odd"
source = "repo"
packages = ["a"]
desktop = "a"
pin = "sidebar"
''')
    with pytest.raises(ValueError, match='odd-pin'):
        load_catalog(path)


def test_no_aur_package_for_hyprland_or_quickshell(catalog):
    for section in catalog.sections:
        for item in section.items:
            if item.source == 'aur':
                for package in item.packages:
                    assert not package.startswith(('hyprland', 'quickshell')), item.id
    assert 'hyprland' in catalog.core_packages and 'quickshell' in catalog.core_packages


def test_aur_only_for_the_documented_apps(catalog):
    aur = {item.id: item.packages for section in catalog.sections for item in section.items
           if item.source == 'aur'}
    assert aur == {
        'chrome': ['google-chrome'],
        'slack': ['slack-desktop'],
        'vscode': ['visual-studio-code-bin'],
        '1password': ['1password'],
    }


def test_items_have_proper_shape(catalog):
    for section in catalog.sections:
        for item in section.items:
            assert isinstance(item, Item)
            assert item.name
            if item.advanced:
                assert section.id in ('dotnet', 'node', 'python')


def run_check_script(tmp_path, absent):
    """Запускает scripts/check-catalog.py с поддельным pacman, который не знает пакеты из `absent`."""
    fake = tmp_path / 'bin'
    fake.mkdir()
    pacman = fake / 'pacman'
    pacman.write_text('#!/bin/sh\ncase " %s " in *" $2 "*) exit 1;; esac\nexit 0\n' % ' '.join(absent))
    pacman.chmod(0o755)
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'check-catalog.py'
    env = {'PATH': f'{fake}:/usr/bin:/bin'}
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env)


def test_check_script_reports_missing_packages(tmp_path):
    result = run_check_script(tmp_path, ['firefox', 'ttf-carlito'])
    assert result.returncode == 1
    assert result.stdout.strip() == 'missing: firefox ttf-carlito'


def test_check_script_passes_when_all_found(tmp_path):
    result = run_check_script(tmp_path, [])
    assert result.returncode == 0
    assert result.stdout.strip() == 'all packages found'


def test_check_script_skips_non_repo_sources(tmp_path):
    result = run_check_script(tmp_path, ['google-chrome', 'com.brave.Browser', 'slack-desktop', 'lts-latest'])
    assert result.returncode == 0
