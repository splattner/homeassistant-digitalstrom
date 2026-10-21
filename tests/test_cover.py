"""Tests for the cover platform."""
from unittest.mock import MagicMock

from homeassistant.components.cover import CoverEntityFeature

from custom_components.digitalstrom.cover import DigitalstromCover


def test_supported_features_use_current_enum_names():
    cover = DigitalstromCover(
        hass=MagicMock(),
        scene_on=MagicMock(),
        scene_off=MagicMock(),
        listener=MagicMock(),
    )

    assert cover.supported_features == CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
