"""Tests for the cover platform, run with stubbed Home Assistant base classes."""
from unittest.mock import MagicMock

from custom_components.digitalstrom.cover import DigitalstromCover


def test_supported_features_use_current_enum_names():
    from custom_components.digitalstrom.cover import CoverEntityFeature

    cover = DigitalstromCover(
        hass=MagicMock(),
        scene_on=MagicMock(),
        scene_off=MagicMock(),
        listener=MagicMock(),
    )

    assert cover.supported_features == CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
