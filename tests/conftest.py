import os
import pytest

# Set minimal env vars before any import of config.settings
os.environ.setdefault("BINANCE_API_KEY", "test_key")
os.environ.setdefault("BINANCE_API_SECRET", "test_secret")
os.environ.setdefault("STRATEGY_ENABLED", "false")


@pytest.fixture
def tmp_json(tmp_path):
    """Return a path string for a temporary JSON file."""
    return str(tmp_path / "test.json")


@pytest.fixture
def tmp_csv(tmp_path):
    """Return a path string for a temporary CSV file."""
    return str(tmp_path / "test.csv")
