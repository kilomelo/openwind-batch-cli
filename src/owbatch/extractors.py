"""Feature extraction entry points.

Feature extraction is intentionally deferred, but future implementations
should be built on top of ``owbatch.response`` so plotting, resonance picking,
and analysis share the same impedance/admittance semantics.
"""

from __future__ import annotations


def extract_frequency_features() -> None:
    """Placeholder for resonance and antiresonance extraction."""

    raise NotImplementedError("Feature extraction is not implemented yet.")
