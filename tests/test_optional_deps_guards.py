from __future__ import annotations

import pytest

from core.utils.optional_deps import FeatureUnavailable, require


def test_require_returns_ok_for_existing_module() -> None:
    ok, msg = require("json", "", "test feature")
    assert ok is True
    assert msg == ""


def test_require_returns_controlled_message_for_missing_module() -> None:
    ok, msg = require("definitely_missing_dep_xyz", "pip install dep", "my feature")
    assert ok is False
    assert "missing dependency" in msg.lower()
    assert "definitely_missing_dep_xyz" in msg
    assert "pip install dep" in msg


def test_require_can_raise_feature_unavailable() -> None:
    with pytest.raises(FeatureUnavailable) as exc:
        require(
            "definitely_missing_dep_xyz",
            "pip install dep",
            "my feature",
            raise_on_missing=True,
        )
    assert "missing dependency" in str(exc.value).lower()
