# ucon/tools/mcp/ner/unit_normalizer.py
#
# Unit string normalization using structure parsing + learned component mapping.

"""
Unit string normalization for natural language unit descriptions.

This module normalizes natural language unit strings (e.g., "mg per dose")
to canonical unit syntax (e.g., "mg/ea") using:

1. Structure parsing (regex): Identifies patterns like "X per Y" → "X/Y"
2. Component normalization (learned): Maps unit words to canonical forms

Example:
    >>> from ucon.tools.mcp.ner.unit_normalizer import normalize_unit_string
    >>> normalize_unit_string("mg per dose")
    'mg/ea'
    >>> normalize_unit_string("milligrams per hour")
    'mg/h'
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# -----------------------------------------------------------------------------
# Structure Parser (rule-based)
# -----------------------------------------------------------------------------

@dataclass
class ParsedUnit:
    """Result of parsing a unit string structure."""
    components: list[str]
    operators: list[str]  # '/' or '*' between components
    original: str

    def reconstruct(self, normalized_components: list[str]) -> str:
        """Reconstruct unit string with normalized components."""
        if not normalized_components:
            return self.original

        result = normalized_components[0]
        for i, op in enumerate(self.operators):
            if i + 1 < len(normalized_components):
                result += op + normalized_components[i + 1]
        return result


# Patterns for structure parsing
_STRUCTURE_PATTERNS = [
    # "X per Y" → X/Y
    (re.compile(r'^(.+?)\s+per\s+(.+)$', re.IGNORECASE), '/'),
    # "X a Y" (e.g., "mg a day") → X/Y
    (re.compile(r'^(.+?)\s+a\s+(day|hour|minute|second|week)$', re.IGNORECASE), '/'),
    # "X every Y" → X/Y
    (re.compile(r'^(.+?)\s+every\s+(.+)$', re.IGNORECASE), '/'),
]


def parse_unit_structure(unit_str: str) -> ParsedUnit:
    """Parse the structure of a unit string.

    Identifies components and operators without normalizing the components.

    Args:
        unit_str: Natural language or formal unit string.

    Returns:
        ParsedUnit with components and operators.

    Example:
        >>> parse_unit_structure("mg per dose")
        ParsedUnit(components=['mg', 'dose'], operators=['/'], original='mg per dose')
        >>> parse_unit_structure("kg*m/s^2")
        ParsedUnit(components=['kg', 'm', 's^2'], operators=['*', '/'], original='kg*m/s^2')
    """
    unit_str = unit_str.strip()

    # Try natural language patterns first
    for pattern, operator in _STRUCTURE_PATTERNS:
        match = pattern.match(unit_str)
        if match:
            components = [g.strip() for g in match.groups()]
            return ParsedUnit(
                components=components,
                operators=[operator],
                original=unit_str,
            )

    # Parse formal unit syntax (contains / or *)
    if '/' in unit_str or '*' in unit_str:
        # Split preserving operators
        parts = re.split(r'([/*])', unit_str)
        components = []
        operators = []

        for part in parts:
            part = part.strip()
            if part in '/*':
                operators.append(part)
            elif part:
                components.append(part)

        return ParsedUnit(
            components=components,
            operators=operators,
            original=unit_str,
        )

    # Single component
    return ParsedUnit(
        components=[unit_str],
        operators=[],
        original=unit_str,
    )


# -----------------------------------------------------------------------------
# Component Normalizer (learned)
# -----------------------------------------------------------------------------

@dataclass
class ComponentMapping:
    """A mapping from variant to canonical unit component."""
    variant: str      # e.g., "milligrams", "dose", "hrs"
    canonical: str    # e.g., "mg", "ea", "h"
    category: str = "general"  # e.g., "mass", "time", "count"


@dataclass
class ComponentNormalizer:
    """Learned normalizer for unit components.

    Maps natural language unit words to canonical abbreviations.
    Can be trained from examples and saved/loaded.
    """
    mappings: dict[str, str] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)

    def normalize(self, component: str) -> str:
        """Normalize a single unit component.

        Args:
            component: Unit word or abbreviation.

        Returns:
            Canonical form if known, otherwise original.
        """
        # Check exact match (case-insensitive)
        lower = component.lower().strip()
        if lower in self.mappings:
            return self.mappings[lower]

        # Check if already canonical (return as-is)
        # This handles cases like "mg", "kg", "L" that don't need normalization
        return component

    def add_mapping(self, variant: str, canonical: str, category: str = "general") -> None:
        """Add a mapping from variant to canonical form."""
        self.mappings[variant.lower()] = canonical
        self.categories[variant.lower()] = category

    def add_mappings(self, mappings: list[ComponentMapping]) -> None:
        """Add multiple mappings."""
        for m in mappings:
            self.add_mapping(m.variant, m.canonical, m.category)

    @classmethod
    def load(cls, path: Path | str) -> "ComponentNormalizer":
        """Load normalizer from JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        normalizer = cls()
        for entry in data.get("mappings", []):
            normalizer.add_mapping(
                entry["variant"],
                entry["canonical"],
                entry.get("category", "general"),
            )
        return normalizer

    def save(self, path: Path | str) -> None:
        """Save normalizer to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        mappings = [
            {
                "variant": variant,
                "canonical": canonical,
                "category": self.categories.get(variant, "general"),
            }
            for variant, canonical in self.mappings.items()
        ]

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mappings": mappings}, f, indent=2)

    def __len__(self) -> int:
        return len(self.mappings)


# -----------------------------------------------------------------------------
# Default Component Mappings
# -----------------------------------------------------------------------------

_DEFAULT_MAPPINGS = [
    # Mass
    ComponentMapping("micrograms", "mcg", "mass"),
    ComponentMapping("microgram", "mcg", "mass"),
    ComponentMapping("mcg", "mcg", "mass"),
    ComponentMapping("µg", "mcg", "mass"),
    ComponentMapping("ug", "mcg", "mass"),
    ComponentMapping("milligrams", "mg", "mass"),
    ComponentMapping("milligram", "mg", "mass"),
    ComponentMapping("grams", "g", "mass"),
    ComponentMapping("gram", "g", "mass"),
    ComponentMapping("kilograms", "kg", "mass"),
    ComponentMapping("kilogram", "kg", "mass"),
    ComponentMapping("pounds", "lb", "mass"),
    ComponentMapping("pound", "lb", "mass"),
    ComponentMapping("lbs", "lb", "mass"),
    ComponentMapping("ounces", "oz", "mass"),
    ComponentMapping("ounce", "oz", "mass"),

    # Volume
    ComponentMapping("microliters", "uL", "volume"),
    ComponentMapping("microliter", "uL", "volume"),
    ComponentMapping("milliliters", "mL", "volume"),
    ComponentMapping("milliliter", "mL", "volume"),
    ComponentMapping("liters", "L", "volume"),
    ComponentMapping("liter", "L", "volume"),
    ComponentMapping("litres", "L", "volume"),
    ComponentMapping("litre", "L", "volume"),
    ComponentMapping("gallons", "gal", "volume"),
    ComponentMapping("gallon", "gal", "volume"),

    # Time
    ComponentMapping("hours", "h", "time"),
    ComponentMapping("hour", "h", "time"),
    ComponentMapping("hr", "h", "time"),
    ComponentMapping("hrs", "h", "time"),
    ComponentMapping("minutes", "min", "time"),
    ComponentMapping("minute", "min", "time"),
    ComponentMapping("mins", "min", "time"),
    ComponentMapping("seconds", "s", "time"),
    ComponentMapping("second", "s", "time"),
    ComponentMapping("sec", "s", "time"),
    ComponentMapping("secs", "s", "time"),
    ComponentMapping("days", "day", "time"),
    ComponentMapping("daily", "day", "time"),
    ComponentMapping("weeks", "week", "time"),
    ComponentMapping("weekly", "week", "time"),

    # Count/Dosing
    ComponentMapping("doses", "ea", "count"),
    ComponentMapping("dose", "ea", "count"),
    ComponentMapping("dosage", "ea", "count"),
    ComponentMapping("tablets", "ea", "count"),
    ComponentMapping("tablet", "ea", "count"),
    ComponentMapping("tabs", "ea", "count"),
    ComponentMapping("tab", "ea", "count"),
    ComponentMapping("capsules", "ea", "count"),
    ComponentMapping("capsule", "ea", "count"),
    ComponentMapping("caps", "ea", "count"),
    ComponentMapping("cap", "ea", "count"),
    ComponentMapping("pills", "ea", "count"),
    ComponentMapping("pill", "ea", "count"),
    ComponentMapping("drops", "gtt", "count"),
    ComponentMapping("drop", "gtt", "count"),
    ComponentMapping("units", "unit", "count"),
    ComponentMapping("iu", "IU", "count"),

    # Length
    ComponentMapping("meters", "m", "length"),
    ComponentMapping("meter", "m", "length"),
    ComponentMapping("metres", "m", "length"),
    ComponentMapping("metre", "m", "length"),
    ComponentMapping("kilometers", "km", "length"),
    ComponentMapping("kilometer", "km", "length"),
    ComponentMapping("centimeters", "cm", "length"),
    ComponentMapping("centimeter", "cm", "length"),
    ComponentMapping("millimeters", "mm", "length"),
    ComponentMapping("millimeter", "mm", "length"),
    ComponentMapping("feet", "ft", "length"),
    ComponentMapping("foot", "ft", "length"),
    ComponentMapping("inches", "in", "length"),
    ComponentMapping("inch", "in", "length"),
    ComponentMapping("miles", "mi", "length"),
    ComponentMapping("mile", "mi", "length"),

    # Pressure
    ComponentMapping("pascals", "Pa", "pressure"),
    ComponentMapping("pascal", "Pa", "pressure"),
    ComponentMapping("kilopascals", "kPa", "pressure"),
    ComponentMapping("kilopascal", "kPa", "pressure"),
]


def get_default_normalizer() -> ComponentNormalizer:
    """Get the default component normalizer with built-in mappings."""
    normalizer = ComponentNormalizer()
    normalizer.add_mappings(_DEFAULT_MAPPINGS)
    return normalizer


# Module-level default normalizer (lazy loaded)
_default_normalizer: ComponentNormalizer | None = None


def _get_normalizer() -> ComponentNormalizer:
    """Get or create the default normalizer."""
    global _default_normalizer
    if _default_normalizer is None:
        # Try to load custom mappings if they exist
        custom_path = Path(__file__).parent.parent / "models" / "component_mappings.json"
        if custom_path.exists():
            _default_normalizer = ComponentNormalizer.load(custom_path)
            # Merge with defaults (custom takes precedence)
            default = get_default_normalizer()
            for variant, canonical in default.mappings.items():
                if variant not in _default_normalizer.mappings:
                    _default_normalizer.mappings[variant] = canonical
        else:
            _default_normalizer = get_default_normalizer()
    return _default_normalizer


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def normalize_unit_string(unit_str: str, normalizer: ComponentNormalizer | None = None) -> str:
    """Normalize a natural language unit string to canonical form.

    Uses structure parsing to identify components and operators,
    then normalizes each component using the learned normalizer.

    Args:
        unit_str: Natural language unit string (e.g., "mg per dose").
        normalizer: Optional custom normalizer. Uses default if not provided.

    Returns:
        Normalized unit string (e.g., "mg/ea").

    Example:
        >>> normalize_unit_string("mg per dose")
        'mg/ea'
        >>> normalize_unit_string("milligrams per hour")
        'mg/h'
        >>> normalize_unit_string("L/min")
        'L/min'
    """
    if not unit_str:
        return unit_str

    if normalizer is None:
        normalizer = _get_normalizer()

    # Parse structure
    parsed = parse_unit_structure(unit_str)

    # Normalize each component
    normalized_components = [
        normalizer.normalize(comp) for comp in parsed.components
    ]

    # Reconstruct
    return parsed.reconstruct(normalized_components)


def add_component_mapping(variant: str, canonical: str, category: str = "general") -> None:
    """Add a custom component mapping to the default normalizer.

    This allows runtime extension of the normalizer without retraining.

    Args:
        variant: The variant form (e.g., "dosage").
        canonical: The canonical form (e.g., "ea").
        category: Optional category for organization.
    """
    normalizer = _get_normalizer()
    normalizer.add_mapping(variant, canonical, category)
