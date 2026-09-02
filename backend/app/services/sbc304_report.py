"""Sprint 10 — SBC 304 Structural Calculation Report.

Data-driven structural calculation package generator.

CRITICAL ARCHITECTURE RULE
--------------------------
This module is a REPORT BUILDER.

It does NOT:
    - perform structural calculations
    - select engineering assumptions
    - determine code compliance
    - invent missing values
    - certify structural work
    - replace professional engineering review

The engineering engines decide the engineering results.
This module only formats and reports those results.

Expected flow:

    Plan / Survey
          |
          v
    Structural Analysis Engine
          |
          +----> Member Design Results
          |
          +----> Load Results
          |
          v
    Compliance Engine
          |
          +----> Pass / Warn / Fail
          |
          v
    BOQ Engine
          |
          v
    THIS REPORT BUILDER
          |
          v
    Preliminary SBC 304 Calculation Package
          |
          v
    Licensed Professional Engineer Review / Certification

Reader-contract notes
---------------------
Every ``*_build_*`` helper reads exactly the fields the upstream engines
actually emit (see analysis.py / concrete_design.py / compliance_engine.py /
boq_generator.py). When an upstream engine does not supply a value, the
report renders "N/A" rather than inventing one.
"""

from __future__ import annotations

import logging
import math
import secrets
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.models.plan_data import PlanData
from app.services.exporters import build_pdf_report, exports_dir, now_iso


log = logging.getLogger("imad.sbc304_report")


class SBC304ReportError(Exception):
    """Raised when an SBC 304 report cannot be generated safely."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_sbc304_report(
    project_id: int,
    project_name: str,
    plan: PlanData,
    analysis: Dict[str, Any],
    compliance: Dict[str, Any],
    boq: Optional[Dict[str, Any]] = None,
    survey: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a data-driven preliminary SBC 304 calculation package.

    IMPORTANT:
        This function reports engineering results supplied by upstream
        engines. It does not create engineering conclusions.

    The generated document is explicitly marked:

        PRELIMINARY DESIGN PACKAGE
        PENDING PROFESSIONAL ENGINEER REVIEW

    Args:
        project_id: Project identifier.
        project_name: Project title.
        plan: Structural geometry and project-level structural data.
        analysis: AnalysisResult from the structural analysis/design engine.
        compliance: ComplianceResult from the code compliance engine.
        boq: Optional BOQ result from the BOQ engine.
        survey: Optional survey/geotechnical/site information.

    Returns:
        Absolute/string path to the generated PDF.

    Raises:
        SBC304ReportError:
            If critical inputs are missing or PDF generation fails.
    """

    _validate_inputs(
        project_id=project_id,
        project_name=project_name,
        plan=plan,
        analysis=analysis,
        compliance=compliance,
    )

    path = exports_dir() / (
        f"SBC304-p{project_id}-{_stamp_slug()}.pdf"
    )

    try:
        document_info = _build_document_info(
            project_id=project_id,
            project_name=project_name,
            analysis=analysis,
            compliance=compliance,
        )

        project_info = _build_project_info(
            project_name=project_name,
            plan=plan,
            survey=survey,
        )

        design_criteria = _build_design_criteria(
            plan=plan,
            analysis=analysis,
            survey=survey,
            compliance=compliance,
        )

        design_loads = _build_design_loads(
            analysis=analysis,
        )

        analysis_results = _build_analysis_results(
            analysis=analysis,
        )

        member_summary, member_details, max_utilization = (
            _build_member_design(
                analysis=analysis,
            )
        )

        compliance_table, compliance_summary = (
            _build_compliance_section(
                compliance=compliance,
            )
        )

        boq_table = _build_boq_summary(boq)

        certification = _build_professional_review(
            project_name=project_name,
            analysis=analysis,
            compliance=compliance,
        )

        references = _build_references(
            analysis=analysis,
            compliance=compliance,
            survey=survey,
        )
        sections = [
            ("Document Control", document_info,
             "Document identification, revision and preparation status."),
            ("Project Information & Scope", project_info,
             ("Project information reported from the project model, "
              "plan and available site/survey data.")),
            ("Design Criteria & Standards", design_criteria,
             ("Design criteria reported from project and engineering "
              "engine inputs. No missing engineering values are "
              "assumed by the report builder.")),
            ("Design Loads", design_loads,
             ("Loads reported from the structural analysis/design "
              "engine together with their supplied source or "
              "calculation method.")),
            ("Structural Analysis Results", analysis_results,
             ("Analysis results reported from the structural analysis "
              "engine.")),
            ("Member Design Summary", member_summary,
             ("Member utilization and status are derived from "
              "individual design-engine results. Missing utilization "
              "data is reported as incomplete rather than treated as "
              "PASS.")),
            ("Member Design Results", member_details,
             ("Detailed member results supplied by the structural "
              "design engine.")),
            ("Code Compliance Checklist", compliance_table,
             ("Compliance status is supplied by the compliance "
              "engine. The report builder does not create or override "
              "PASS/WARN/FAIL results.")),
        ]

        if boq_table:
            sections.append(
                ("Bill of Quantities — Preliminary Summary", boq_table,
                 ("BOQ quantities and costs are reported from the BOQ "
                  "engine. This section is a preliminary structural "
                  "quantity/cost summary and is not a substitute for "
                  "the final project BOQ."))
            )

        sections.extend(
            [
                ("References & Source Traceability", references,
                 ("Engineering references and source information "
                  "supplied by the upstream project/design engines.")),
                ("Professional Review & Certification", certification,
                 ("This document is a preliminary autonomous design "
                  "package. A licensed professional engineer must "
                  "review the engineering inputs, calculations, "
                  "assumptions, drawings and compliance results before "
                  "any formal submission or certification.")),
            ]
        )

        compliance_counts = _get_compliance_counts(compliance)

        summary_box = {
            "Code": _resolve_code_name(analysis, compliance),
            "Max Utilization": (
                f"{max_utilization:.2f}"
                if max_utilization is not None
                else "N/A"
            ),
            "Compliance": (
                f"PASS {compliance_counts['passed']} | "
                f"WARN {compliance_counts['warned']} | "
                f"FAIL {compliance_counts['failed']}"
            ),
            "Status": "PENDING PROFESSIONAL REVIEW",
        }

        build_pdf_report(
            path,
            title="Structural Calculation Package",
            subtitle=f"SBC 304 — {project_name}",
            meta_rows=document_info,
            summary_box=summary_box,
            sections=sections,
        )

        log.info(
            "SBC 304 preliminary calculation package generated: %s",
            path,
        )

        return str(path)

    except SBC304ReportError:
        raise

    except Exception as exc:
        log.exception(
            "SBC 304 report generation failed"
        )
        raise SBC304ReportError(
            f"PDF generation failed: {exc}"
        ) from exc
# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_inputs(
    *,
    project_id: int,
    project_name: str,
    plan: PlanData,
    analysis: Dict[str, Any],
    compliance: Dict[str, Any],
) -> None:
    """Validate only the data required to build the report.

    This deliberately does NOT validate engineering correctness.
    Engineering correctness belongs to the upstream engines.
    """

    if project_id is None:
        raise SBC304ReportError(
            "project_id is required"
        )

    if not project_name or not project_name.strip():
        raise SBC304ReportError(
            "project_name is required"
        )

    if plan is None:
        raise SBC304ReportError(
            "plan is required"
        )

    if not isinstance(analysis, dict):
        raise SBC304ReportError(
            "analysis must be a dictionary"
        )

    if not isinstance(compliance, dict):
        raise SBC304ReportError(
            "compliance must be a dictionary"
        )


# ---------------------------------------------------------------------------
# Code resolution
# ---------------------------------------------------------------------------

def _resolve_code_name(
    analysis: Dict[str, Any],
    compliance: Dict[str, Any],
) -> str:
    """Report the code the engineering engines actually applied.

    Preference order: compliance engine, then the design engine, then the
    literal fallback. This avoids labelling the package with a code the
    engines did not use.
    """

    for candidate in (
        compliance,
        analysis,
        analysis.get("design"),
    ):
        if not isinstance(candidate, dict):
            continue

        name = candidate.get("code_name")

        if name and str(name).strip():
            return str(name).strip()

    return "SBC 304"


# ---------------------------------------------------------------------------
# Document control
# ---------------------------------------------------------------------------

def _build_document_info(
    *,
    project_id: int,
    project_name: str,
    analysis: Dict[str, Any],
    compliance: Dict[str, Any],
) -> List[List[str]]:
    """Build document-control metadata."""

    return [
        ["Document Type", "Structural Calculation Package"],
        ["Code", _resolve_code_name(analysis, compliance)],
        ["Project", project_name],
        ["Project ID", str(project_id)],
        [
            "Document Number",
            _safe_text(
                analysis.get("document_number"),
                f"IMAD-SBC304-{project_id}",
            ),
        ],
        [
            "Revision",
            _safe_text(analysis.get("revision"), "00"),
        ],
        [
            "Issue Status",
            _safe_text(
                analysis.get("issue_status"),
                "PRELIMINARY DESIGN PACKAGE",
            ),
        ],
        ["Prepared By", "Imad Engineering Engine"],
        ["Generated", now_iso()],
        ["Professional Review", "PENDING"],
    ]
# ---------------------------------------------------------------------------
# Project information
# ---------------------------------------------------------------------------

def _build_project_info(
    *,
    project_name: str,
    plan: PlanData,
    survey: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Build project/scope information without engineering assumptions."""

    bounds = _safe_bounds(plan)
    footprint = _calculate_footprint(bounds)

    rows = [
        ["Attribute", "Value", "Source"],
        ["Project Title", project_name, "Project input"],
        [
            "Number of Stories",
            _value_or_na(getattr(plan, "stories", None)),
            "Plan geometry",
        ],
        [
            "Footprint (m²)",
            (
                f"{footprint:.2f}"
                if footprint is not None
                else "N/A"
            ),
            "Plan bounds",
        ],
        [
            "Structural System",
            _value_or_na(getattr(plan, "system_type", None)),
            "Plan specification",
        ],
        [
            "Columns",
            str(len(getattr(plan, "columns", []) or [])),
            "Plan geometry",
        ],
        [
            "Beams",
            str(len(getattr(plan, "beams", []) or [])),
            "Plan geometry",
        ],
        [
            "Walls",
            str(len(getattr(plan, "walls", []) or [])),
            "Plan geometry",
        ],
    ]

    if survey:
        rows.extend(_survey_project_rows(survey))

    return rows


def _survey_project_rows(
    survey: Dict[str, Any],
) -> List[List[str]]:
    """Extract site/survey values without inventing them.

    Field names follow the :class:`SurveyReading` contract
    (``soil_bearing_capacity_kpa``, ``groundwater_depth_m``,
    ``terrain_slope_deg``, ``latitude``/``longitude``).
    """

    rows: List[List[str]] = []

    if survey.get("soil_bearing_capacity_kpa") is not None:
        rows.append([
            "Soil Bearing Capacity",
            _format_value(survey.get("soil_bearing_capacity_kpa")),
            "Survey / geotechnical input",
        ])

    if survey.get("groundwater_depth_m") is not None:
        rows.append([
            "Groundwater Depth",
            _format_value(survey.get("groundwater_depth_m")),
            "Survey / geotechnical input",
        ])

    if survey.get("terrain_slope_deg") is not None:
        rows.append([
            "Terrain Slope",
            _format_value(survey.get("terrain_slope_deg")),
            "Survey / geotechnical input",
        ])

    if survey.get("soil_type"):
        rows.append([
            "Soil Type",
            str(survey.get("soil_type")),
            "Survey / geotechnical input",
        ])

    if survey.get("geotechnical_report"):
        rows.append([
            "Geotechnical Report",
            str(survey.get("geotechnical_report")),
            "Survey / geotechnical input",
        ])

    lat, lon = survey.get("latitude"), survey.get("longitude")

    if lat is not None and lon is not None:
        rows.append([
            "Project Location",
            f"{float(lat):.4f}, {float(lon):.4f}",
            "Survey / geotechnical input",
        ])

    return rows


# ---------------------------------------------------------------------------
# Design criteria
# ---------------------------------------------------------------------------

def _build_design_criteria(
    *,
    plan: PlanData,
    analysis: Dict[str, Any],
    survey: Optional[Dict[str, Any]],
    compliance: Dict[str, Any],
) -> List[List[str]]:
    """Build design criteria from supplied engine/project data.

    IMPORTANT:
        No code factors are invented here. Strength values come from the
        plan materials (``concrete``/``steel`` labels or numeric
        ``concrete_strength_mpa``/``steel_yield_mpa``). Code factors are
        read from the design engine (``design.design_factors``) when present.
    """

    materials = getattr(plan, "materials", None) or {}
    design = analysis.get("design", {}) or {}

    rows = [
        ["Criterion", "Value", "Source / Reference"],
        [
            "Applicable Code",
            _resolve_code_name(analysis, compliance),
            _safe_text(analysis.get("code_source"), "Analysis engine"),
        ],
    ]

    fc = _numeric(materials.get("concrete_strength_mpa"))

    if fc is not None:
        rows.append([
            "Concrete Strength",
            f"{fc:.1f} MPa",
            "Plan materials",
        ])
    elif materials.get("concrete"):
        rows.append([
            "Concrete Grade",
            str(materials.get("concrete")),
            "Plan materials",
        ])

    fy = _numeric(materials.get("steel_yield_mpa"))

    if fy is not None:
        rows.append([
            "Reinforcement Yield Strength",
            f"{fy:.1f} MPa",
            "Plan materials",
        ])
    elif materials.get("steel"):
        rows.append([
            "Reinforcement Grade",
            str(materials.get("steel")),
            "Plan materials",
        ])

    rows.append([
        "Structural Analysis Method",
        _safe_text(
            analysis.get("method"),
            analysis.get("solver"),
            "N/A",
        ),
        "Analysis engine",
    ])

    rows.append([
        "Analysis Software",
        _safe_text(
            analysis.get("software"),
            analysis.get("solver"),
            "N/A",
        ),
        "Analysis engine",
    ])

    code_factors = design.get(
        "design_factors",
        analysis.get("design_factors", {}),
    )

    if isinstance(code_factors, dict):
        for name, value in code_factors.items():
            if value is None:
                continue

            clause = ""

            if isinstance(value, dict):
                actual_value = value.get("value")
                clause = _safe_text(value.get("clause"), "")
            else:
                actual_value = value

            rows.append([
                _humanize_key(name),
                _format_value(actual_value),
                clause or "Design engine",
            ])

    if analysis.get("design_life_years") is not None:
        rows.append([
            "Design Life",
            f"{analysis.get('design_life_years')} years",
            _safe_text(
                analysis.get("design_life_source"),
                "Project/design input",
            ),
        ])

    seismic = analysis.get("seismic", {})

    if isinstance(seismic, dict):
        for key in (
            "site_class",
            "sds",
            "sd1",
            "seismic_design_category",
            "importance_factor",
        ):
            if key not in seismic:
                continue

            rows.append([
                _humanize_key(key),
                _format_value(seismic.get(key)),
                _safe_text(
                    seismic.get(f"{key}_source"),
                    seismic.get("source", "Analysis engine"),
                ),
            ])

    return rows


# ---------------------------------------------------------------------------
# Loads
# ---------------------------------------------------------------------------

def _build_design_loads(
    *,
    analysis: Dict[str, Any],
) -> List[List[str]]:
    """Build the load table exclusively from supplied analysis data.

    Recognises both the fields the current analysis engine emits
    (``loads.live_kpa``, ``loads.floor_area_kpa``, ``loads.total_weight_kN``,
    ``loads.lateral_base_kN``) and the extended load surface documented for
    richer engines (dead/live/wind/seismic keys).
    """

    loads = analysis.get("loads", {})

    if not isinstance(loads, dict):
        loads = {}

    rows = [
        ["Load / Parameter", "Value", "Source / Calculation Method"],
    ]

    current_engine_fields = [
        (
            "live_kpa",
            "Floor Live Load",
            "kN/m²",
            "live_load_source",
        ),
        (
            "dead_extra_kpa",
            "Superimposed Dead Load",
            "kN/m²",
            "dead_load_source",
        ),
        (
            "floor_area_kpa",
            "Total Floor Load",
            "kN/m²",
            "Analysis engine",
        ),
        (
            "total_weight_kN",
            "Total Gravity Weight",
            "kN",
            "Analysis engine",
        ),
        (
            "lateral_base_kN",
            "Base Shear",
            "kN",
            "Lateral analysis",
        ),
    ]

    for key, label, unit, source_key in current_engine_fields:
        value = loads.get(key)

        if value is None:
            continue

        rows.append([
            label,
            f"{_format_number(value)} {unit}",
            _safe_text(loads.get(source_key), "Analysis engine"),
        ])

    base_shear = (
        loads.get("base_shear_kn")
        or loads.get("lateral_base_kN")
    )

    if base_shear is None:
        reactions = analysis.get("reactions", {})

        if isinstance(reactions, dict):
            base_shear = reactions.get("base_shear_kN")

    if base_shear is not None:
        rows.append([
            "Base Shear",
            f"{_format_number(base_shear)} kN",
            _safe_text(loads.get("base_shear_source"), "Lateral analysis"),
        ])

    load_definitions = [
        ("dead_load_kn_m2", "Dead Load", "kN/m²", "dead_load_source"),
        ("live_load_kn_m2", "Live Load", "kN/m²", "live_load_source"),
        ("wind_speed_kmh", "Basic Wind Speed", "km/h", "wind_source"),
        (
            "wind_pressure_kpa",
            "Design Wind Pressure",
            "kPa",
            "wind_pressure_source",
        ),
        ("sds", "SDS", "g", "seismic_source"),
        ("sd1", "SD1", "g", "seismic_source"),
        (
            "seismic_weight_kn",
            "Seismic Weight",
            "kN",
            "seismic_weight_source",
        ),
        ("base_shear_kn", "Base Shear", "kN", "base_shear_source"),
    ]

    for key, label, unit, source_key in load_definitions:
        if key not in loads:
            continue

        value = loads.get(key)

        if value is None:
            continue

        rows.append([
            label,
            f"{_format_number(value)} {unit}",
            _safe_text(loads.get(source_key), "Analysis engine"),
        ])

    extra_loads = loads.get("additional", [])

    if isinstance(extra_loads, list):
        for load in extra_loads:
            if not isinstance(load, dict):
                continue

            name = load.get("name")
            value = load.get("value")

            if name is None or value is None:
                continue

            unit = _safe_text(load.get("unit"), "")

            rows.append([
                str(name),
                (
                    f"{_format_value(value)} {unit}"
                    if unit
                    else _format_value(value)
                ),
                _safe_text(load.get("source"), "Analysis engine"),
            ])

    if len(rows) == 1:
        rows.append([
            "Load data",
            "N/A",
            "No load data supplied by analysis engine",
        ])

    return rows


# ---------------------------------------------------------------------------
# Structural analysis
# ---------------------------------------------------------------------------

def _build_analysis_results(
    *,
    analysis: Dict[str, Any],
) -> List[List[str]]:
    """Build high-level analysis results from supplied engine data."""

    rows = [["Metric", "Value", "Method / Source"]]

    mappings = [
        ("method", "Analysis Method", "Analysis request"),
        ("solver", "Analysis Solver", "Analysis engine"),
        ("software", "Analysis Software", "Analysis engine"),
        ("model_version", "Model Version", "Analysis engine"),
        ("max_deflection_mm", "Maximum Deflection", "Structural model"),
        ("max_moment_kNm", "Maximum Moment", "Load combinations"),
        ("max_shear_kn", "Maximum Shear", "Load combinations"),
        ("max_axial_kn", "Maximum Axial Force", "Load combinations"),
        ("base_shear_kn", "Base Shear", "Lateral analysis"),
        ("max_utilization", "Max Utilization", "Design engine"),
    ]

    for key, label, source in mappings:
        if analysis.get(key) is None:
            continue

        rows.append([
            label,
            _format_value_with_unit(key, analysis.get(key)),
            source,
        ])

    if len(rows) == 1:
        rows.append([
            "Analysis results",
            "N/A",
            "No summary results supplied",
        ])

    return rows


# ---------------------------------------------------------------------------
# Member design
# ---------------------------------------------------------------------------

def _build_member_design(
    *,
    analysis: Dict[str, Any],
) -> Tuple[List[List[str]], List[List[str]], Optional[float]]:
    """Build member summary and detailed member results.

    Missing utilization is NOT interpreted as zero.
    """

    design = analysis.get("design", {})

    if not isinstance(design, dict):
        design = {}

    member_groups = [
        ("Columns", design.get("columns", [])),
        ("Beams", design.get("beams", [])),
        ("Walls", design.get("walls", [])),
        ("Slabs", design.get("slabs", [])),
        ("Foundations", design.get("foundations", [])),
        ("Members", design.get("members", [])),
    ]

    summary = [["Member Type", "Count", "Max Utilization", "Status"]]
    details = [
        ["Member Type", "Member ID", "Utilization", "Status", "Governing Check"],
    ]

    all_utilizations: List[float] = []

    for member_type, members in member_groups:
        if not isinstance(members, list) or not members:
            continue

        valid_utils: List[float] = []

        for member in members:
            if not isinstance(member, dict):
                continue

            utilization = _numeric(member.get("utilization"))
            member_id = _safe_text(
                member.get("id"), member.get("member_id"), "N/A"
            )

            if utilization is None:
                status = "DATA INCOMPLETE"
                utilization_text = "N/A"
            else:
                valid_utils.append(utilization)
                all_utilizations.append(utilization)
                status = _utilization_status(utilization)
                utilization_text = f"{utilization:.2f}"

            details.append([
                member_type,
                member_id,
                utilization_text,
                status,
                _safe_text(member.get("governing_check"), "N/A"),
            ])

        if valid_utils:
            max_util = max(valid_utils)

            summary.append([
                member_type,
                str(len(members)),
                f"{max_util:.2f}",
                _utilization_status(max_util),
            ])
        else:
            summary.append([
                member_type,
                str(len(members)),
                "N/A",
                "DATA INCOMPLETE",
            ])

    if all_utilizations:
        max_utilization = max(all_utilizations)

        summary.append([
            "MAXIMUM — ALL MEMBERS",
            "—",
            f"{max_utilization:.2f}",
            _utilization_status(max_utilization),
        ])
    else:
        max_utilization = None

        summary.append([
            "MAXIMUM — ALL MEMBERS",
            "—",
            "N/A",
            "DATA INCOMPLETE",
        ])

    if len(details) == 1:
        details.append([
            "N/A",
            "N/A",
            "N/A",
            "NO MEMBER DATA",
            "Analysis engine did not supply member results",
        ])

    return summary, details, max_utilization


def _utilization_status(utilization: float) -> str:
    """Convert an actual utilization result into a report status.

    Presentation logic only — the compliance engine remains authoritative.
    """

    if not math.isfinite(utilization):
        return "DATA INVALID"

    if utilization <= 1.0:
        return "✓ PASS"

    return "✗ FAIL"


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

def _build_compliance_section(
    *,
    compliance: Dict[str, Any],
) -> Tuple[List[List[str]], Dict[str, int]]:
    """Report compliance-engine results without changing them."""

    rows = [["Check", "Clause", "Status", "Details"]]

    checks = compliance.get("checks", [])

    if not isinstance(checks, list):
        checks = []

    for check in checks:
        if not isinstance(check, dict):
            continue

        details = check.get("details", {})

        if not isinstance(details, dict):
            details = {}

        rows.append([
            _safe_text(check.get("check_name"), "Unnamed check"),
            _safe_text(details.get("clause"), "N/A"),
            _normalize_status(check.get("status")),
            _safe_text(details.get("note"), details.get("message"), ""),
        ])

    counts = _get_compliance_counts(compliance)

    rows.append([
        "SUMMARY",
        "",
        (
            f"PASS {counts['passed']} | "
            f"WARN {counts['warned']} | "
            f"FAIL {counts['failed']}"
        ),
        _safe_text(
            compliance.get("disclaimer"),
            "Compliance results supplied by compliance engine.",
        ),
    ])

    if len(rows) == 1:
        rows.append([
            "Compliance checks",
            "N/A",
            "NO DATA",
            "No compliance checks supplied",
        ])

    return rows, counts


def _normalize_status(status: Any) -> str:
    """Normalize an engine status for display only."""

    value = str(status or "unknown").strip().lower()

    if value == "pass":
        return "✓ PASS"

    if value == "warn":
        return "⚠ WARN"

    if value == "fail":
        return "✗ FAIL"

    return f"? {value.upper()}"


def _get_compliance_counts(compliance: Dict[str, Any]) -> Dict[str, int]:
    """Get counts from the compliance engine without recomputing them."""

    summary = compliance.get("summary", {})

    if not isinstance(summary, dict):
        summary = {}

    return {
        "passed": _safe_int(summary.get("passed")),
        "warned": _safe_int(summary.get("warned")),
        "failed": _safe_int(summary.get("failed")),
    }


# ---------------------------------------------------------------------------
# BOQ
# ---------------------------------------------------------------------------

def _build_boq_summary(
    boq: Optional[Dict[str, Any]],
) -> Optional[List[List[str]]]:
    """Build a preliminary BOQ summary from BOQ-engine output.

    The complete BOQ remains the responsibility of the BOQ exporter.
    Accepts both the codebase's item contract (``quantity``/``rate``) and
    the extended contract (``qty``/``unit_cost``); missing values are
    reported as N/A, never inferred.
    """

    if not boq:
        return None

    items = boq.get("items", [])

    if not isinstance(items, list):
        return None

    rows = [
        ["Item Code", "Description", "Quantity", "Unit", "Unit Cost", "Total"],
    ]

    # Report the first 10 as a summary, explicitly labelled as such.
    for item in items[:10]:
        if not isinstance(item, dict):
            continue

        quantity = _numeric(item.get("quantity", item.get("qty"))) or 0.0
        unit_cost = _numeric(item.get("unit_cost", item.get("rate")))
        total = _numeric(item.get("total"))

        if total is None and unit_cost is not None:
            total = quantity * unit_cost

        rows.append([
            _safe_text(item.get("code"), ""),
            _safe_text(item.get("description"), ""),
            f"{quantity:.2f}",
            _safe_text(item.get("unit"), ""),
            f"${unit_cost:,.2f}" if unit_cost is not None else "N/A",
            f"${total:,.2f}" if total is not None else "N/A",
        ])

    totals = boq.get("totals", {})

    if not isinstance(totals, dict):
        totals = {}

    amount = None

    for key in ("amount_usd", "grand_total", "total_usd", "total"):
        amount = _numeric(totals.get(key))

        if amount is not None:
            break

    amount_per_m2 = None

    for key in ("amount_per_m2", "cost_per_m2"):
        amount_per_m2 = _numeric(totals.get(key))

        if amount_per_m2 is not None:
            break

    if amount is not None:
        rows.append(["", "TOTAL ESTIMATE", "", "", "", f"${amount:,.2f}"])

    if amount_per_m2 is not None:
        rows.append(["", "COST PER M²", "", "", "", f"${amount_per_m2:,.2f}"])

    rows.append(["", f"SUMMARY OF {len(items)} BOQ ITEMS", "", "", "", ""])

    return rows


# ---------------------------------------------------------------------------
# Professional review
# ---------------------------------------------------------------------------

def _build_professional_review(
    *,
    project_name: str,
    analysis: Dict[str, Any],
    compliance: Dict[str, Any],
) -> List[List[str]]:
    """Build professional review/certification section."""

    return [
        ["Field", "Status / Value"],
        ["Project", project_name],
        ["Prepared By", "Imad Engineering Engine"],
        ["Document Type", "PRELIMINARY DESIGN PACKAGE"],
        ["Current Status", "⚠ PENDING PROFESSIONAL ENGINEER REVIEW"],
        [
            "Analysis Engine",
            _safe_text(analysis.get("method"), "N/A"),
        ],
        [
            "Compliance Engine",
            (
                "Results supplied by compliance engine"
                if compliance.get("checks")
                else "N/A"
            ),
        ],
        ["", ""],
        ["Professional Engineer Name", "____________________________"],
        ["SCE License Number", "____________________________"],
        ["Engineering Firm / Organization", "____________________________"],
        ["Signature / Seal", "____________________________"],
        ["Date", "____________________________"],
        ["", ""],
        [
            "Approval Status",
            "☐ APPROVED    ☐ REVISION REQUIRED    ☐ REJECTED",
        ],
    ]


# ---------------------------------------------------------------------------
# References / traceability
# ---------------------------------------------------------------------------

def _build_references(
    *,
    analysis: Dict[str, Any],
    compliance: Dict[str, Any],
    survey: Optional[Dict[str, Any]],
) -> List[List[str]]:
    """Build a traceability table from supplied engine metadata."""

    rows = [
        ["Reference / Source", "Purpose", "Source"],
    ]

    references = analysis.get("references", [])

    if isinstance(references, list):
        for reference in references:
            if isinstance(reference, dict):
                rows.append([
                    _safe_text(reference.get("name"), "Unnamed reference"),
                    _safe_text(reference.get("purpose"), ""),
                    _safe_text(reference.get("source"), "Analysis engine"),
                ])
            elif isinstance(reference, str):
                rows.append([reference, "", "Analysis engine"])

    compliance_refs = compliance.get("references", [])

    if isinstance(compliance_refs, list):
        for reference in compliance_refs:
            if isinstance(reference, dict):
                rows.append([
                    _safe_text(reference.get("name"), "Unnamed reference"),
                    _safe_text(reference.get("purpose"), ""),
                    _safe_text(reference.get("source"), "Compliance engine"),
                ])
            elif isinstance(reference, str):
                rows.append([reference, "", "Compliance engine"])

    if survey and survey.get("geotechnical_report"):
        rows.append([
            str(survey.get("geotechnical_report")),
            "Geotechnical/site information",
            "Survey input",
        ])

    if len(rows) == 1:
        rows.append(["No references supplied", "N/A", "N/A"])

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_bounds(plan: PlanData) -> Optional[Dict[str, float]]:
    """Safely obtain plan bounds."""

    try:
        bounds = plan.bounds()

        if not isinstance(bounds, dict):
            return None

        required = ("min_x", "max_x", "min_y", "max_y")

        if not all(key in bounds for key in required):
            return None

        return {key: float(bounds[key]) for key in required}

    except Exception:
        return None


def _calculate_footprint(
    bounds: Optional[Dict[str, float]],
) -> Optional[float]:
    """Calculate geometric footprint when valid bounds exist."""

    if not bounds:
        return None

    width = bounds["max_x"] - bounds["min_x"]
    depth = bounds["max_y"] - bounds["min_y"]

    if width <= 0 or depth <= 0:
        return None

    return width * depth


def _value_or_na(value: Any) -> str:
    """Return N/A for absent values."""

    if value is None:
        return "N/A"

    if isinstance(value, str) and not value.strip():
        return "N/A"

    return str(value)


def _safe_text(*values: Any) -> str:
    """Return the first non-empty textual value."""

    for value in values:
        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return "N/A"


def _numeric(value: Any) -> Optional[float]:
    """Convert a value to finite float or return None."""

    if value is None:
        return None

    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    """Convert to a non-negative integer safely."""

    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _format_number(value: Any) -> str:
    """Format numeric values without assuming engineering meaning."""

    number = _numeric(value)

    if number is None:
        return "N/A"

    return f"{number:.3f}".rstrip("0").rstrip(".")


def _format_value(value: Any) -> str:
    """Format arbitrary report values."""

    if value is None:
        return "N/A"

    if isinstance(value, float):
        if not math.isfinite(value):
            return "N/A"

        return _format_number(value)

    return str(value)


def _format_value_with_unit(key: str, value: Any) -> str:
    """Format common analysis metrics with presentation units."""

    units = {
        "max_deflection_mm": "mm",
        "max_moment_kNm": "kN·m",
        "max_shear_kn": "kN",
        "max_axial_kn": "kN",
        "base_shear_kn": "kN",
    }

    unit = units.get(key)
    formatted = _format_value(value)

    if formatted == "N/A":
        return formatted

    return f"{formatted} {unit}" if unit else formatted


def _humanize_key(key: str) -> str:
    """Convert engine metadata keys to readable labels."""

    return key.replace("_", " ").title()


def _stamp_slug() -> str:
    """Generate a short random filename slug."""

    return secrets.token_hex(4)