# ============================================================================
# utils/api_version.py
# ============================================================================
"""API version management utilities."""

from __future__ import annotations


class APIVersionManager:
    """Manager for API version compatibility."""

    # Known versions with metadata
    _KNOWN_VERSIONS = {
        "2024-10-01-preview": {"since": (2024, 10, 1)},
        "2025-01-01-preview": {"since": (2025, 1, 1)},
        "2025-03-01-preview": {"since": (2025, 3, 1), "responses_min": True},
    }

    @classmethod
    def known_versions(cls) -> list[str]:
        """Get list of known API versions, sorted by date."""
        return sorted(
            cls._KNOWN_VERSIONS.keys(),
            key=lambda v: cls._KNOWN_VERSIONS[v]["since"],
        )

    @classmethod
    def best_for_model(cls, model: str | None) -> str:
        """
        Get best API version for a model.

        Args:
            model: Model name

        Returns:
            Recommended API version
        """
        model_lower = (model or "").lower()

        # Reasoning models (o-series) need Responses API
        if model_lower.startswith("o"):
            return "2025-03-01-preview"

        # Default to latest known
        versions = cls.known_versions()
        return versions[-1] if versions else "2025-03-01-preview"

    @classmethod
    def ensure_min(cls, version: str, minimum: str) -> str:
        """
        Ensure version is at least minimum.

        Args:
            version: Current version
            minimum: Minimum required version

        Returns:
            version if >= minimum, else minimum
        """

        def parse(v: str) -> tuple[int, int, int]:
            parts = v.split("-")[0].split(".")
            try:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                return (1900, 1, 1)

        v_tuple = parse(version)
        m_tuple = parse(minimum)

        return version if v_tuple >= m_tuple else minimum
