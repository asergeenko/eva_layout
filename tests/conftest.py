"""Pytest configuration and shared fixtures."""

import pytest
import sys
from pathlib import Path

# Add the parent directory to sys.path so we can import layout_optimizer
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session") 
def dxf_samples_dir(project_root):
    """Return the DXF samples directory."""
    return project_root / "dxf_samples"