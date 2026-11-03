"""Каталог программ установщика: загрузка `installer/catalog.toml`, проверка и пакеты выбора.

Схема `catalog.toml`:

    [core]                    # основа, ставится всегда
    packages = [...]          # пакеты репозитория Arch
    services = [...]          # службы systemd, которые включаются
    aur = [...]               # необязательно: пакеты AUR основы, собираются раньше пакетов AUR вариантов
    desktop = "..."           # необязательно: desktop ID программы основы для закрепления
    pin = "terminal"          # вид закрепления программы основы

    [[section]]               # раздел экрана «Программы»
    id, title_key, multiple   # title_key — ключ заголовка из texts.TEXTS; multiple — можно несколько

    [[section.item]]          # вариант раздела
    id                        # уникален среди вариантов (id разделов уникальны среди разделов); по нему хранится выбор
    name                      # название программы (имя собственное, не переводится)
    source                    # repo | flatpak | aur | manual | fnm | uv
    packages                  # repo/aur — пакеты; flatpak — ровно один id приложения;
                              # fnm/uv — версии (`lts-latest`, `22`, `3.12`); manual — пусто
    repo_packages             # необязательно: пакеты репозитория Arch, нужные варианту сверх `packages`
    desktop                   # desktop ID без `.desktop` (или пусто) — для закрепления в доке
    recommended               # входит в рекомендуемый набор
    services                  # службы systemd варианта
    pin                       # files | browser | code | terminal | messenger | пусто
    advanced                  # вариант «Расширенных»: экран показывает его вложенным в раздел
    provides                  # необязательно: пакеты репозитория, которые вариант заменяет собой;
                              # при его выборе они не ставятся, даже если их просит другой вариант

«Расширенные» версии (.NET 8.0/9.0, Node.js 22/24/26, Python 3.12/3.13) — обычные варианты раздела
с `advanced = true`: `Section.basic_items` и `Section.advanced_items` делят `Section.items` для экрана,
а `Catalog.plan()` обращается с ними как с остальными.

Порядок в плане не зависит от порядка выбора: основа, затем разделы и варианты в порядке каталога.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

SOURCES = ('repo', 'flatpak', 'aur', 'manual', 'fnm', 'uv')
PIN_KINDS = ('files', 'browser', 'code', 'terminal', 'messenger')


@dataclass
class Item:
    """Вариант раздела каталога."""

    id: str
    name: str
    source: str
    packages: list[str] = field(default_factory=list)
    repo_packages: list[str] = field(default_factory=list)
    desktop: str = ''
    recommended: bool = False
    services: list[str] = field(default_factory=list)
    pin: str = ''
    advanced: bool = False
    provides: list[str] = field(default_factory=list)


@dataclass
class Section:
    """Раздел каталога: заголовок, режим выбора и варианты."""

    id: str
    title_key: str
    multiple: bool
    items: list[Item]

    @property
    def basic_items(self) -> list[Item]:
        return [item for item in self.items if not item.advanced]

    @property
    def advanced_items(self) -> list[Item]:
        return [item for item in self.items if item.advanced]


@dataclass
class Plan:
    """Что установить по выбору: пакеты по источникам, службы и закрепления дока.

    `manual` — id вариантов с ручной установкой; `fnm` и `uv` — списки версий.
    """

    repo: list[str] = field(default_factory=list)
    flatpak: list[str] = field(default_factory=list)
    aur: list[str] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)
    fnm: list[str] = field(default_factory=list)
    uv: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    pins: list[str] = field(default_factory=list)


@dataclass
class Catalog:
    core_packages: list[str]
    core_services: list[str]
    core_item: Item
    sections: list[Section]
    core_aur: list[str] = field(default_factory=list)

    def items(self) -> list[Item]:
        return [item for section in self.sections for item in section.items]

    def validate(self) -> None:
        """Проверяет каталог; нарушение — `ValueError` с id варианта или раздела."""
        section_ids = set()
        for section in self.sections:
            if section.id in section_ids:
                raise ValueError(f'duplicate id: {section.id}')
            section_ids.add(section.id)
        seen = set()
        for item in self.items():
            if item.id in seen:
                raise ValueError(f'duplicate id: {item.id}')
            seen.add(item.id)
            if item.source not in SOURCES:
                raise ValueError(f'{item.id}: unknown source {item.source!r}')
            if item.source == 'flatpak' and len(item.packages) != 1:
                raise ValueError(f'{item.id}: flatpak needs exactly one app id')
            if item.source in ('repo', 'aur', 'fnm', 'uv') and not item.packages:
                raise ValueError(f'{item.id}: no packages')
            if item.pin and item.pin not in PIN_KINDS:
                raise ValueError(f'{item.id}: unknown pin {item.pin!r}')
            if item.pin and not item.desktop:
                raise ValueError(f'{item.id}: pin needs a desktop ID')
        if self.core_item.pin and self.core_item.pin not in PIN_KINDS:
            raise ValueError(f'core: unknown pin {self.core_item.pin!r}')
        if self.core_item.pin and not self.core_item.desktop:
            raise ValueError('core: pin needs a desktop ID')

    def recommended(self) -> set[str]:
        """Id вариантов рекомендуемого набора."""
        return {item.id for item in self.items() if item.recommended}

    def plan(self, selection: set[str]) -> Plan:
        """План установки по выбору; основа входит всегда. Неизвестный id — `ValueError`."""
        known = {item.id for item in self.items()}
        for item_id in selection:
            if item_id not in known:
                raise ValueError(f'unknown item: {item_id}')
        chosen = [item for item in self.items() if item.id in selection]
        plan = Plan(repo=list(self.core_packages), aur=list(self.core_aur), services=list(self.core_services))
        for item in chosen:
            plan.repo.extend(item.repo_packages)
            if item.source == 'repo':
                plan.repo.extend(item.packages)
            elif item.source == 'manual':
                plan.manual.append(item.id)
            else:
                getattr(plan, item.source).extend(item.packages)
            plan.services.extend(item.services)
        provided = {name for item in chosen for name in item.provides}
        plan.repo = [name for name in plan.repo if name not in provided]
        for name in ('repo', 'flatpak', 'aur', 'manual', 'fnm', 'uv', 'services'):
            setattr(plan, name, list(dict.fromkeys(getattr(plan, name))))
        plan.pins = self._pins(chosen)
        return plan

    def _pins(self, chosen: list[Item]) -> list[str]:
        """Desktop ID закреплений: по одному на вид (первый выбранный в порядке каталога)."""
        candidates = [self.core_item, *chosen]
        pins = []
        for kind in PIN_KINDS:
            for item in candidates:
                if item.pin == kind and item.desktop:
                    pins.append(item.desktop)
                    break
        return pins


def _item(raw: dict) -> Item:
    try:
        return Item(
            id=raw['id'], name=raw['name'], source=raw['source'],
            packages=list(raw.get('packages', [])), repo_packages=list(raw.get('repo_packages', [])),
            desktop=raw.get('desktop', ''), recommended=raw.get('recommended', False),
            services=list(raw.get('services', [])), pin=raw.get('pin', ''),
            advanced=raw.get('advanced', False), provides=list(raw.get('provides', [])),
        )
    except KeyError as error:
        raise ValueError(f'{raw.get("id", "?")}: missing field {error}') from None


def load_catalog(path: Path) -> Catalog:
    """Читает и проверяет каталог."""
    with open(path, 'rb') as file:
        raw = tomllib.load(file)
    core = raw['core']
    core_item = Item(id='core', name='core', source='repo', packages=list(core['packages']),
                     desktop=core.get('desktop', ''), pin=core.get('pin', ''))
    sections = [
        Section(id=section['id'], title_key=section['title_key'], multiple=section['multiple'],
                items=[_item(item) for item in section.get('item', [])])
        for section in raw.get('section', [])
    ]
    catalog = Catalog(core_packages=list(core['packages']), core_services=list(core.get('services', [])),
                      core_item=core_item, sections=sections, core_aur=list(core.get('aur', [])))
    catalog.validate()
    return catalog
