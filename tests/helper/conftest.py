"""Общая изоляция тестов `quietline-shell`: чужой `region.json` не влияет на язык уведомлений."""

import pytest


@pytest.fixture(autouse=True)
def isolated_language(tmp_path_factory, monkeypatch):
    """Без `region.json` и с `LANG=ru_RU.UTF-8`: уведомления по умолчанию русские."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
