"""Tests for the RQ2 modality-contrast aggregate + static report figure (EX4).

TDD: these tests are written BEFORE the implementation.

Covers:
- compute_rq2_aggregate returns correct per-condition distributions
- fabrication shifts are computed correctly vs the FULL baseline
- clears_floor is True when shift > modality error_rate, False when <=
- text error floor governs CONTENT_ABSENT shift
- structure error floor governs KNOWLEDGE_ABSENT shift
- FULL_NO_EDIT_RERUN runs are EXCLUDED from the RQ2 contrast
- epistemic_level == INTERVENTIONAL_AGGREGATE
- zero-run condition does not crash
- make_rq2_figure returns a Figure with INTERVENTIONAL_AGGREGATE stamp
- figure has SE error bars, noise-floor marks, small-N caveat, STATUS palette
"""
from __future__ import annotations

import plotly.graph_objects as go

from ivg_kg.diagnostics import proportion_se
from ivg_kg.experiment.rq2_aggregate import (
    RQ2Aggregate,
    compute_rq2_aggregate,
    make_rq2_figure,
)
from ivg_kg.experiment.sweep import RunSet
from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    Condition,
    EpistemicLevel,
    GroundingPath,
    GroundingRun,
    SupportSource,
)

# ---------------------------------------------------------------------------
# Helpers: minimal GroundingRun builders
# ---------------------------------------------------------------------------


def _make_claim(cid: str, status: ClaimStatus) -> ClaimRecord:
    """Minimal ClaimRecord with no support path (sufficient for diagnostics)."""
    return ClaimRecord(
        claim_id=cid,
        text=f"claim {cid}",
        status=status,
        support_source=SupportSource.NONE if status == ClaimStatus.FABRICATED else SupportSource.DIRECT_TRIPLE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
    )


def _make_run(
    run_id: str,
    condition: Condition,
    statuses: list[ClaimStatus],
    question: str = "test question",
) -> GroundingRun:
    """Minimal GroundingRun with the given claim statuses."""
    claims = [_make_claim(f"c{i}", s) for i, s in enumerate(statuses)]
    return GroundingRun(
        run_id=run_id,
        question=question,
        answer_text="test answer",
        slice="books",
        phase="A",
        condition=condition,
        sample_index=0,
        claims=claims,
    )


# ---------------------------------------------------------------------------
# Synthetic reliability dict (mirrors the shape of reliability_report.json)
# ---------------------------------------------------------------------------

def _make_reliability(text_error: float, structure_error: float) -> dict:
    return {
        "per_modality_error": [
            {"modality": "text", "n": 10, "n_correct": 8, "error_rate": text_error},
            {"modality": "structure", "n": 10, "n_correct": 8, "error_rate": structure_error},
        ],
        "overall_error_rate": (text_error + structure_error) / 2,
        "frozen_tau": 0.5,
        "gate": "minicheck",
        "calibrated": True,
    }


# ---------------------------------------------------------------------------
# Synthetic RunSet fixture
# ---------------------------------------------------------------------------

def _build_runset(
    full_fab_frac: float = 0.2,
    content_fab_frac: float = 0.6,
    knowledge_fab_frac: float = 0.5,
    n: int = 5,
) -> RunSet:
    """
    Build a RunSet with controlled fabrication fractions per condition.

    Each run has exactly `n_claims` claims, with the given fraction FABRICATED
    and the rest RETRIEVED. The fractions must produce integer claim counts
    when multiplied by n_claims=5.
    """
    n_claims = 5

    def _fab_count(frac: float) -> int:
        return round(frac * n_claims)

    def _run_statuses(fab_count: int) -> list[ClaimStatus]:
        return [ClaimStatus.FABRICATED] * fab_count + [ClaimStatus.RETRIEVED] * (n_claims - fab_count)

    runs: list[GroundingRun] = []

    # FULL condition: n runs
    fab_full = _fab_count(full_fab_frac)
    for i in range(n):
        runs.append(_make_run(f"full-{i}", Condition.FULL, _run_statuses(fab_full)))

    # CONTENT_ABSENT condition: n runs
    fab_ca = _fab_count(content_fab_frac)
    for i in range(n):
        runs.append(_make_run(f"ca-{i}", Condition.CONTENT_ABSENT, _run_statuses(fab_ca)))

    # KNOWLEDGE_ABSENT condition: n runs
    fab_ka = _fab_count(knowledge_fab_frac)
    for i in range(n):
        runs.append(_make_run(f"ka-{i}", Condition.KNOWLEDGE_ABSENT, _run_statuses(fab_ka)))

    # FULL_NO_EDIT_RERUN runs (should be EXCLUDED from the RQ2 contrast)
    # Give them a very different fabrication fraction to detect if they leak in
    for i in range(n):
        runs.append(_make_run(f"no-edit-{i}", Condition.FULL_NO_EDIT_RERUN, [ClaimStatus.FABRICATED] * n_claims))

    return RunSet(
        sweep_id="test-sweep",
        slice_id="books-test",
        bank_id="test-bank",
        conditions=[Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT],
        n_runs=n,
        runs=runs,
    )


# ---------------------------------------------------------------------------
# Tests: compute_rq2_aggregate
# ---------------------------------------------------------------------------

class TestComputeRQ2Aggregate:

    def test_returns_rq2_aggregate_instance(self):
        runset = _build_runset()
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)
        assert isinstance(result, RQ2Aggregate)

    def test_epistemic_level_is_interventional(self):
        runset = _build_runset()
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)
        assert result.epistemic_level == EpistemicLevel.INTERVENTIONAL_AGGREGATE

    def test_per_condition_distributions_match_hand_computation(self):
        """All runs in a condition have identical fabrication fractions, so
        the mean per-run fraction equals that fraction exactly."""
        # 1 out of 5 claims fabricated = 0.2 fab fraction
        runset = _build_runset(full_fab_frac=0.2, content_fab_frac=0.6, knowledge_fab_frac=0.4, n=5)
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)

        fab_key = ClaimStatus.FABRICATED.value

        # FULL: 1/5 = 0.2
        full_diag = result.condition_diagnostics[Condition.FULL.value]
        assert abs(full_diag.status_distribution[fab_key].mean - 0.2) < 1e-9

        # CONTENT_ABSENT: 3/5 = 0.6
        ca_diag = result.condition_diagnostics[Condition.CONTENT_ABSENT.value]
        assert abs(ca_diag.status_distribution[fab_key].mean - 0.6) < 1e-9

        # KNOWLEDGE_ABSENT: 2/5 = 0.4
        ka_diag = result.condition_diagnostics[Condition.KNOWLEDGE_ABSENT.value]
        assert abs(ka_diag.status_distribution[fab_key].mean - 0.4) < 1e-9

    def test_fabrication_shifts_equal_hand_computed_deltas(self):
        runset = _build_runset(full_fab_frac=0.2, content_fab_frac=0.6, knowledge_fab_frac=0.4, n=5)
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)

        # content shift: 0.6 - 0.2 = 0.4
        assert abs(result.content_absent_shift.shift - 0.4) < 1e-9
        # knowledge shift: 0.4 - 0.2 = 0.2
        assert abs(result.knowledge_absent_shift.shift - 0.2) < 1e-9

    def test_clears_floor_true_when_shift_exceeds_error_rate(self):
        # shift = 0.4, text_error = 0.05 -> 0.4 > 0.05 -> True
        runset = _build_runset(full_fab_frac=0.2, content_fab_frac=0.6, n=5)
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)
        assert result.content_absent_shift.clears_floor is True

    def test_clears_floor_false_when_shift_at_or_below_error_rate(self):
        # shift = content 0.22 - 0.2 = 0.02, text_error = 0.05 -> 0.02 <= 0.05 -> False
        # use n_claims=5: 1/5=0.2 full, 1/5+eps ~ round to 1/5 too; need 0.22
        # Instead use 2/5=0.4 full, 2/5=0.4 content (zero shift) -> also False
        runset = _build_runset(full_fab_frac=0.4, content_fab_frac=0.4, knowledge_fab_frac=0.4, n=5)
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)
        # shift = 0.4 - 0.4 = 0.0 <= 0.05
        assert result.content_absent_shift.clears_floor is False

    def test_content_floor_uses_text_modality(self):
        runset = _build_runset(full_fab_frac=0.2, content_fab_frac=0.6, n=5)
        reliability = _make_reliability(text_error=0.07, structure_error=0.50)
        result = compute_rq2_aggregate(runset, reliability)
        assert abs(result.content_absent_shift.noise_floor - 0.07) < 1e-9

    def test_knowledge_floor_uses_structure_modality(self):
        runset = _build_runset(full_fab_frac=0.2, knowledge_fab_frac=0.6, n=5)
        reliability = _make_reliability(text_error=0.50, structure_error=0.09)
        result = compute_rq2_aggregate(runset, reliability)
        assert abs(result.knowledge_absent_shift.noise_floor - 0.09) < 1e-9

    def test_full_no_edit_rerun_excluded_from_contrast(self):
        """FULL_NO_EDIT_RERUN runs should not contaminate any condition's diagnostics."""
        runset = _build_runset(full_fab_frac=0.2, content_fab_frac=0.4, knowledge_fab_frac=0.4, n=5)
        # the FULL_NO_EDIT_RERUN runs have 100% fabrication; if they leaked into
        # FULL or any condition, the mean would be far above 0.2
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)

        fab_key = ClaimStatus.FABRICATED.value
        full_mean = result.condition_diagnostics[Condition.FULL.value].status_distribution[fab_key].mean
        # should be 0.2, not inflated toward 1.0
        assert full_mean < 0.5

    def test_zero_run_condition_does_not_crash_and_is_absent(self):
        """A RunSet with no KNOWLEDGE_ABSENT runs must not crash."""
        runs: list[GroundingRun] = []
        n = 5
        for i in range(n):
            runs.append(_make_run(f"full-{i}", Condition.FULL, [ClaimStatus.RETRIEVED] * 4 + [ClaimStatus.FABRICATED]))
        for i in range(n):
            runs.append(_make_run(f"ca-{i}", Condition.CONTENT_ABSENT, [ClaimStatus.FABRICATED] * 3 + [ClaimStatus.RETRIEVED] * 2))
        # no KNOWLEDGE_ABSENT runs at all
        runset = RunSet(
            sweep_id="test-sweep-partial",
            slice_id="books-test",
            bank_id="test-bank",
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=n,
            runs=runs,
        )
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)
        # knowledge shift should be absent / None (no runs)
        assert result.knowledge_absent_shift is None

    def test_full_baseline_mean_and_se_present(self):
        runset = _build_runset(full_fab_frac=0.2, n=5)
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        result = compute_rq2_aggregate(runset, reliability)

        # baseline mean stored separately
        assert abs(result.full_baseline_fab_mean - 0.2) < 1e-9
        # SE should equal proportion_se(0.2, 5)
        expected_se = proportion_se(0.2, 5)
        assert abs(result.full_baseline_fab_se - expected_se) < 1e-9

    def test_noise_floor_in_aggregate(self):
        """The aggregate stores the per-modality noise floor used."""
        reliability = _make_reliability(text_error=0.06, structure_error=0.10)
        runset = _build_runset()
        result = compute_rq2_aggregate(runset, reliability)
        assert abs(result.text_noise_floor - 0.06) < 1e-9
        assert abs(result.structure_noise_floor - 0.10) < 1e-9


# ---------------------------------------------------------------------------
# Tests: make_rq2_figure
# ---------------------------------------------------------------------------

class TestMakeRQ2Figure:

    def _make_agg(self) -> RQ2Aggregate:
        runset = _build_runset(full_fab_frac=0.2, content_fab_frac=0.6, knowledge_fab_frac=0.4, n=5)
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        return compute_rq2_aggregate(runset, reliability)

    def test_returns_plotly_figure(self):
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        assert isinstance(fig, go.Figure)

    def test_figure_has_interventional_aggregate_stamp(self):
        """The INTERVENTIONAL_AGGREGATE stamp must appear in the figure."""
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        # Check title or annotations contain the stamp
        fig_json = fig.to_json()
        assert "interventional" in fig_json.lower() or "INTERVENTIONAL" in fig_json

    def test_figure_has_small_n_caveat(self):
        """A small-N caveat annotation must be present."""
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        fig_json = fig.to_json()
        # Should mention SE formula or N floor
        assert "n=" in fig_json.lower() or "small" in fig_json.lower() or "floor" in fig_json.lower()

    def test_figure_uses_status_palette_for_status_series(self):
        """Each status trace uses the STATUS_COLORS hex value."""
        from app.theme import STATUS_COLORS
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        fig_json = fig.to_json()
        # at least one status color hex should appear in the figure JSON
        any_color = any(c.lstrip("#").lower() in fig_json.lower() for c in STATUS_COLORS.values())
        assert any_color, "No STATUS_COLORS hex found in figure JSON"

    def test_figure_has_error_bars(self):
        """Error bars (SE interval) must be present in the figure."""
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        # At least one Bar trace should have error_y visible
        has_error_y = any(
            getattr(trace, "error_y", None) is not None
            and getattr(trace.error_y, "visible", False)
            for trace in fig.data
        )
        assert has_error_y, "No visible error_y found in figure traces"

    def test_figure_has_noise_floor_annotation_or_shape(self):
        """The noise floor must be represented (shape or annotation)."""
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        fig_json = fig.to_json()
        # noise floor presence: either a shape (line/rect) or annotation with 'noise' or 'floor'
        has_shapes = len(fig.layout.shapes or []) > 0
        has_noise_text = "noise" in fig_json.lower() or "floor" in fig_json.lower()
        assert has_shapes or has_noise_text, "No noise floor shape or annotation found"

    def test_bars_start_at_zero(self):
        """Y-axis range mode must include zero (rangemode or explicit range)."""
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        yaxis = fig.layout.yaxis
        # either rangemode=tozero or range starts at 0
        rangemode_ok = getattr(yaxis, "rangemode", None) == "tozero"
        range_ok = (
            yaxis.range is not None
            and len(yaxis.range) == 2
            and yaxis.range[0] == 0
        )
        assert rangemode_ok or range_ok, "Y-axis does not start at 0"

    def test_knowledge_absent_labeled_as_control(self):
        """The knowledge-withheld condition must be labeled as control."""
        agg = self._make_agg()
        fig = make_rq2_figure(agg)
        fig_json = fig.to_json()
        assert "control" in fig_json.lower() or "hard-entity" in fig_json.lower() or "knowledge" in fig_json.lower()

    def test_no_crash_when_knowledge_absent_is_none(self):
        """make_rq2_figure must not crash when knowledge_absent_shift is None."""
        runs: list[GroundingRun] = []
        n = 5
        for i in range(n):
            runs.append(_make_run(f"full-{i}", Condition.FULL, [ClaimStatus.RETRIEVED] * 4 + [ClaimStatus.FABRICATED]))
        for i in range(n):
            runs.append(_make_run(f"ca-{i}", Condition.CONTENT_ABSENT, [ClaimStatus.FABRICATED] * 3 + [ClaimStatus.RETRIEVED] * 2))
        runset = RunSet(
            sweep_id="partial",
            slice_id="books-test",
            bank_id="test-bank",
            conditions=[Condition.FULL, Condition.CONTENT_ABSENT],
            n_runs=n,
            runs=runs,
        )
        reliability = _make_reliability(text_error=0.05, structure_error=0.08)
        agg = compute_rq2_aggregate(runset, reliability)
        fig = make_rq2_figure(agg)
        assert isinstance(fig, go.Figure)
