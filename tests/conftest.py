"""Make the client module importable without pulling in Home Assistant.

The package __init__ imports homeassistant, which is not needed to exercise
the page parsing, so the integration directory itself goes on the path.
"""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "airbalticcard")
)
