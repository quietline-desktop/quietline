"""Шаги установки по выбору пользователя: всё для входа в сеанс — раньше AUR, заголовки окон (hyprbars) —
после них, ручные шаги — последними."""

from quietline_install.catalog import Plan
from quietline_install.runner import Step
from quietline_install.steps import aur, configs, packages, session


def build_steps(plan: Plan) -> list[Step]:
    steps = [packages.upgrade_step(), packages.repo_step(plan.repo), packages.graphics_step(),
             packages.locales_step(), packages.quietline_package_step(), packages.services_step(plan.services),
             configs.hyprland_step(), configs.fish_step(with_fnm=bool(plan.fnm)), configs.tide_step(),
             configs.micro_step(),
             configs.quickshell_link_step(), configs.user_dirs_step(), configs.region_step(),
             configs.pins_step(plan.pins), session.greetd_step(), session.keyring_step()]
    if plan.flatpak:
        steps.append(packages.flatpak_step(plan.flatpak))
    if plan.fnm:
        steps.append(packages.fnm_step(plan.fnm))
    if plan.uv:
        steps.append(packages.uv_step(plan.uv))
    steps += [aur.aur_step(name) for name in plan.aur]
    steps.append(session.default_shell_step())
    steps.append(session.hyprbars_step())
    if 'docker' in plan.repo:
        steps.append(session.docker_group_step())
    manual = {'docker-desktop': session.docker_desktop_step, 'amneziavpn': session.amneziavpn_step}
    steps += [manual[item]() for item in plan.manual if item in manual]
    return steps
