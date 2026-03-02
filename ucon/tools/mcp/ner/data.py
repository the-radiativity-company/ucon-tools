# ucon/tools/mcp/ner/data.py
#
# Training data loading, validation, and dataset management.

"""
Training data management for NER model.

This module provides dataclasses and utilities for loading, validating,
and splitting training data for the quantity extraction NER model.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ucon.tools.mcp.ner.config import EntityLabel


@dataclass
class TrainingExample:
    """A single training example for NER.

    Attributes:
        text: The input text containing quantities.
        entities: List of (start, end, label) tuples marking entity spans.
        domain: Optional domain tag (e.g., 'medical', 'physics').
    """
    text: str
    entities: list[tuple[int, int, str]]
    domain: str = "general"

    def to_spacy_format(self) -> tuple[str, dict[str, Any]]:
        """Convert to SpaCy training format.

        Returns:
            Tuple of (text, {"entities": [(start, end, label), ...]}).
        """
        return (self.text, {"entities": self.entities})

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TrainingExample":
        """Create from dictionary representation.

        Args:
            d: Dictionary with 'text', 'entities', and optional 'domain'.

        Returns:
            TrainingExample instance.
        """
        return cls(
            text=d["text"],
            entities=[tuple(e) for e in d["entities"]],
            domain=d.get("domain", "general"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with 'text', 'entities', and 'domain'.
        """
        return {
            "text": self.text,
            "entities": [list(e) for e in self.entities],
            "domain": self.domain,
        }


@dataclass
class TrainingDataset:
    """A collection of training examples.

    Attributes:
        version: Dataset version string.
        entity_labels: List of entity labels used in this dataset.
        examples: List of training examples.
    """
    version: str
    entity_labels: list[str]
    examples: list[TrainingExample]

    @classmethod
    def load(cls, path: Path | str) -> "TrainingDataset":
        """Load dataset from a JSON file.

        Args:
            path: Path to JSON file with training data.

        Returns:
            TrainingDataset instance.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Training data must be a JSON object")

        required_fields = ["version", "entity_labels", "examples"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")

        examples = [TrainingExample.from_dict(ex) for ex in data["examples"]]

        return cls(
            version=data["version"],
            entity_labels=data["entity_labels"],
            examples=examples,
        )

    def save(self, path: Path | str) -> None:
        """Save dataset to a JSON file.

        Args:
            path: Path to save the JSON file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.version,
            "entity_labels": self.entity_labels,
            "examples": [ex.to_dict() for ex in self.examples],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def split(
        self,
        ratio: float = 0.2,
        seed: int | None = None,
    ) -> tuple["TrainingDataset", "TrainingDataset"]:
        """Split dataset into training and validation sets.

        Args:
            ratio: Fraction of data to use for validation.
            seed: Random seed for reproducibility.

        Returns:
            Tuple of (training_dataset, validation_dataset).
        """
        if seed is not None:
            random.seed(seed)

        examples = list(self.examples)
        random.shuffle(examples)

        split_idx = int(len(examples) * (1 - ratio))
        train_examples = examples[:split_idx]
        val_examples = examples[split_idx:]

        train_dataset = TrainingDataset(
            version=self.version,
            entity_labels=self.entity_labels,
            examples=train_examples,
        )
        val_dataset = TrainingDataset(
            version=self.version,
            entity_labels=self.entity_labels,
            examples=val_examples,
        )

        return train_dataset, val_dataset

    def filter_by_domain(self, domain: str) -> "TrainingDataset":
        """Filter examples by domain.

        Args:
            domain: Domain to filter by.

        Returns:
            New dataset with only examples from the specified domain.
        """
        filtered = [ex for ex in self.examples if ex.domain == domain]
        return TrainingDataset(
            version=self.version,
            entity_labels=self.entity_labels,
            examples=filtered,
        )

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self):
        return iter(self.examples)


def validate_example(example: dict[str, Any]) -> list[str]:
    """Validate a single training example.

    Checks:
    - Required fields exist (text, entities)
    - Text is non-empty string
    - Entities have valid format [(start, end, label), ...]
    - Entity spans are within text bounds
    - Entity spans don't overlap
    - Labels are valid EntityLabel values

    Args:
        example: Dictionary with training example data.

    Returns:
        List of validation issues (empty if valid).
    """
    issues = []

    # Check required fields
    if "text" not in example:
        issues.append("Missing 'text' field")
        return issues

    if "entities" not in example:
        issues.append("Missing 'entities' field")
        return issues

    text = example["text"]
    entities = example["entities"]

    # Validate text
    if not isinstance(text, str):
        issues.append("'text' must be a string")
        return issues

    if len(text) == 0:
        issues.append("'text' is empty")

    # Validate entities
    if not isinstance(entities, list):
        issues.append("'entities' must be a list")
        return issues

    valid_labels = {e.value for e in EntityLabel}
    spans = []

    for i, ent in enumerate(entities):
        if not isinstance(ent, (list, tuple)):
            issues.append(f"Entity {i}: must be a list/tuple [start, end, label]")
            continue

        if len(ent) != 3:
            issues.append(f"Entity {i}: must have exactly 3 elements [start, end, label]")
            continue

        start, end, label = ent

        # Validate types
        if not isinstance(start, int) or not isinstance(end, int):
            issues.append(f"Entity {i}: start and end must be integers")
            continue

        if not isinstance(label, str):
            issues.append(f"Entity {i}: label must be a string")
            continue

        # Validate bounds
        if start < 0:
            issues.append(f"Entity {i}: start ({start}) is negative")

        if end > len(text):
            issues.append(f"Entity {i}: end ({end}) exceeds text length ({len(text)})")

        if start >= end:
            issues.append(f"Entity {i}: start ({start}) >= end ({end})")

        # Validate label
        if label not in valid_labels:
            issues.append(f"Entity {i}: unknown label '{label}' (valid: {valid_labels})")

        spans.append((start, end, i))

    # Check for overlapping spans
    spans.sort()
    for i in range(len(spans) - 1):
        _, end1, idx1 = spans[i]
        start2, _, idx2 = spans[i + 1]
        if end1 > start2:
            issues.append(f"Entities {idx1} and {idx2} overlap")

    return issues


def validate_dataset(dataset: TrainingDataset) -> dict[str, Any]:
    """Validate an entire dataset.

    Args:
        dataset: TrainingDataset to validate.

    Returns:
        Dictionary with validation results:
        - valid_count: Number of valid examples
        - invalid_count: Number of invalid examples
        - issues: List of (index, issues) tuples for invalid examples
    """
    valid_count = 0
    invalid_count = 0
    all_issues = []

    for i, example in enumerate(dataset.examples):
        issues = validate_example(example.to_dict())
        if issues:
            invalid_count += 1
            all_issues.append((i, issues))
        else:
            valid_count += 1

    return {
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "issues": all_issues,
    }
