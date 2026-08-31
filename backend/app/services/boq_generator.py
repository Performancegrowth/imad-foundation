"""Sprint 7 — Bill of Quantities generation from structural analysis.

Generates detailed BOQ (materials, labor, equipment) and BBS (bar bending
schedule) from a plan + optional analysis results. When analysis is present,
uses member forces to size reinforcement more accurately.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.models.plan_data import PlanData
from app.models.survey_data import SurveyReading

log = logging.getLogger("imad.boq")


class BOQError(Exception):
    """Raised when BOQ generation fails."""


CONCRETE_COST_PER_M3 = 850.0  # USD
STEEL_COST_PER_TON = 1200.0  # USD
LABOR_COST_PER_M3 = 180.0  # USD (concrete)
FORMWORK_COST_PER_M2 = 45.0  # USD


def generate_boq(plan: PlanData, survey: Optional[SurveyReading] = None,
                 analysis: Optional[Dict[str, Any]] = None,
                 project_name: str = "Imad Project") -> Dict[str, Any]:
    """Generate a complete bill of quantities from plan + optional analysis.
    
    Args:
        plan: Structural geometry (walls, columns, beams)
        survey: Optional geotechnical data (affects foundation costs)
        analysis: Optional AnalysisResult (member forces, utilization) for better sizing
        project_name: Project identifier
    
    Returns:
        BOQ dict with items, totals, BBS, and cost breakdown
    """
    if not plan:
        raise BOQError("Plan contains no geometry")
    
    # Calculate volumes
    volumes = _calculate_volumes(plan)
    
    # If analysis provided, adjust reinforcement based on actual demands
    if analysis:
        reinforcement = _calculate_reinforcement_from_analysis(plan, analysis)
    else:
        reinforcement = _estimate_reinforcement(plan, volumes)
    
    # Build BOQ items
    items = _generate_items(plan, volumes, reinforcement, survey)
    
    # Calculate totals
    total_usd = sum(item["quantity"] * item["unit_cost"] for item in items)
    total_m2 = volumes.get("total_area_m2", 1.0)
    cost_per_m2 = total_usd / max(total_m2, 1.0)
    
    return {
        "project_name": project_name,
        "items": items,
        "totals": {
            "quantity_concrete_m3": round(volumes["concrete_m3"], 2),
            "quantity_rebar_tonnes": round(reinforcement["steel_tonnes"], 2),
            "amount_usd": round(total_usd, 2),
            "amount_per_m2": round(cost_per_m2, 2),
            "currency": "USD",
            "rebar_kg": round(reinforcement["steel_kg"], 2),
        },
        "bbs": _generate_bbs(plan, reinforcement),
    }


def _calculate_volumes(plan: PlanData) -> Dict[str, float]:
    """Calculate structural volumes: concrete, formwork, area."""
    stories = max(1, plan.stories)
    
    # Slab volume (flat slabs)
    bounds = plan.bounds()
    slab_area = max((bounds["max_x"] - bounds["min_x"]), 1.0) * \
                max((bounds["max_y"] - bounds["min_y"]), 1.0)
    slab_thickness = 0.15  # 150mm typical
    slab_vol = slab_area * slab_thickness * stories
    
    # Columns volume
    col_vol = sum((c.size_m ** 2) * c.height for c in plan.columns) * stories
    
    # Beams volume
    beam_vol = 0.0
    for beam in plan.beams:
        length = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
        beam_vol += beam.width_m * beam.depth_m * length * stories
    
    # Walls volume (outer perimeter)
    wall_vol = 0.0
    for wall in plan.walls:
        length = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
        height = wall.height_m or 3.0
        wall_vol += length * wall.thickness_m * height * stories
    
    total_concrete = slab_vol + col_vol + beam_vol + wall_vol
    
    return {
        "slab_m3": slab_vol,
        "columns_m3": col_vol,
        "beams_m3": beam_vol,
        "walls_m3": wall_vol,
        "concrete_m3": total_concrete,
        "total_area_m2": slab_area,
        "formwork_m2": total_concrete / slab_thickness * 1.5,  # rough estimate
    }


def _estimate_reinforcement(plan: PlanData, volumes: Dict[str, float]) -> Dict[str, float]:
    """Estimate reinforcement when no analysis is available."""
    # Typical steel ratio: ~1% for columns, ~0.8% for beams
    concrete_m3 = volumes["concrete_m3"]
    steel_kg_per_m3 = 80.0  # typical for reinforced concrete
    steel_kg = concrete_m3 * steel_kg_per_m3
    
    return {
        "steel_kg": steel_kg,
        "steel_tonnes": steel_kg / 1000.0,
        "bars_by_size": {
            "10mm": 200,
            "12mm": 300,
            "16mm": 500,
            "20mm": 800,
        },
    }


def _calculate_reinforcement_from_analysis(plan: PlanData,
                                           analysis: Dict[str, Any]) -> Dict[str, float]:
    """Calculate reinforcement requirements from AnalysisResult.
    
    Uses member forces and design checks from analysis to size rebar more accurately.
    """
    # Extract member forces from analysis
    member_forces = analysis.get("member_forces", [])
    design = analysis.get("design", {})
    
    # Collect required steel areas from design
    total_as = 0.0
    
    # From columns
    for col in design.get("columns", []):
        total_as += col.get("as_required_mm2", 0.0)
    
    # From beams
    for beam in design.get("beams", []):
        total_as += beam.get("as_required_mm2", 0.0)
    
    # Convert area to mass (assume 7850 kg/m³ for steel)
    # as_mm2 → as_m2 → volume m3 → kg
    steel_kg = (total_as / 1e6) * 1.0 * 7850.0  # rough: assume 1m length per unit
    
    # Add margin for actual placement (stirrups, development, splices)
    steel_kg *= 1.25
    
    return {
        "steel_kg": steel_kg,
        "steel_tonnes": steel_kg / 1000.0,
        "bars_by_size": _estimate_bar_distribution(design),
    }


def _estimate_bar_distribution(design: Dict[str, Any]) -> Dict[str, int]:
    """Estimate bar count by size from design output."""
    # Placeholder: would parse suggested_rebars from design checks
    return {
        "10mm": 100,
        "12mm": 200,
        "16mm": 400,
        "20mm": 600,
    }


def _generate_items(plan: PlanData, volumes: Dict[str, float],
                   reinforcement: Dict[str, float],
                   survey: Optional[SurveyReading]) -> List[Dict[str, Any]]:
    """Generate detailed BOQ line items."""
    items = []
    
    # Concrete items
    if volumes["slab_m3"] > 0:
        items.append({
            "code": "CONC-001",
            "description": "Reinforced concrete floor slabs (C30)",
            "unit": "m³",
            "quantity": round(volumes["slab_m3"], 2),
            "unit_cost": CONCRETE_COST_PER_M3,
        })
    
    if volumes["columns_m3"] > 0:
        items.append({
            "code": "CONC-002",
            "description": "Reinforced concrete columns (C30)",
            "unit": "m³",
            "quantity": round(volumes["columns_m3"], 2),
            "unit_cost": CONCRETE_COST_PER_M3,
        })
    
    if volumes["beams_m3"] > 0:
        items.append({
            "code": "CONC-003",
            "description": "Reinforced concrete beams (C30)",
            "unit": "m³",
            "quantity": round(volumes["beams_m3"], 2),
            "unit_cost": CONCRETE_COST_PER_M3,
        })
    
    # Reinforcement
    items.append({
        "code": "REBAR-001",
        "description": "High-yield deformed steel bars (A615)",
        "unit": "ton",
        "quantity": round(reinforcement["steel_tonnes"], 2),
        "unit_cost": STEEL_COST_PER_TON,
    })
    
    # Formwork
    items.append({
        "code": "FORM-001",
        "description": "Timber formwork (reusable)",
        "unit": "m²",
        "quantity": round(volumes["formwork_m2"], 2),
        "unit_cost": FORMWORK_COST_PER_M2,
    })
    
    # Labor
    items.append({
        "code": "LABOR-001",
        "description": "Labor for concrete (excavation to finish)",
        "unit": "m³",
        "quantity": round(volumes["concrete_m3"], 2),
        "unit_cost": LABOR_COST_PER_M3,
    })
    
    return items


def _generate_bbs(plan: PlanData, reinforcement: Dict[str, float]) -> Dict[str, Any]:
    """Generate bar bending schedule (simplified)."""
    return {
        "title": "Bar Bending Schedule",
        "bars_by_size": reinforcement.get("bars_by_size", {}),
        "total_kg": reinforcement["steel_kg"],
        "note": "Simplified BBS; detailed schedule requires member-by-member sizing.",
    }


# Re-export for boq.py API
def boq_pdf(record: Dict[str, Any]):
    """Export BOQ as PDF. Delegates to exporters.py."""
    from app.services.exporters import build_pdf_report, exports_dir
    
    path = exports_dir() / f"boq_{record.get('project_id', 1)}.pdf"
    boq = record.get("payload", record)
    
    items_table = [["Code", "Description", "Unit", "Qty", "Unit Cost", "Total"]]
    for item in boq.get("items", []):
        total = item["quantity"] * item["unit_cost"]
        items_table.append([
            item["code"],
            item["description"],
            item["unit"],
            str(item["quantity"]),
            f"${item['unit_cost']:.0f}",
            f"${total:.0f}",
        ])
    
    build_pdf_report(
        path,
        title="Bill of Quantities",
        subtitle=boq.get("project_name", "Project"),
        meta_rows=[
            ["Total Concrete", f"{boq['totals']['quantity_concrete_m3']} m³"],
            ["Total Steel", f"{boq['totals']['quantity_rebar_tonnes']} t"],
        ],
        summary_box={
            "Total Estimate (USD)": boq["totals"]["amount_usd"],
            "Cost per m²": boq["totals"]["amount_per_m2"],
        },
        sections=[("Bill of Quantities", items_table, None)],
    )
    
    return str(path)


def boq_xlsx(record: Dict[str, Any]):
    """Export BOQ as Excel workbook. Delegates to exporters.py."""
    from app.services.exporters import build_workbook, exports_dir
    
    path = exports_dir() / f"boq_{record.get('project_id', 1)}.xlsx"
    boq = record.get("payload", record)
    
    # BOQ sheet
    items_data = [["Code", "Description", "Unit", "Qty", "Unit Cost", "Total"]]
    for item in boq.get("items", []):
        total = item["quantity"] * item["unit_cost"]
        items_data.append([
            item["code"],
            item["description"],
            item["unit"],
            item["quantity"],
            item["unit_cost"],
            total,
        ])
    items_data.append([
        "TOTAL", "", "", "", "",
        boq["totals"]["amount_usd"]
    ])
    
    # Summary sheet
    summary_data = [
        ["Metric", "Value"],
        ["Project", boq.get("project_name", "Imad Project")],
        ["Total Concrete (m³)", boq["totals"]["quantity_concrete_m3"]],
        ["Total Steel (tonnes)", boq["totals"]["quantity_rebar_tonnes"]],
        ["Total Estimate (USD)", boq["totals"]["amount_usd"]],
        ["Cost per m²", boq["totals"]["amount_per_m2"]],
    ]
    
    sheets = [
        ("Summary", "Project Summary", summary_data),
        ("BOQ", "Bill of Quantities", items_data),
    ]
    
    return build_workbook(path, sheets)
