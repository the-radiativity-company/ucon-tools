# ucon/tools/mcp/ner/__init__.py
#
# NER training module for quantity extraction.

"""
NER training and evaluation for quantity extraction.

This module provides tools for training, evaluating, and managing
SpaCy NER models for extracting quantities from natural language text.

Example:
    >>> from ucon.tools.mcp.ner import TrainingDataset, DEFAULT_CONFIG
    >>> dataset = TrainingDataset.load("data/ner/training_v1.json")
    >>> train, val = dataset.split(ratio=0.2)

    >>> from ucon.tools.mcp.ner import normalize_unit_string
    >>> normalize_unit_string("mg per dose")
    'mg/ea'
"""

from ucon.tools.mcp.ner.config import EntityLabel, NERConfig, DEFAULT_CONFIG
from ucon.tools.mcp.ner.data import (
    TrainingExample,
    TrainingDataset,
    validate_example,
    validate_dataset,
)
from ucon.tools.mcp.ner.evaluation import (
    EntityMatch,
    EvaluationResult,
    evaluate,
    evaluate_model,
)
from ucon.tools.mcp.ner.unit_normalizer import (
    normalize_unit_string,
    parse_unit_structure,
    ParsedUnit,
    ComponentNormalizer,
    ComponentMapping,
    get_default_normalizer,
    add_component_mapping,
)

__all__ = [
    # Config
    "EntityLabel",
    "NERConfig",
    "DEFAULT_CONFIG",
    # Data
    "TrainingExample",
    "TrainingDataset",
    "validate_example",
    "validate_dataset",
    # Evaluation
    "EntityMatch",
    "EvaluationResult",
    "evaluate",
    "evaluate_model",
    # Unit normalization
    "normalize_unit_string",
    "parse_unit_structure",
    "ParsedUnit",
    "ComponentNormalizer",
    "ComponentMapping",
    "get_default_normalizer",
    "add_component_mapping",
]
