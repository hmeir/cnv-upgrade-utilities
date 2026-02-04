"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def valid_y_stream_pairs():
    """Valid Y-stream upgrade pairs (source, target)."""
    return [
        ("4.19", "4.20"),
        ("4.20", "4.21"),
        ("4.18", "4.19"),
    ]


@pytest.fixture
def valid_z_stream_pairs():
    """Valid Z-stream upgrade pairs (source, target)."""
    return [
        ("4.20", "4.20"),
        ("4.19", "4.19"),
        ("4.20.1", "4.20.2"),
        ("4.20.1", "4.20"),  # Full to minor is valid
    ]


@pytest.fixture
def valid_eus_pairs():
    """Valid EUS upgrade pairs (source, target)."""
    return [
        ("4.18", "4.20"),
        ("4.20", "4.22"),
        ("4.16", "4.18"),
    ]


@pytest.fixture
def valid_latest_z_pairs():
    """Valid latest-z upgrade pairs (source, target)."""
    return [
        ("4.20.0", "4.20"),
        ("4.19.0", "4.19"),
        ("4.18.0", "4.18"),
    ]
