from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _janela_fixa_do_rate_limit(monkeypatch):
    """Os limites contam por janela de 1 minuto do relógio; um teste que cruzasse a virada do
    minuto começaria a contar do zero no meio. Aqui o limitador vê sempre o mesmo instante."""
    monkeypatch.setattr("apps.core.ratelimit.time", SimpleNamespace(time=lambda: 1_000_020.0))
