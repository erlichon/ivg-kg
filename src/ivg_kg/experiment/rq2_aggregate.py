"""EX4: RQ2 modality-contrast aggregate + static report figure (SPEC-text sec 8 / 10 / 4.8).

The RQ2 modality-contrast aggregate is the claim-status distribution shift across the
three sweep conditions {full, content-absent, knowledge-absent}, with:

- per-condition answer-level mean+SE (from aggregate_runset, per-condition)
- fabrication shifts vs the FULL baseline
- per-modality noise floor: the gate's own error_rate from the reliability report
  (text floor governs CONTENT_ABSENT shift; structure floor governs KNOWLEDGE_ABSENT)
- clears_floor: shift > noise_floor boolean
- HARD-ENTITY control: KNOWLEDGE_ABSENT is labeled as the intrinsic-difficulty control
- FULL_NO_EDIT_RERUN runs are EXCLUDED from the RQ2 contrast (they are EX3's baseline)

This module is PURE (no file I/O). Use load_reliability_report for the script layer.

Epistemic glyph contract (Invariant #20): the offline-sweep aggregate stamps
EpistemicLevel.INTERVENTIONAL_AGGREGATE on the figure (filled triangle + interval).
DO NOT import from app/ (UI6 layer) -- this is science-side.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from pydantic import BaseModel

from ivg_kg.diagnostics import aggregate_runset
from ivg_kg.experiment.sweep import RunSet
from ivg_kg.schema import (
    AnswerDiagnostics,
    ClaimStatus,
    Condition,
    EpistemicLevel,
)

__all__ = [
    "FabricationShift",
    "RQ2Aggregate",
    "compute_rq2_aggregate",
    "make_rq2_figure",
    "save_rq2_figure",
    "load_reliability_report",
]

# The three RQ2 conditions (FULL_NO_EDIT_RERUN is EX3, excluded from RQ2).
_RQ2_CONDITIONS = frozenset({
    Condition.FULL,
    Condition.CONTENT_ABSENT,
    Condition.KNOWLEDGE_ABSENT,
})

_FAB = ClaimStatus.FABRICATED.value


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class FabricationShift(BaseModel):
    """Fabrication fraction shift from FULL baseline under one condition.

    shift     = condition_fab_mean - full_baseline_fab_mean (positive = more fab)
    noise_floor = the relevant gate modality error_rate (text or structure)
    clears_floor = shift > noise_floor (a shift is only real when it clears the gate)
    """

    shift: float
    noise_floor: float
    clears_floor: bool


class RQ2Aggregate(BaseModel):
    """The RQ2 modality-contrast aggregate (SPEC-text sec 8 / 10 / 4.8).

    Fields:
        condition_diagnostics   : per-condition AnswerDiagnostics (FULL/CA/KA only)
        text_noise_floor        : per-modality classifier error_rate for text
        structure_noise_floor   : per-modality classifier error_rate for structure
        full_baseline_fab_mean  : FULL baseline fabrication mean (across N runs)
        full_baseline_fab_se    : SE of the FULL baseline fabrication proportion
        content_absent_shift    : FabricationShift for CONTENT_ABSENT vs FULL
        knowledge_absent_shift  : FabricationShift for KNOWLEDGE_ABSENT vs FULL (None if no KA runs)
        epistemic_level         : always INTERVENTIONAL_AGGREGATE (Invariant #20)
    """

    condition_diagnostics: dict[str, AnswerDiagnostics]
    text_noise_floor: float
    structure_noise_floor: float
    full_baseline_fab_mean: float
    full_baseline_fab_se: float
    content_absent_shift: FabricationShift | None = None
    knowledge_absent_shift: FabricationShift | None = None
    epistemic_level: EpistemicLevel = EpistemicLevel.INTERVENTIONAL_AGGREGATE


# ---------------------------------------------------------------------------
# Pure computation
# ---------------------------------------------------------------------------


def _extract_modality_error(reliability: dict[str, Any], modality: str) -> float:
    """Extract the error_rate for a given modality from the reliability dict.

    Returns 0.0 if the modality is not found (safe fallback).
    """
    for entry in reliability.get("per_modality_error", []):
        if entry.get("modality") == modality:
            return float(entry.get("error_rate", 0.0))
    return 0.0


def compute_rq2_aggregate(
    runset: RunSet,
    reliability: dict[str, Any],
) -> RQ2Aggregate:
    """Compute the RQ2 modality-contrast aggregate from a RunSet + reliability report.

    Groups the runset's runs by condition, EXCLUDING FULL_NO_EDIT_RERUN (EX3 baseline).
    Calls aggregate_runset per condition. Computes fabrication shifts + clears_floor
    against the per-modality noise floor from the reliability report.

    A condition with zero runs is skipped (its shift is None; no crash).

    Pure function: no file I/O.
    """
    # Group runs by condition, excluding FULL_NO_EDIT_RERUN.
    by_condition: dict[str, list] = {c.value: [] for c in _RQ2_CONDITIONS}
    for run in runset.runs:
        if run.condition in _RQ2_CONDITIONS:
            by_condition[run.condition.value].append(run)

    # Aggregate per condition (skip empty).
    condition_diagnostics: dict[str, AnswerDiagnostics] = {}
    for cond_value, runs in by_condition.items():
        if not runs:
            continue
        condition_diagnostics[cond_value] = aggregate_runset(runs)

    # Extract noise floors from the reliability report.
    text_floor = _extract_modality_error(reliability, "text")
    structure_floor = _extract_modality_error(reliability, "structure")

    # FULL baseline fabrication mean + SE.
    full_diag = condition_diagnostics.get(Condition.FULL.value)
    if full_diag is None:
        # No FULL runs: degenerate case (should not happen in practice).
        full_fab_mean = 0.0
        full_fab_se = 0.0
    else:
        full_fab_mean = full_diag.status_distribution.get(_FAB, _zero_mean_se()).mean
        full_fab_se = full_diag.status_distribution.get(_FAB, _zero_mean_se()).se

    # Compute fabrication shifts.
    content_shift = _compute_shift(
        condition_diagnostics.get(Condition.CONTENT_ABSENT.value),
        full_fab_mean,
        noise_floor=text_floor,
    )
    knowledge_shift = _compute_shift(
        condition_diagnostics.get(Condition.KNOWLEDGE_ABSENT.value),
        full_fab_mean,
        noise_floor=structure_floor,
    )

    return RQ2Aggregate(
        condition_diagnostics=condition_diagnostics,
        text_noise_floor=text_floor,
        structure_noise_floor=structure_floor,
        full_baseline_fab_mean=full_fab_mean,
        full_baseline_fab_se=full_fab_se,
        content_absent_shift=content_shift,
        knowledge_absent_shift=knowledge_shift,
    )


def _zero_mean_se():
    """Return a zero-valued StatusMeanSE (avoids circular import)."""
    from ivg_kg.schema import StatusMeanSE
    return StatusMeanSE(mean=0.0, se=0.0)


def _compute_shift(
    diag: AnswerDiagnostics | None,
    full_fab_mean: float,
    noise_floor: float,
) -> FabricationShift | None:
    """Compute the FabricationShift for one condition vs the FULL baseline.

    Returns None when diag is None (condition had no runs).
    """
    if diag is None:
        return None
    cond_fab_mean = diag.status_distribution.get(_FAB, _zero_mean_se()).mean
    shift = cond_fab_mean - full_fab_mean
    return FabricationShift(
        shift=shift,
        noise_floor=noise_floor,
        clears_floor=shift > noise_floor,
    )


# ---------------------------------------------------------------------------
# Static report figure (Part 2)
# ---------------------------------------------------------------------------

# Condition display labels (x-axis tick labels).
_COND_LABELS: dict[str, str] = {
    Condition.FULL.value: "Full",
    Condition.CONTENT_ABSENT.value: "Content-withheld",
    Condition.KNOWLEDGE_ABSENT.value: "Knowledge-withheld\n(hard-entity control)",
}

# Ordered conditions for the x-axis grouping.
_COND_ORDER = [
    Condition.FULL.value,
    Condition.CONTENT_ABSENT.value,
    Condition.KNOWLEDGE_ABSENT.value,
]

# Figure title including the INTERVENTIONAL_AGGREGATE stamp.
_FIGURE_TITLE = (
    "RQ2 modality-contrast aggregate -- claim-status distribution across conditions"
    "<br><b>INTERVENTIONAL_AGGREGATE</b> (offline sweep; filled triangle + interval)"
)

# Small-N caveat text shown as an annotation.
_SMALL_N_CAVEAT = (
    "SE = sqrt(p(1-p)/N); N=20 is a floor -- small differences are within noise."
)


def make_rq2_figure(aggregate: RQ2Aggregate) -> go.Figure:
    """Build the RQ2 modality-contrast static report figure.

    Encodings (ORTHOGONAL channels; hue stays STATUS -- Invariant #12):
    - Grouped bars: per-status answer-level mean fraction per condition
    - SE error bars: the +interval
    - Noise floor: horizontal lines per modality (NOT a hue change)
    - INTERVENTIONAL_AGGREGATE stamp: filled-triangle marker in the title + legend
    - Small-N caveat: prominent annotation

    The knowledge-withheld condition is labeled as the intrinsic-difficulty /
    hard-entity control for the content-absence/obscurity confound.

    Bars start at y=0.
    """
    # Status palette: same hex values as app/theme.py STATUS_COLORS + STATUS_ORDER
    # + STATUS_UI_LABELS (the canonical single source of truth for hue = status).
    # Inlined here so rq2_aggregate is importable without the app/ directory on
    # sys.path (scripts/emit_rq2_figure.py runs from an arbitrary cwd).
    # If you change app/theme.py STATUS_COLORS, update these in sync.
    status_colors = {
        "retrieved": "#8fd9a8",
        "reasoned-supportable": "#f2d08a",
        "fabricated": "#f4a6c0",
    }
    status_order = ["retrieved", "reasoned-supportable", "fabricated"]
    status_labels = {
        "retrieved": "Retrieved",
        "reasoned-supportable": "Supportable",
        "fabricated": "Fabricated",
    }

    fig = go.Figure()

    # Determine conditions present in the aggregate.
    conditions_present = [c for c in _COND_ORDER if c in aggregate.condition_diagnostics]
    x_labels = [_COND_LABELS.get(c, c) for c in conditions_present]

    # Add one grouped Bar trace per status (hue = status, orthogonal to condition).
    for status in status_order:
        means_pct = []
        errors_pct = []
        for cond_val in conditions_present:
            diag = aggregate.condition_diagnostics[cond_val]
            ms = diag.status_distribution.get(status)
            m = ms.mean if ms else 0.0
            e = ms.se if ms else 0.0
            means_pct.append(round(m * 100, 2))
            errors_pct.append(round(e * 100, 2))

        label = status_labels.get(status, status)
        color = status_colors.get(status, "#888888")

        fig.add_trace(
            go.Bar(
                name=label,
                x=x_labels,
                y=means_pct,
                marker_color=color,
                error_y={
                    "type": "data",
                    "array": errors_pct,
                    "visible": True,
                    "color": "#c9d1d9",  # theme.TEXT (avoid importing theme entirely)
                    "thickness": 1.5,
                    "width": 6,
                },
                text=[f"{v:.1f}+/-{e:.1f}%" for v, e in zip(means_pct, errors_pct, strict=False)],
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "%{x}: %{y:.1f}% (SE +/-%{error_y.array:.1f}%)"
                    "<extra></extra>"
                ),
            )
        )

    # --- Noise floor horizontal lines (orthogonal channel -- NOT a hue change) ---
    # Text noise floor governs CONTENT_ABSENT; structure governs KNOWLEDGE_ABSENT.
    # Draw each as a horizontal line spanning the full figure.
    shapes = []
    noise_annotations = []

    text_floor_pct = aggregate.text_noise_floor * 100
    struct_floor_pct = aggregate.structure_noise_floor * 100

    shapes.append(
        {
            "type": "line",
            "x0": -0.5,
            "x1": len(conditions_present) - 0.5,
            "y0": text_floor_pct,
            "y1": text_floor_pct,
            "xref": "x",
            "yref": "y",
            "line": {"color": "#aaddff", "width": 1.5, "dash": "dot"},
        }
    )
    noise_annotations.append(
        {
            "x": len(conditions_present) - 0.5,
            "y": text_floor_pct,
            "xref": "x",
            "yref": "y",
            "text": f"text noise floor ({text_floor_pct:.1f}%)",
            "showarrow": False,
            "xanchor": "right",
            "yanchor": "bottom",
            "font": {"size": 9, "color": "#aaddff"},
        }
    )

    if text_floor_pct != struct_floor_pct:
        shapes.append(
            {
                "type": "line",
                "x0": -0.5,
                "x1": len(conditions_present) - 0.5,
                "y0": struct_floor_pct,
                "y1": struct_floor_pct,
                "xref": "x",
                "yref": "y",
                "line": {"color": "#ffddaa", "width": 1.5, "dash": "dash"},
            }
        )
        noise_annotations.append(
            {
                "x": len(conditions_present) - 0.5,
                "y": struct_floor_pct,
                "xref": "x",
                "yref": "y",
                "text": f"structure noise floor ({struct_floor_pct:.1f}%)",
                "showarrow": False,
                "xanchor": "right",
                "yanchor": "bottom",
                "font": {"size": 9, "color": "#ffddaa"},
            }
        )

    # --- INTERVENTIONAL_AGGREGATE filled-triangle stamp in legend ---
    # Add a scatter trace with a filled-triangle marker (Invariant #20).
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker={
                "symbol": "triangle-up",
                "size": 12,
                "color": "#ffffff",
                "line": {"width": 1.5, "color": "#c9d1d9"},
            },
            name="INTERVENTIONAL_AGGREGATE",
            showlegend=True,
            legendgroup="epistemic",
        )
    )

    # --- Small-N caveat annotation ---
    small_n_annotation = {
        "x": 0.5,
        "y": -0.22,
        "xref": "paper",
        "yref": "paper",
        "text": f"<i>Caveat: {_SMALL_N_CAVEAT}</i>",
        "showarrow": False,
        "xanchor": "center",
        "yanchor": "top",
        "font": {"size": 9, "color": "#8b949e"},
    }

    # --- Clears-floor summary annotation ---
    shift_lines = []
    if aggregate.content_absent_shift is not None:
        s = aggregate.content_absent_shift
        verdict = "CLEARS floor" if s.clears_floor else "within noise"
        shift_lines.append(
            f"Content-absent shift: {s.shift * 100:+.1f}pp ({verdict}; text floor {s.noise_floor * 100:.1f}%)"
        )
    if aggregate.knowledge_absent_shift is not None:
        s = aggregate.knowledge_absent_shift
        verdict = "CLEARS floor" if s.clears_floor else "within noise"
        shift_lines.append(
            f"Knowledge-absent shift: {s.shift * 100:+.1f}pp ({verdict}; structure floor {s.noise_floor * 100:.1f}%)"
        )

    shift_annotation = {
        "x": 0.01,
        "y": 0.99,
        "xref": "paper",
        "yref": "paper",
        "text": "<br>".join(shift_lines) if shift_lines else "",
        "showarrow": False,
        "xanchor": "left",
        "yanchor": "top",
        "align": "left",
        "font": {"size": 9, "color": "#c9d1d9"},
        "bgcolor": "rgba(22,27,34,0.7)",
        "bordercolor": "#30363d",
        "borderwidth": 1,
    }

    all_annotations = noise_annotations + [small_n_annotation, shift_annotation]

    fig.update_layout(
        title={
            "text": _FIGURE_TITLE,
            "font": {"size": 11},
            "xanchor": "left",
            "x": 0.0,
        },
        barmode="group",
        plot_bgcolor="#0d1117",
        paper_bgcolor="#161b22",
        font={
            "color": "#c9d1d9",
            "family": "'JetBrains Mono', 'SF Mono', 'Menlo', 'Consolas', monospace",
            "size": 11,
        },
        xaxis={
            "color": "#8b949e",
            "showgrid": False,
            "title": "Condition",
        },
        yaxis={
            "title": "% of claims (mean across N runs)",
            "color": "#8b949e",
            "gridcolor": "#30363d",
            "range": [0, 105],
            "rangemode": "tozero",
        },
        legend={
            "bgcolor": "rgba(22,27,34,0.8)",
            "bordercolor": "#30363d",
            "borderwidth": 1,
            "title": {"text": "Status / Epistemic"},
        },
        shapes=shapes,
        annotations=all_annotations,
        margin={"l": 56, "r": 16, "t": 80, "b": 100},
        height=480,
    )

    return fig


def save_rq2_figure(fig: go.Figure, out_path: str | Path) -> None:
    """Save the RQ2 figure to HTML always; PNG/PDF only if kaleido is available.

    Best-effort: absence of kaleido does not crash. HTML is always written.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Always write HTML.
    html_path = out_path.with_suffix(".html")
    fig.write_html(str(html_path))

    # PNG: attempt only if kaleido is importable.
    try:
        import kaleido  # noqa: F401 -- presence check only
        png_path = out_path.with_suffix(".png")
        fig.write_image(str(png_path))
        pdf_path = out_path.with_suffix(".pdf")
        fig.write_image(str(pdf_path))
    except ImportError:
        pass  # kaleido not installed; HTML-only is fine


# ---------------------------------------------------------------------------
# Reliability report loader (thin helper for scripts; pure I/O)
# ---------------------------------------------------------------------------


def load_reliability_report(path: str | Path) -> dict[str, Any]:
    """Load a reliability_report.json from disk and return it as a plain dict.

    compute_rq2_aggregate takes an already-loaded dict, so this helper is only
    needed by the emit script layer.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))
