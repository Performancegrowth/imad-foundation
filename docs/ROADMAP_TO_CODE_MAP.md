# Roadmap → Code Integration Map

This document connects each roadmap item (1-25) to:
1. Which Sprints it touches (0-14)
2. Which files need changes
3. What the API contract looks like
4. What data flows through

---

## Phase 0: Quick Wins (Week 1)

### #1: Fix dead "Read post" buttons on BlogWorkspace
- **Sprints touched**: 9 (frontend only)
- **Files to change**:
  - `frontend/app/src/views/BlogWorkspace.jsx` → add onClick handlers
  - `frontend/app/src/api.js` → add `getPost(id)`, `listPosts()` endpoints
  - `backend/app/api/platform.py` → add GET `/blogs`, GET `/blogs/{id}`
- **Data flow**: BlogWorkspace component → api.js → /api/v1/blogs/{id} → return blog metadata + content
- **Effort**: 30 min

---

### #2: Add 2-3 real case studies (replace static)
- **Sprints touched**: 9 (content + frontend)
- **Files to change**:
  - `frontend/app/src/views/CaseStudiesWorkspace.jsx` → fetch from API
  - `backend/app/api/platform.py` → POST/GET `/case-studies`
  - `database/schema.sql` → add `case_studies` table if not exists
- **Data flow**: CaseStudiesWorkspace → /api/v1/case-studies → queries DB
- **Effort**: 2 hrs (mostly content, not code)

---

### #3: Add Pint for unit-safe calculations ✅ DONE
- **Sprints touched**: 0, 5, 7, 8, 10 (all calculation layers)
- **Already done**: In `backend/requirements.txt` (line 75: `pint>=0.24`)
- **Current usage**: `backend/app/core/units.py` (referenced in docstring)
- **What's missing**: NOT IMPORTED ANYWHERE YET
- **Files to change**:
  - `backend/app/services/structural_engine.py` (line 1-30) → add `from pint import UnitRegistry`
  - `backend/app/services/concrete_design.py` → wrap all calculations in Pint quantities
  - `backend/app/services/boq_generator.py` → use Pint for material quantities
  - `backend/app/services/carbon_calculator.py` → use Pint for CO₂ calculations
  - `backend/app/core/units.py` → define shared UnitRegistry + conversions
- **Data flow**: 
  ```python
  from pint import UnitRegistry
  ureg = UnitRegistry()
  
  # Instead of:
  moment_kNm = w * span * span / 8.0
  
  # Do:
  w_kpa = 2.5 * ureg.kPa  # live load
  span = 6.0 * ureg.meter
  moment = (w_kpa * span**2 / 8).to(ureg.kN * ureg.meter)
  ```
- **Effort**: 3 days (refactor 5 service modules)

---

### #4: Fix NoProject hook inconsistency across views
- **Sprints touched**: 1 (project scoping)
- **Files to change**:
  - `frontend/app/src/useProjectId.jsx` → consistent hook implementation
  - `frontend/app/src/views/*.jsx` → all workspace views use same hook
  - `frontend/app/src/App.jsx` (line 49-54) → centralize `currentPid()` logic
- **Data flow**: All views → useProjectId() → check localStorage + fallback to project 1
- **Effort**: 2 hrs

---

## Phase 1: Foundation (Week 2-3)

### #5: Integrate IfcOpenShell — BIM/IFC import ✅ PARTIALLY DONE
- **Sprints touched**: 1, 2, 12
- **Already exists**:
  - `backend/requirements.txt` (optional, line ~47: `# ifcopenshell>=0.7`)
  - `backend/app/services/bim_service.py` → `import_ifc()`, `export_ifc()`
  - `backend/app/api/collaboration.py` (line 51-87) → POST/DELETE `/ifc/import`, `/ifc/export`
- **What's missing**: 
  - IfcOpenShell NOT in active requirements (commented out)
  - No real-world testing with Revit/ArchiCAD exports
  - IFC → PlanData conversion incomplete (needs bounding boxes, spatial relationships)
- **Files to change**:
  - `backend/requirements.txt` → uncomment `ifcopenshell>=0.7`
  - `backend/app/services/bim_service.py` → expand `import_ifc()` to extract:
    ```python
    def import_ifc(file_path: str) -> PlanData:
        import ifcopenshell
        ifc_file = ifcopenshell.open(file_path)
        
        # Extract walls, columns, beams, grids from IfcWallStandardCase, etc.
        walls = [Wall(...) for wall in ifc_file.by_type('IfcWallStandardCase')]
        columns = [Column(...) for col in ifc_file.by_type('IfcColumn')]
        beams = [Beam(...) for beam in ifc_file.by_type('IfcBeam')]
        
        return PlanData(walls=walls, columns=columns, beams=beams, ...)
    ```
  - `backend/app/api/collaboration.py` → add POST `/ifc/validate` (check conversion quality)
- **Data flow**: 
  ```
  User uploads .ifc file
    → POST /api/v1/ifc/import
    → IfcOpenShell extracts geometry
    → Returns PlanData + counts
    → Frontend shows extraction preview
  ```
- **Effort**: 1 week (real-world testing with Revit files is the blocker)

---

### #6: Add Shapely for 2D geometry processing ✅ PARTIALLY DONE
- **Sprints touched**: 5, 10, 12
- **Already exists**:
  - `backend/requirements.txt` (line 36: `shapely>=2.0`)
  - `backend/app/services/geometry_utils.py` → uses Shapely for `merge_collinear_walls()`, `floor_envelope()`, etc.
  - Functions like `derive_rooms()`, `enrich_plan()` already implemented
- **What's missing**:
  - Not called from API routes yet
  - No validation of wall/column/beam geometry before analysis
  - No room detection visualization
- **Files to change**:
  - `backend/app/api/analysis.py` (line 59-107) → add geometry validation before analyze:
    ```python
    def run_analysis(data):
        plan = _resolve_plan(request)
        
        # NEW: Validate and enrich
        from app.services.geometry_utils import enrich_plan
        warnings = enrich_plan(plan)  # detects overlaps, missing info
        if warnings:
            log.warning("Plan geometry issues: %s", warnings)
        
        result = _engine.analyze(plan, survey, request.options)
    ```
  - `frontend/app/src/components/PlanViewer.jsx` → render room detection results
- **Data flow**: PlanData → geometry validation → AnalysisResult (with warnings)
- **Effort**: 2 days

---

### #7: Build Section Designer with sectionproperties ✅ PARTIALLY DONE
- **Sprints touched**: 5, 7
- **Already exists**:
  - `backend/app/api/sections.py` (full router)
  - `backend/app/services/section_designer.py` → MATERIALS dict, beam/column design
  - sectionproperties referenced but optional (commented in requirements)
- **What's missing**:
  - sectionproperties NOT activated (too heavy; requires scipy + meshing)
  - Fallback to closed-form calculations (exact formulas for rect beams) is in place
  - No UI workspace for section designer
- **Files to change**:
  - `frontend/app/src/views/SectionDesignerWorkspace.jsx` → NEW COMPONENT
  - `frontend/app/src/App.jsx` → add route for section designer
  - `backend/app/requirements.txt` → optional install guide for sectionproperties
  - `backend/app/api/sections.py` → enhance POST `/sections/design` to return I, A, J, etc.
- **Data flow**: 
  ```
  SectionDesignerWorkspace
    → User inputs beam width/depth/material
    → POST /api/v1/sections/design
    → Returns moment capacity, shear capacity, deflection limits
    → UI shows visualization (2D cross-section)
  ```
- **Effort**: 3 days

---

### #8: Enhance PlanViewer to render IFC geometry ✅ PARTIALLY DONE
- **Sprints touched**: 2, 12
- **Already exists**:
  - `frontend/app/src/components/PlanViewer.jsx` → Canvas 2D drawing
  - `frontend/app/src/planUtil.js` → shared drawing pipeline (walls, beams, columns, grids)
  - IFC import endpoint exists
- **What's missing**:
  - No visual feedback when IFC geometry is extracted
  - PlanViewer doesn't re-render after IFC import
  - No geometry correction workflow (snap walls, merge columns, etc.)
- **Files to change**:
  - `frontend/app/src/components/PlanViewer.jsx` → add mode: "edit" mode for geometry fixing
  - `frontend/app/src/views/CadWorkspace.jsx` → after IFC import, show PlanViewer with editable geometry
  - `frontend/app/src/planUtil.js` → add snap-to-grid, merge-columns helpers
- **Data flow**: IFC import → PlanData → PlanViewer renders it → user can edit
- **Effort**: 2 days

---

## Phase 2: Core Engineering (Week 4-6)

### #9: Integrate structuralcodes — full ACI/Eurocode ⚠️ PARTIAL
- **Sprints touched**: 5, 10
- **Current state**:
  - ACI 318 hardcoded in `backend/app/services/concrete_design.py`
  - SBC 304 hardcoded in `backend/app/services/compliance_engine.py`
  - No abstraction for swappable codes
- **What's missing**:
  - structuralcodes library (Python package) NOT in requirements
  - No Eurocode 2 support
  - No dynamic code selection per project
- **Files to change**:
  - `backend/requirements.txt` → add `structuralcodes` (if it exists; may need custom wrapper)
  - `backend/app/core/config.py` → add `DESIGN_STANDARD` env var (default: "ACI 318-19")
  - `backend/app/services/concrete_design.py` → refactor into code-agnostic:
    ```python
    class ConcreteDesigner:
        def __init__(self, code_standard: str = "ACI 318-19"):
            if code_standard == "ACI 318-19":
                self.code = ACIDesigner()
            elif code_standard == "SBC 304":
                self.code = SBCDesigner()
            elif code_standard == "EC2":
                self.code = EurocodeDesigner()
        
        def design(self, member: Member) -> DesignResult:
            return self.code.design(member)
    ```
  - `backend/app/api/analysis.py` (line 59) → pass `code_standard` from project:
    ```python
    # Get project design standard
    design_standard = db.execute(
        text("SELECT design_standard FROM projects WHERE id = :id"),
        {"id": request.project_id}
    ).scalar()
    
    result = _engine.analyze(plan, survey, {
        **request.options,
        "code_standard": design_standard
    })
    ```
  - `backend/app/services/structural_engine.py` → pass code to concrete_design
- **Data flow**: Project.design_standard → API → structural_engine → concrete_design → code-specific checks
- **Effort**: 1 week (biggest effort: creating EurocodeDesigner class)

---

### #10: Add Explainable AI — cite code clauses in outputs
- **Sprints touched**: 5, 9, 10
- **Current state**:
  - AnalysisResult returns JSON (no explanations)
  - Ollama is available for AI narrative (generative.py line 114-131)
  - ComplianceEngine returns clause names but no full text
- **What's missing**:
  - No citation links to code sections
  - No step-by-step calculation narrative
  - Outputs are opaque (user can't see why a member failed)
- **Files to change**:
  - `backend/app/services/structural_engine.py` → add explanation layer:
    ```python
    @dataclass
    class MemberForce:
        # ... existing fields ...
        explanation: Optional[str] = None  # e.g., "Per ACI 318-19 §7.6.1.1, max deflection = L/240"
        code_references: List[str] = Field(default_factory=list)  # ["ACI 318-19 §7.6.1.1", ...]
    ```
  - `backend/app/services/concrete_design.py` → add cite() function:
    ```python
    def cite(code: str, section: str, text: str) -> str:
        return f"{text} (per {code} §{section})"
    ```
  - `backend/app/api/analysis.py` → after analysis, call Ollama to generate narrative:
    ```python
    async def _generate_narrative(result: AnalysisResult) -> str:
        prompt = f"""
        A structural analysis produced these results: {result.summary}.
        Explain in plain English what each number means and which code rules govern it.
        Cite specific sections (e.g., "ACI 318-19 §7.6.1.1").
        """
        narrative = await ollama_provider.chat(prompt)
        return narrative
    ```
  - `frontend/app/src/views/AnalysisWorkspace.jsx` → display explanation + citations
- **Data flow**: AnalysisResult → Ollama narrative + citations → AnalysisWorkspace UI
- **Effort**: 3 days

---

### #11: Enhance AnalysisWorkspace with code-compliant design ✅ DONE
- **Sprints touched**: 5
- **Current state**:
  - AnalysisWorkspace exists and works
  - Returns full AnalysisResult (forces, moments, deflection)
  - Concrete design integrated
  - ComplianceEngine runs checks
- **What's missing**: Just needs #9 (structuralcodes) to be swappable
- **Files to change**: None (depends on #9)
- **Effort**: 0 (done)

---

### #12: Add brightway2 for scientifically valid LCA ⚠️ NOT NEEDED YET
- **Sprints touched**: 8
- **Current state**:
  - `backend/app/services/carbon_calculator.py` exists (simplified embodied-carbon calcs)
  - Uses basic material factors (GGBS, recycled steel multipliers)
  - No lifecycle modeling (cradle-to-gate, end-of-life, etc.)
- **Why not now**: brightway2 adds 50MB+ deps; carbon_calculator.py works well enough for MVP
- **Files to change** (later):
  - `backend/requirements.txt` → add `brightway2>=2.4`
  - `backend/app/services/carbon_calculator.py` → wrap in LCA framework
  - `backend/app/api/sustainability.py` → add `/carbon-report/lifecycle` endpoint
- **Data flow**: BOQ → brightway2 LCA → carbon report with lifecycle stages
- **Effort**: 3 days (when you want full LCA)

---

## Phase 3: KILLER FEATURE — Municipal Submission (Week 7-10)

### #13: Get 3 real SBC 304 submission PDFs from engineers
- **Sprints touched**: 0, 10
- **Current state**: None
- **What you need**:
  - 3 anonymized real SBC 304 submission PDFs from Saudi engineers
  - Screenshots of: project info page, structural drawings page, calculations page, compliance page, seal/signature page
  - Template structure (headers, footers, logos, stamp block layout)
- **Why this matters**: #15 (PDF generator) depends on this template
- **Action**: **BLOCKERS REMOVED — go ask 3 structural engineers for templates**
- **Effort**: 1 week (sourcing, not coding)

---

### #14: Integrate ReportLab for PDF generation ✅ DONE
- **Sprints touched**: 7, 10, 15
- **Already done**:
  - `backend/requirements.txt` (line 61: `reportlab>=4.0`)
  - Used in `backend/app/services/exporters.py` (boq_pdf, lca_pdf functions exist)
- **Effort**: 0 (done)

---

### #15: Build SBC Submission PDF generator 🚨 BLOCKING
- **Sprints touched**: 5, 10, 15
- **Current state**:
  - No `/api/v1/submission/generate` endpoint
  - No PDF template for SBC 304 submission
  - No docstore("submissions") collection
- **What needs to happen**:
  - `backend/app/api/governance.py` (expand Sprint 10 router):
    ```python
    class SubmissionRequest(BaseModel):
        project_id: int
        analysis_result_id: str        # from Sprint 5 /analyze
        compliance_result_id: str      # from Sprint 10 /compliance/check
        engineer_name: str
        seal_id: Optional[str] = None
        signature_image: Optional[str] = None  # base64
    
    @router.post("/submission/generate", summary="Generate SBC 304 submission package")
    async def generate_submission(payload: SubmissionRequest) -> Dict[str, Any]:
        # 1. Load analysis_result from storage
        analysis = load_result(payload.analysis_result_id)
        
        # 2. Load compliance_result from storage
        compliance = load_result(payload.compliance_result_id)
        
        # 3. Build PDF from template (ReportLab)
        #    - Page 1: Project info + municipality header
        #    - Page 2: Structural drawings (2D + 3D screenshots)
        #    - Page 3-5: Hand calculations (forces, design, code checks)
        #    - Page 6: Compliance matrix (all SBC 304 checks)
        #    - Page 7: Material certs + engineer seal block
        
        from app.services.exporters import submission_pdf
        path = submission_pdf(
            project=db.query(projects).get(payload.project_id),
            analysis=analysis,
            compliance=compliance,
            engineer_name=payload.engineer_name,
            seal_image=payload.signature_image
        )
        
        # 4. Store in docstore
        doc = collection("submissions").put({
            "project_id": payload.project_id,
            "analysis_result_id": payload.analysis_result_id,
            "compliance_result_id": payload.compliance_result_id,
            "file_path": path,
            "status": "draft",
            "engineer": payload.engineer_name,
            "created_at": datetime.now().isoformat(),
        }, prefix="sub")
        
        return {
            "submission_id": doc["id"],
            "file": path,
            "status": "draft",
            "download_url": f"/api/v1/exports/download?path={path}"
        }
    ```
  
  - `backend/app/services/exporters.py` (NEW FUNCTION):
    ```python
    def submission_pdf(project, analysis, compliance, engineer_name, seal_image=None):
        """Render SBC 304 submission PDF using ReportLab template."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        
        path = f"{exports_dir()}/submission_{project.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        c = canvas.Canvas(path, pagesize=A4)
        
        # Page 1: Project Info
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "SBC 304 STRUCTURAL SUBMISSION")
        c.drawString(50, 720, f"Project: {project.name}")
        c.drawString(50, 700, f"Engineer: {engineer_name}")
        c.drawString(50, 680, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        # Page 2: Structural Drawings (placeholder — user uploads screenshots)
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 750, "STRUCTURAL DRAWINGS")
        # Insert 2D/3D images here (from analysis["image"] if available)
        
        # Page 3-5: Calculations
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 750, "STRUCTURAL ANALYSIS & DESIGN")
        
        # Extract from analysis.get("summary")
        for i, member in enumerate(analysis.get("member_forces", [])[:10]):
            y = 700 - i * 30
            c.setFont("Helvetica", 10)
            c.drawString(50, y, 
                f"{member['element_id']}: M={member['moment_kNm']} kNm, "
                f"V={member['shear_kN']} kN, Δ={member['deflection_mm']} mm")
        
        # Page 6: Compliance Matrix
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 750, "CODE COMPLIANCE CHECKS (SBC 304)")
        
        for i, check in enumerate(compliance.get("checks", [])[:8]):
            y = 700 - i * 40
            status_symbol = "✓" if check["status"] == "pass" else "✗"
            c.setFont("Helvetica", 9)
            c.drawString(50, y, f"{status_symbol} {check['check_name']}")
            c.drawString(70, y-15, f"Status: {check['status']} | {check['details'].get('clause', '')}")
        
        # Page 7: Seal & Signature
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 750, "ENGINEER'S CERTIFICATION")
        c.drawString(50, 700, f"Name: {engineer_name}")
        if seal_image:
            # Draw base64 seal image
            c.drawString(50, 600, "[SEAL IMAGE]")
        c.drawString(50, 550, "Date: _____________")
        c.drawString(50, 530, "Signature: _____________")
        
        c.save()
        return path
    ```

  - `backend/app/core/docstore.py` → ensure `collection("submissions")` exists
  
  - `frontend/app/src/views/ReviewWorkspace.jsx` → add submission generation UI:
    ```jsx
    async function generateSubmission() {
      const payload = {
        project_id: activeProject,
        analysis_result_id: analysisId,  // from /analyze
        compliance_result_id: complianceId,  // from /compliance/check
        engineer_name: user.full_name,
        signature_image: signaturePNG,  // captured from canvas
      }
      const { submission_id, file } = await api.generateSubmission(payload)
      // Show "Download PDF" button
    }
    ```

- **Data flow**:
  ```
  AnalysisWorkspace
    → click "Review & Submit"
    → ReviewWorkspace loads analysis + compliance results
    → user enters engineer name + uploads signature
    → POST /api/v1/submission/generate
    → ReportLab renders PDF from template
    → PDF stored in docstore("submissions")
    → User sees download button
  ```

- **Effort**: 1 week (ReportLab template building is iterative)

---

### #16: Add submission tracking dashboard ✅ DONE
- **Sprints touched**: 10, 12
- **Implemented**: dual-mode `GET /submission/{ref}` — a numeric id lists a project's
  submissions (sorted newest-first), any other id returns one submission's details;
  `POST /submission/{submission_id}/status` records municipality-side transitions
  (`generated → submitted → under_review → …`) appended as auditable `tracking` events;
  `status` + `tracking` are stamped at both record-creation sites. Submissions table in
  `GovernanceWorkspace.jsx`, client functions in `platformApiOps.js`. Note: the original
  sketch's two routes (`{project_id}` int vs `{submission_id}` str) would shadow each
  other in FastAPI, so they were merged into the one dual-mode route.
- **Files to change**:
  - `backend/app/api/governance.py` (expand):
    ```python
    @router.get("/submission/{project_id}", summary="List submissions for a project")
    async def list_submissions(project_id: int) -> Dict[str, Any]:
        docs = collection("submissions").list(
            lambda d: d.get("project_id") == project_id
        )
        return {
            "submissions": sorted(docs, key=lambda d: d.get("created_at", ""), reverse=True)
        }
    
    @router.get("/submission/{submission_id}", summary="Get submission details")
    async def get_submission(submission_id: str) -> Dict[str, Any]:
        doc = collection("submissions").get(submission_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Submission not found")
        return doc
    ```
  
  - `frontend/app/src/views/GovernanceWorkspace.jsx` → add Submissions tab:
    ```jsx
    export default function GovernanceWorkspace() {
      const [submissions, setSubmissions] = useState([])
      
      useEffect(() => {
        async function loadSubmissions() {
          const { submissions } = await api.getSubmissions(projectId)
          setSubmissions(submissions)
        }
        loadSubmissions()
      }, [projectId])
      
      return (
        <div>
          <h2>Municipal Submissions</h2>
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Created</th>
                <th>Engineer</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map(sub => (
                <tr key={sub.id}>
                  <td>{sub.status}</td>
                  <td>{new Date(sub.created_at).toLocaleDateString()}</td>
                  <td>{sub.engineer}</td>
                  <td>
                    <a href={sub.download_url}>Download PDF</a>
                    <button onClick={() => transitionSubmission(sub.id, 'signed')}>
                      Mark Signed
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }
    ```

- **Effort**: 1-2 days

---

### #17: Add python-docx for Word calculation notes
- **Sprints touched**: 10, 15
- **Files to change**:
  - `backend/requirements.txt` → add `python-docx>=0.8.11`
  
  - `backend/app/services/exporters.py` (NEW FUNCTION):
    ```python
    def submission_docx(analysis, compliance, engineer_name):
        """Generate Word document with detailed calculations."""
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        
        doc = Document()
        
        # Title
        title = doc.add_heading('Structural Analysis & Design Report', 0)
        title.alignment = 1  # center
        
        # Project info
        doc.add_paragraph(f"Engineer: {engineer_name}")
        doc.add_paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        # Member forces table
        doc.add_heading('Member Forces & Moments', 1)
        table = doc.add_table(rows=1, cols=6)
        table.style = 'Light Grid Accent 1'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Member ID'
        hdr_cells[1].text = 'Type'
        hdr_cells[2].text = 'Moment (kNm)'
        hdr_cells[3].text = 'Shear (kN)'
        hdr_cells[4].text = 'Axial (kN)'
        hdr_cells[5].text = 'Deflection (mm)'
        
        for member in analysis.get("member_forces", []):
            row_cells = table.add_row().cells
            row_cells[0].text = member['element_id']
            row_cells[1].text = member['kind']
            row_cells[2].text = str(member['moment_kNm'])
            row_cells[3].text = str(member['shear_kN'])
            row_cells[4].text = str(member['axial_kN'])
            row_cells[5].text = str(member['deflection_mm'])
        
        # Compliance checks
        doc.add_heading('Code Compliance (SBC 304)', 1)
        for check in compliance.get("checks", []):
            status = "✓ PASS" if check["status"] == "pass" else "✗ FAIL"
            doc.add_paragraph(
                f"{status}: {check['check_name']} ({check['details'].get('clause', '')})",
                style='List Bullet'
            )
        
        path = f"{exports_dir()}/submission_{engineer_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        doc.save(path)
        return path
    ```
  
  - `backend/app/api/governance.py`:
    ```python
    @router.post("/submission/{submission_id}/export/docx",
                 summary="Export submission calculations as Word document")
    async def export_submission_docx(submission_id: str) -> Dict[str, Any]:
        sub = collection("submissions").get(submission_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        analysis = load_result(sub["analysis_result_id"])
        compliance = load_result(sub["compliance_result_id"])
        
        from app.services.exporters import submission_docx
        path = submission_docx(analysis, compliance, sub["engineer"])
        
        return {
            "file": path,
            "filename": path.split("/")[-1]
        }
    ```

- **Effort**: 2 days

---

### #18: Add openpyxl for enhanced BOQ Excel export ✅ PARTIALLY DONE
- **Sprints touched**: 7, 15
- **Current state**:
  - `backend/requirements.txt` has `openpyxl>=3.1`
  - `backend/app/services/exporters.py` has `boq_xlsx()` function
  - `backend/app/api/boq.py` (line 108-119) calls it
- **What's missing**:
  - Submission Summary sheet (project info, total cost, total carbon, compliance status)
  - Material certifications sheet
  - Schedule of rates comparison
- **Files to change**:
  - `backend/app/services/exporters.py` → enhance `boq_xlsx()`:
    ```python
    def boq_xlsx(boq_data, submission_id=None):
        # ... existing BOQ sheets ...
        
        if submission_id:
            # Add Submission Summary sheet
            ws_summary = wb.create_sheet("Submission Summary", 0)
            ws_summary['A1'] = "Project"
            ws_summary['B1'] = boq_data.get("project_name", "")
            ws_summary['A2'] = "Total Cost (USD)"
            ws_summary['B2'] = boq_data["totals"]["amount_usd"]
            ws_summary['A3'] = "Total Embodied Carbon (t CO₂e)"
            ws_summary['B3'] = submission["carbon"]["total_co2e_tonnes"]
            ws_summary['A4'] = "Compliance Status"
            ws_summary['B4'] = submission["compliance"]["overall_status"]
    ```

- **Effort**: 1 day

---

## Phase 4: Growth (Week 11-14)

### #19: Arabic-First Engineering NLP (fine-tune Ollama)
- **Sprints touched**: 3, 6, 9, 14
- **Current state**:
  - Ollama is running (Sprint 9, docker-compose.yml line 23-33)
  - Default model: qwen2.5:0.5b (lightweight CPU model)
  - No Arabic-specific fine-tuning
- **What's needed**:
  - Create Ollama Modelfile for Arabic structural engineering
  - Dataset: Arabic technical terms (جدران, أعمدة, كمرات) + code citations (SBC 304 conditions)
  - Fine-tune Ollama model on this dataset
- **Files to change**:
  - `docker-compose.yml` → pull Arabic model:
    ```yaml
    ollama:
      environment:
        - OLLAMA_MODEL=qwen2.5:0.5b  # or arabic-specific variant
    ```
  - `backend/app/services/ai_provider.py` → add Arabic mode:
    ```python
    class OllamaLocalProvider:
        def __init__(self, language: str = "en"):
            self.language = language
            self.model = "qwen2.5:0.5b-ar" if language == "ar" else "qwen2.5:0.5b"
    ```
  - `frontend/app/src/App.jsx` → detect user locale + switch AI language

- **Effort**: 1 week (mostly data preparation + testing)

---

### #20: Live Cost-Carbon-Structural Slider
- **Sprints touched**: 6, 8, 9, 11
- **Current state**:
  - Generative design returns Pareto set (cost, carbon, flexibility trade-offs)
  - UI shows options but no interactive slider
- **What's needed**:
  - Interactive 3-axis slider: cost ↔ carbon ↔ structural efficiency
  - Real-time option recommendation as user drags
  - Visual diff showing material changes per slider position
- **Files to change**:
  - `frontend/app/src/views/GenerativeDesignWorkspace.jsx` → add slider:
    ```jsx
    const [costWeight, setCostWeight] = useState(0.33)
    const [carbonWeight, setCarbonWeight] = useState(0.33)
    const [flexWeight, setFlexWeight] = useState(0.34)
    
    // Normalize weights to sum to 1
    const weights = {
      cost: costWeight / (costWeight + carbonWeight + flexWeight),
      carbon: carbonWeight / (costWeight + carbonWeight + flexWeight),
      flexibility: flexWeight / (costWeight + carbonWeight + flexWeight),
    }
    
    // Score each option
    const scored = options.map(opt => ({
      ...opt,
      score: (weights.cost * opt.fitness.cost +
              weights.carbon * opt.fitness.carbon +
              weights.flexibility * opt.fitness.flexibility)
    }))
    
    // Recommend top option
    const recommended = scored.sort((a, b) => a.score - b.score)[0]
    ```
  - `frontend/app/src/components/CostCarbonSlider.jsx` → NEW COMPONENT

- **Effort**: 1 week (UI interaction + scoring algorithm)

---

### #21: Embedded Contractor Marketplace (real data)
- **Sprints touched**: 13
- **Current state**:
  - `backend/app/api/ecosystem.py` has stubs for `/suppliers`, `/consultants`
  - No real supplier database
  - No rating/review system
- **What's needed**:
  - Seed 10-20 real Saudi contractors/suppliers (concrete, steel, rebar)
  - Add review/rating system
  - Show supplier in BOQ ("Estimated cost from: XYZ Supplier")
- **Files to change**:
  - `database/schema.sql` → add `suppliers` table (if not exists):
    ```sql
    CREATE TABLE suppliers (
      id INTEGER PRIMARY KEY,
      name TEXT,
      category TEXT,  -- concrete, steel, rebar, formwork
      phone TEXT,
      email TEXT,
      region TEXT,    -- Riyadh, Jeddah, etc.
      avg_rating REAL DEFAULT 0.0,
      quote_count INTEGER DEFAULT 0
    );
    ```
  
  - `backend/app/api/ecosystem.py`:
    ```python
    @router.get("/suppliers", summary="List suppliers by category")
    async def list_suppliers(category: Optional[str] = None):
        db = get_session()
        q = db.execute(text("SELECT * FROM suppliers"))
        if category:
            q = q.execute(text("SELECT * FROM suppliers WHERE category = :cat"), {"cat": category})
        return {"suppliers": [dict(row) for row in q.mappings()]}
    ```
  
  - `frontend/app/src/views/BoqWorkspace.jsx` → show supplier options per line item

- **Effort**: 1 week (data sourcing + UI integration)

---

## Phase 5: Future (Week 15+)

### #22: Design Version Control (Git for structures)
### #23: Offline-First PWA with edge AI
### #24: Digital Twin with IoT integration
### #25: Carbon Credit Tokenization

*(Skipping details; these are speculative long-term features)*

---

## Summary: Code Changes Required by Phase

| Phase | Items | Key Files to Touch | Effort |
|-------|-------|-------------------|--------|
| 0 | 1-4 | BlogWorkspace.jsx, useProjectId.jsx, core/units.py | 1 week |
| 1 | 5-8 | bim_service.py, PlanViewer.jsx, collaboration.py | 2-3 weeks |
| 2 | 9-12 | concrete_design.py, compliance_engine.py, carbon_calculator.py | 3 weeks |
| **3** | **13-18** | **exporters.py, governance.py, submission PDF template** | **3-4 weeks** |
| 4 | 19-21 | ai_provider.py, GenerativeDesignWorkspace.jsx, ecosystem.py | 3-4 weeks |
| 5 | 22-25 | (future, no code yet) | ? |

---

## 🎯 What to Do Next (Right Now)

1. **Confirm you have #13** (3 real SBC 304 PDFs from engineers) — this is your blocker
2. **Start #15** (PDF template building) — 3-day sprint
3. **Then #16-18** (tracking + exports) — wraps up Phase 3

Once Phase 3 is **working and used by real engineers**, Phases 4-5 become possible.

**Questions?**
