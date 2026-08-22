"""Service layer — engineering engine and file-processing interfaces."""
from .cad_processor import (
    CADProcessor,
    EzdxfCADProcessor,
    ImageCADProcessor,
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
from .visualization_service import VisualizationService, ViewportMesh

__all__ = [
    "CADProcessor",
    "EzdxfCADProcessor",
    "ImageCADProcessor",
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
    "VisualizationService",
    "ViewportMesh",
]