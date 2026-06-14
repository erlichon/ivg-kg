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
RunSet              -- all runs produced by one offline sweep (SPEC sec 4.8)
run_sweep           -- GR11 offline precompute sweep harness
sweep_seed          -- deterministic per-draw seed scheme
default_perturbations_for -- books-spine condition -> perturbation mapping
write_runset        -- write RunSet runs to data/runs/
manifest_perturbations_for -- EX2 manifest-driven condition -> perturbation adapter
"""

from ivg_kg.experiment.ablation import manifest_perturbations_for
from ivg_kg.experiment.gold_qa import GoldQAItem, GoldQASet, load_gold_qa_set
from ivg_kg.experiment.question_bank import (
    QuestionBank,
    QuestionBankItem,
    load_question_bank,
)
from ivg_kg.experiment.sweep import (
    RunSet,
    default_perturbations_for,
    run_sweep,
    sweep_seed,
    write_runset,
)

__all__ = [
    "GoldQAItem",
    "GoldQASet",
    "QuestionBank",
    "QuestionBankItem",
    "load_gold_qa_set",
    "load_question_bank",
    "RunSet",
    "default_perturbations_for",
    "manifest_perturbations_for",
    "run_sweep",
    "sweep_seed",
    "write_runset",
]
