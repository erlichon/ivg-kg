"""
ivg_kg.experiment -- Experiment-stream seam formats (SPEC-text §4.7, §5, §4.4).

These are authoring/evaluation artifacts owned by the data/experiments stream.
They import FROM ivg_kg.schema; they never modify it.

Public API
----------
GoldQAItem          -- a single calibration/RQ2 anchor item (SPEC §4.7 / GR10)
GoldQASet           -- a validated collection of GoldQAItems
load_gold_qa_set    -- load from a JSON file path and validate
QuestionBankItem    -- a single fixed-bank question (SPEC §5 / EX1)
QuestionBank        -- a validated collection of QuestionBankItems
load_question_bank  -- load from a JSON file path and validate
"""

from ivg_kg.experiment.gold_qa import GoldQAItem, GoldQASet, load_gold_qa_set
from ivg_kg.experiment.question_bank import (
    QuestionBank,
    QuestionBankItem,
    load_question_bank,
)

__all__ = [
    "GoldQAItem",
    "GoldQASet",
    "QuestionBank",
    "QuestionBankItem",
    "load_gold_qa_set",
    "load_question_bank",
]
