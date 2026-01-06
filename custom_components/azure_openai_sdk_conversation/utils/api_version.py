# ============================================================================
# utils/api_version.py
# ============================================================================
"""API version management utilities."""

from __future__ import annotations

from typing import Any


class APIVersionManager:
    """API version management and model recommendations."""

    # Map version -> metadata with 'since' as a tuple(year, month, day)
    _KNOWN: dict[str, dict[str, Any]] = {
        # Common examples (add/remove as needed)
        "2024-10-01-preview": {"since": (2024, 10, 1)},
        "2025-01-01-preview": {"since": (2025, 1, 1)},
        "2025-03-01-preview": {
            "since": (2025, 3, 1),
            "responses_min": True,  # Official Responses API from here on
        },
    }

    @classmethod
    def _date_tuple(cls, ver: str) -> tuple[int, int, int]:
        core = (ver or "").split("-preview")[0]
        parts = core.split("-")
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:  # noqa: BLE001
            return (1900, 1, 1)

    @classmethod
    def known_versions(cls) -> list[str]:
        """List sorted by 'since' ascending, deterministic."""
        return sorted(
            cls._KNOWN.keys(),
            key=lambda v: cls._KNOWN.get(v, {}).get("since", cls._date_tuple(v)),
        )

    @classmethod
    def ensure_min(cls, ver: str, minimum: str) -> str:
        """Returns 'ver' if >= minimum, otherwise 'minimum'."""
        v = cls._date_tuple(ver)
        m = cls._date_tuple(minimum)
        return ver if v >= m else minimum

    @classmethod
    def best_for_model(cls, model: str | None, fallback: str | None = None) -> str:
        """
        Selects recommended version deterministically:
        - for 'o*' models, force at least 2025-03-01-preview (Responses),
        - otherwise use the last known (sorted by 'since') or fallback.
        """
        m = (model or "").strip().lower()
        if m.startswith("o"):
            if "2025-03-01-preview" in cls._KNOWN:
                return "2025-03-01-preview"
        # Not 'o*': choose the last known version
        versions = cls.known_versions()
        if versions:
            return versions[-1]
        return fallback or "2025-01-01-preview"
