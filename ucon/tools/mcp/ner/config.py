# ucon/tools/mcp/ner/config.py
#
# Configuration for NER model training and entity labels.

"""
NER configuration for quantity extraction.

This module defines entity labels and training configuration for the
SpaCy NER model used to extract quantities from natural language text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class EntityLabel(Enum):
    """Entity labels for NER training.

    Currently supports QUANTITY for numeric values with units.
    Reserved labels (RATE, CONVERSION_FACTOR) can be added in future versions.
    """
    QUANTITY = "QUANTITY"
    # Reserved for future:
    # RATE = "RATE"
    # CONVERSION_FACTOR = "CONVERSION_FACTOR"


@dataclass(frozen=True)
class NERConfig:
    """Configuration for NER model training.

    Attributes:
        model_name: Name for the trained model.
        base_model: SpaCy base model to start from.
        entity_labels: Tuple of entity label names to train.
        n_iter: Number of training iterations.
        batch_size: Batch size for training.
        dropout: Dropout rate during training.
        model_path: Path to save/load the trained model.
        validation_split: Fraction of data to use for validation.
    """
    model_name: str = "quantity_ner"
    base_model: str = "en_core_web_sm"
    entity_labels: tuple[str, ...] = (EntityLabel.QUANTITY.value,)
    n_iter: int = 30
    batch_size: int = 8
    dropout: float = 0.3
    model_path: str = "models/quantity_ner"
    validation_split: float = 0.2

    def get_model_dir(self, base_dir: Path | None = None) -> Path:
        """Get the full path to the model directory.

        Args:
            base_dir: Base directory for models. If None, uses
                      ucon/mcp/models as the base.

        Returns:
            Path to the model directory.
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "models"
        return base_dir / self.model_name


DEFAULT_CONFIG = NERConfig()
