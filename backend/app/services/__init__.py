"""Service layer — engineering engine and file-processing interfaces."""
from .cad_processor import (
    CADProcessor,
    EzdxfCADProcessor,
    ImageCADProcessor,
    IfcCADProcessor,
    get_cad_processor,
    CADProcessingError,
)
from .ai_provider import (
    AIProvider,
    OllamaLocalProvider,
    BaseMessage,
    Role,
    AIProviderError,
)
from .noncad_processor import (
    PlanGenerator,
    TEMPLATE_LIBRARY,
    get_template,
    PlanGenerationError,
)
from .survey_processor import (
    SurveyProcessor,
    ManualSurveyProcessor,
    FileSurveyProcessor,
    SurveyError,
)
from .structural_engine import (
    StructuralEngine,
    OpenSeesEngine,
    StructuralError,
    AnalysisResult,
    MemberForce,
)
from .concrete_design import concrete_design, preliminary_boq
from .geometry_utils import (
    SHAPELY_AVAILABLE,
    derive_rooms,
    enrich_plan,
    floor_envelope,
    merge_collinear_walls,
    validation_warnings,
)
from .section_designer import (
    MATERIALS as SECTION_MATERIALS,
    SUPPORTED_SHAPES as SECTION_SHAPES,
    SectionDesigner,
    SectionDesignError,
)
from .visualization_service import VisualizationService, ViewportMesh

__all__ = [
    "CADProcessor",
    "EzdxfCADProcessor",
    "ImageCADProcessor",
    "IfcCADProcessor",
    "get_cad_processor",
    "CADProcessingError",
    "AIProvider",
    "OllamaLocalProvider",
    "BaseMessage",
    "Role",
    "AIProviderError",
    "PlanGenerator",
    "TEMPLATE_LIBRARY",
    "get_template",
    "PlanGenerationError",
    "SurveyProcessor",
    "ManualSurveyProcessor",
    "FileSurveyProcessor",
    "SurveyError",
    "StructuralEngine",
    "OpenSeesEngine",
    "StructuralError",
    "AnalysisResult",
    "MemberForce",
    "concrete_design",
    "preliminary_boq",
    "SHAPELY_AVAILABLE",
    "derive_rooms",
    "enrich_plan",
    "floor_envelope",
    "merge_collinear_walls",
    "validation_warnings",
    "SECTION_MATERIALS",
    "SECTION_SHAPES",
    "SectionDesigner",
    "SectionDesignError",
    "VisualizationService",
    "ViewportMesh",
]