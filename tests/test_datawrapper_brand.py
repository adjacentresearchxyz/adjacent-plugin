"""Datawrapper charts must receive the Adjacent visual contract."""

from __future__ import annotations

import sys

from tests.test_offline_signals import load_script


def test_datawrapper_metadata_uses_adjacent_brand_tokens():
    module = load_script("_datawrapper.py")
    payload = module.adjacent_metadata(
        title="Index moved higher",
        intro="The index gained over the period.",
    )

    assert payload["title"] == "Index moved higher"
    assert payload["metadata"]["describe"]["intro"] == "The index gained over the period."
    visualize = payload["metadata"]["visualize"]
    assert visualize["base-color"] == "#0a0f0d"
    assert visualize["background"] == "#ece9e2"
    assert visualize["plot-background"] == "#ece9e2"
    assert visualize["grid-color"] == "#ecebea"
    assert visualize["color-range"] == module.SERIES
    assert payload["metadata"]["describe"]["source-name"] == "Adjacent"


def test_brand_chart_patches_before_publish(monkeypatch):
    module = load_script("_datawrapper.py")
    calls = []

    def fake_patch(api_key, path, body):
        calls.append(("patch", path, body))
        return {"ok": True}

    monkeypatch.setattr(module, "patch", fake_patch)
    result = module.brand_chart(
        "secret-is-not-logged",
        "chart-123",
        title="Index moved higher",
        intro="The index gained over the period.",
    )

    assert result == {"ok": True}
    assert calls[0][0] == "patch"
    assert calls[0][1] == "/v3/charts/chart-123"
    assert calls[0][2]["metadata"]["describe"]["source-name"] == "Adjacent"
