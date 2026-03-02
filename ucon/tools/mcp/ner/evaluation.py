# ucon/tools/mcp/ner/evaluation.py
#
# Evaluation metrics for NER model performance.

"""
Evaluation utilities for NER model.

This module provides precision, recall, and F1 scoring for evaluating
the performance of the trained quantity extraction NER model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityMatch:
    """Represents a match between predicted and gold entities.

    Attributes:
        predicted: The predicted entity span (start, end, label) or None.
        gold: The gold entity span (start, end, label) or None.
        match_type: Type of match ('exact', 'partial', 'spurious', 'missing').
    """
    predicted: tuple[int, int, str] | None
    gold: tuple[int, int, str] | None
    match_type: str


@dataclass
class EvaluationResult:
    """Results of evaluating NER model performance.

    Attributes:
        precision: Precision score (true positives / predicted positives).
        recall: Recall score (true positives / actual positives).
        f1: F1 score (harmonic mean of precision and recall).
        true_positives: Number of correctly predicted entities.
        false_positives: Number of spurious predictions.
        false_negatives: Number of missed entities.
        total_examples: Number of examples evaluated.
        per_label_scores: Scores broken down by entity label.
    """
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    total_examples: int
    per_label_scores: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "total_examples": self.total_examples,
            "per_label_scores": self.per_label_scores,
        }

    def __str__(self) -> str:
        lines = [
            f"Precision: {self.precision:.3f}",
            f"Recall:    {self.recall:.3f}",
            f"F1:        {self.f1:.3f}",
            f"",
            f"TP: {self.true_positives}, FP: {self.false_positives}, FN: {self.false_negatives}",
            f"Examples: {self.total_examples}",
        ]

        if self.per_label_scores:
            lines.append("")
            lines.append("Per-label scores:")
            for label, scores in self.per_label_scores.items():
                lines.append(
                    f"  {label}: P={scores['precision']:.3f} "
                    f"R={scores['recall']:.3f} F1={scores['f1']:.3f}"
                )

        return "\n".join(lines)


def _spans_match(
    pred: tuple[int, int, str],
    gold: tuple[int, int, str],
    mode: str = "exact",
) -> bool:
    """Check if predicted and gold spans match.

    Args:
        pred: Predicted span (start, end, label).
        gold: Gold span (start, end, label).
        mode: Matching mode ('exact' or 'partial').

    Returns:
        True if spans match according to the mode.
    """
    p_start, p_end, p_label = pred
    g_start, g_end, g_label = gold

    if p_label != g_label:
        return False

    if mode == "exact":
        return p_start == g_start and p_end == g_end

    elif mode == "partial":
        # Check for any overlap
        return p_start < g_end and p_end > g_start

    return False


def evaluate(
    predictions: list[list[tuple[int, int, str]]],
    gold: list[list[tuple[int, int, str]]],
    mode: str = "exact",
) -> EvaluationResult:
    """Evaluate NER predictions against gold annotations.

    Args:
        predictions: List of predicted entity lists, one per example.
        gold: List of gold entity lists, one per example.
        mode: Matching mode ('exact' or 'partial').

    Returns:
        EvaluationResult with precision, recall, and F1 scores.

    Raises:
        ValueError: If predictions and gold have different lengths.
    """
    if len(predictions) != len(gold):
        raise ValueError(
            f"Predictions ({len(predictions)}) and gold ({len(gold)}) "
            "must have the same length"
        )

    total_tp = 0
    total_fp = 0
    total_fn = 0

    # Per-label counters
    label_tp: dict[str, int] = {}
    label_fp: dict[str, int] = {}
    label_fn: dict[str, int] = {}

    for preds, golds in zip(predictions, gold):
        # Track which gold entities have been matched
        matched_gold = set()

        for pred in preds:
            _, _, p_label = pred
            matched = False

            for i, g in enumerate(golds):
                if i in matched_gold:
                    continue

                if _spans_match(pred, g, mode):
                    matched = True
                    matched_gold.add(i)
                    total_tp += 1
                    label_tp[p_label] = label_tp.get(p_label, 0) + 1
                    break

            if not matched:
                total_fp += 1
                label_fp[p_label] = label_fp.get(p_label, 0) + 1

        # Unmatched gold entities are false negatives
        for i, g in enumerate(golds):
            if i not in matched_gold:
                _, _, g_label = g
                total_fn += 1
                label_fn[g_label] = label_fn.get(g_label, 0) + 1

    # Calculate scores
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Per-label scores
    all_labels = set(label_tp.keys()) | set(label_fp.keys()) | set(label_fn.keys())
    per_label_scores = {}

    for label in all_labels:
        tp = label_tp.get(label, 0)
        fp = label_fp.get(label, 0)
        fn = label_fn.get(label, 0)

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

        per_label_scores[label] = {
            "precision": p,
            "recall": r,
            "f1": f,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
        }

    return EvaluationResult(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        total_examples=len(predictions),
        per_label_scores=per_label_scores,
    )


def evaluate_model(
    nlp,
    examples: list[tuple[str, dict[str, Any]]],
    mode: str = "exact",
) -> EvaluationResult:
    """Evaluate a SpaCy NER model on a list of examples.

    Args:
        nlp: SpaCy NLP pipeline with NER component.
        examples: List of (text, {"entities": [...]}) tuples.
        mode: Matching mode ('exact' or 'partial').

    Returns:
        EvaluationResult with precision, recall, and F1 scores.
    """
    predictions = []
    gold = []

    for text, annotations in examples:
        doc = nlp(text)
        pred_entities = [
            (ent.start_char, ent.end_char, ent.label_)
            for ent in doc.ents
        ]
        predictions.append(pred_entities)

        gold_entities = [tuple(e) for e in annotations.get("entities", [])]
        gold.append(gold_entities)

    return evaluate(predictions, gold, mode)
