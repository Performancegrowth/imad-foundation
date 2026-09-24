import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { getVisualizationData, inspectMember } from '../platformApi.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { useProjectPlan } from '../useProjectPlan'
import { Button, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { WorkflowStepper } from '../components/WorkflowStepper.jsx'
import { LoadingCard, EmptyCard, NextStep } from '../components/ui.jsx'

// Hover tooltip — follows the cursor, names the member + its utilization.
function HoverTip({ tip }) {
  if (!tip) return null
  return (
    <div className="viewer-tip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
      <strong>{tip.element_id}</strong>
      <span> · {tip.kind}{tip.util != null ? ` · util ${(tip.util * 100).toFixed(0)}%` : ''}</span>
    </div>
  )
}

// Click inspector — merged forces + design for the selected member.
function InspectorPanel({ projectId, selection, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!selection || !projectId) return
    let alive = true
    setLoading(true); setError(null); setDetail(null)
    inspectMember(projectId, selection.element_id)
      .then((d) => { if (alive) setDetail(d) })
      .catch((e) => { if (alive) setError(e.message || 'Inspector failed.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [selection, projectId])
  if (!selection) return null
  const d = detail || {}
  const des = d.design || {}
  const rows = selection.kind === 'column'
    ? [
        ['Axial', d.axial_kN != null ? `${d.axial_kN} kN` : '—'],
        ['Capacity φPn', des.phi_pn_kN != null ? `${des.phi_pn_kN} kN` : '—'],
        ['Section', des.section_mm != null ? `${des.section_mm}×${des.section_mm} mm` : '—'],
        ['Rebar', des.arrangement || '—'],
        ['Ties', des.ties || '—'],
      ]
    : selection.kind === 'beam'
      ? [
          ['Moment', d.moment_kNm != null ? `${d.moment_kNm} kN·m` : '—'],
          ['Shear', d.shear_kN != null ? `${d.shear_kN} kN` : '—'],
          ['Capacity φMn', des.phi_mn_kNm != null ? `${des.phi_mn_kNm} kN·m` : '—'],
          ['Section', des.width_mm != null ? `${des.width_mm}×${des.depth_mm} mm` : '—'],
          ['Rebar', des.arrangement || '—'],
          ['Stirrups', des.stirrups || '—'],
          ['Deflection', d.deflection_mm != null ? `${d.deflection_mm} mm` : '—'],
        ]
      : [['Type', 'Non-structural wall']]
  return (
    <div className="viewer-inspector" role="dialog" aria-label={`Member ${selection.element_id}`}>
      <div className="viewer-inspector-head">
        <strong>{selection.element_id}</strong>
        <Badge variant={d.utilization > 1 ? 'fail' : d.utilization > 0.85 ? 'warn' : 'success'}>
          {d.utilization != null ? `util ${(d.utilization * 100).toFixed(0)}%` : selection.kind}
        </Badge>
        <Button size="sm" variant="outline" onClick={onClose} aria-label="Close inspector">✕</Button>
      </div>
      {loading && <p className="muted small">Loading member data...</p>}
      {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      {d && !d.analysis_present && !loading && (
        <p className="muted small">No analysis for this project yet — run Analyze to see forces.</p>
      )}
      <table className="viewer-inspector-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}><th>{k}</th><td className="mono">{v}</td></tr>
          ))}
          {d.load_combo && <tr><th>Governing combo</th><td className="mono">{d.load_combo}</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

// Real building 3D viewer (roadmap #31).
// Two modes:
//   engineer  - utilization heat-map over the real designed structure
//   customer  - clean doll-house view (no forces, no jargon)
// Renders the ACTUAL columns/beams/walls from the plan + analysis, coloured by
// utilization. This replaces the old generic placeholder box building.

export default function Building3DWorkspace() {
  const mountRef = useRef(null)
  const storeRef = useRef(null)
  const [scene, setScene] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState('engineer')   // engineer | customer
  const [floor, setFloor] = useState('all')
  const [selection, setSelection] = useState(null)  // {element_id, kind}
  const [tip, setTip] = useState(null)              // hover tooltip
  const projectId = useProjectId()
  const { plan, loading: planLoading } = useProjectPlan()

  useEffect(() => {
    if (!projectId) return
    let alive = true
    setLoading(true); setError(null)
    getVisualizationData(projectId)
      .then((resp) => {
        if (!alive) return
        const sc = resp.scene || resp
        setScene(sc)
        if (!sc.nodes || sc.nodes.length === 0) {
          setError('No structural geometry \u2014 generate and analyse a plan first.')
        }
      })
      .catch((e) => { if (alive) setError(e.message || 'Could not load 3D scene.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [projectId])

  const nodes = scene?.nodes ?? []
  const stories = Math.max(1, Number(scene?.stories ?? 1))
  const floorHeight = Number(scene?.floor_height ?? 3.0)
  const analysisPresent = !!scene?.analysis_present

  const bounds = scene?.bounds || {}
  const spanX = Math.max((bounds.max_x || 10) - (bounds.min_x || 0), 5)
  const spanZ = Math.max((bounds.max_y || 10) - (bounds.min_y || 0), 5)
  const camDist = Math.max(spanX, spanZ) * 1.6

  useEffect(() => {
    const mount = mountRef.current; if (!mount || !nodes.length) return
    const w = mount.clientWidth || 760, h = mount.clientHeight || 460
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(w, h); renderer.setClearColor(0xf5f7fa)
    mount.appendChild(renderer.domElement)

    const scene3d = new THREE.Scene()
    scene3d.add(new THREE.HemisphereLight(0xffffff, 0xcccccc, 0.85))
    const sun = new THREE.DirectionalLight(0xffffff, 1.0)
    sun.position.set(camDist, camDist * 1.2, camDist); scene3d.add(sun)

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(camDist * 6, camDist * 6),
      new THREE.MeshLambertMaterial({ color: 0xe7ebf1 }))
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.02; scene3d.add(ground)
    scene3d.add(new THREE.GridHelper(Math.max(spanX, spanZ) * 6, 40, 0x0A5C36, 0xc9d2dd))

    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, camDist * 20)
    camera.position.set(camDist, stories * floorHeight * 0.9, camDist)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, (stories * floorHeight) / 2, 0); controls.enableDamping = true

    const mat = (color) => new THREE.MeshLambertMaterial({ color })
    const group = new THREE.Group()
    const meshes = []

    for (const node of nodes) {
      const colorHex = node.color || (node.type === 'cylinder' ? '#0A5C36' : '#C9A227')
      let mesh
      if (node.type === 'cylinder') {
        mesh = new THREE.Mesh(
          new THREE.CylinderGeometry(node.radius, node.radius, node.height, 16),
          mat(parseInt(colorHex.replace('#', ''), 16)))
        mesh.position.set(node.x, node.y, node.z)
      } else {
        mesh = new THREE.Mesh(
          new THREE.BoxGeometry(node.length || 1, node.width || 0.3, node.height || 0.3),
          mat(parseInt(colorHex.replace('#', ''), 16)))
        mesh.position.set(node.x, node.y, node.z)
        mesh.rotation.z = node.rotation_z || 0
      }
      mesh.userData = { element_id: node.element_id, kind: node.kind || node.type, util: node.utilization || 0, floor: node.level ?? 0 }
      group.add(mesh); meshes.push(mesh)
    }
    scene3d.add(group)
    storeRef.current = { group, meshes }

    // Click + hover picking (inspector): meshes carry userData
    // {element_id, kind, util, floor}. Raycast on pointer events.
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    const pickMember = (ev) => {
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1
      raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObjects(meshes.filter((m) => m.visible))
      const obj = hits.length ? hits[0].object : null
      return obj ? { ud: obj.userData, x: ev.clientX - rect.left, y: ev.clientY - rect.top } : null
    }
    const onHover = (ev) => {
      const hit = pickMember(ev)
      if (hit && hit.ud.element_id) {
        setTip({ element_id: hit.ud.element_id, kind: hit.ud.kind, util: hit.ud.util, x: hit.x, y: hit.y })
        renderer.domElement.style.cursor = 'pointer'
      } else {
        setTip(null)
        renderer.domElement.style.cursor = ''
      }
    }
    const onPick = (ev) => {
      const hit = pickMember(ev)
      if (hit && hit.ud.element_id) {
        setSelection({ element_id: hit.ud.element_id, kind: hit.ud.kind })
      }
    }
    renderer.domElement.addEventListener('pointermove', onHover)
    renderer.domElement.addEventListener('click', onPick)

    const raf = requestAnimationFrame(function loop() {
      controls.update(); renderer.render(scene3d, camera); requestAnimationFrame(loop)
    })
    const onResize = () => {
      const w2 = mount.clientWidth || w, h2 = mount.clientHeight || h
      camera.aspect = w2 / h2; camera.updateProjectionMatrix(); renderer.setSize(w2, h2)
    }
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf); window.removeEventListener('resize', onResize)
      renderer.domElement.removeEventListener('pointermove', onHover)
      renderer.domElement.removeEventListener('click', onPick)
      controls.dispose(); renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, stories, floorHeight, camDist, spanX, spanZ])

  // Apply mode + floor filters to the meshes.
  useEffect(() => {
    const s = storeRef.current; if (!s) return
    s.meshes.forEach((mesh) => {
      const ud = mesh.userData
      const floorOk = floor === 'all' || String(ud.floor) === floor
      if (mode === 'customer') {
        mesh.material.color.setHex(0xdfe4ea)
        mesh.visible = floorOk
      } else {
        mesh.material.color.setHex(mesh.material.userData?.origColor || 0xdfe4ea)
        mesh.visible = floorOk
      }
    })
  }, [mode, floor, nodes])

  // Store original colours once after meshes are created.
  useEffect(() => {
    const s = storeRef.current; if (!s) return
    s.meshes.forEach((mesh) => {
      if (!mesh.material.userData) mesh.material.userData = {}
      mesh.material.userData.origColor = mesh.material.color.getHex()
    })
  }, [nodes])

  if (!projectId) return <NoProject />
  if (loading) return <LoadingCard label="Loading building model..." />

  // EMPTY — the scene resolved but carries no structural geometry.
  if (!nodes.length) {
    return (
      <EmptyCard
        title="No 3D geometry yet"
        description={error || 'No structural geometry found. Create a plan, then run the analysis so the model has members to show.'}
        ctaLabel="Go to Create Plan"
        ctaHref="/create-plan"
      />
    )
  }

  const floorBtns = ['all', ...Array.from({ length: stories }, (_, i) => String(i))];

  return (
    <div className="workspace-grid">
      <WorkflowStepper projectId={projectId} currentKey="building3d" />
      <Card className="span-2">
        <CardHeader>
          <CardTitle>3D Building View</CardTitle>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Badge variant="default">{stories} storey{stories > 1 ? 's' : ''} · {nodes.length} elements</Badge>
            {plan && <Badge variant="success">{plan.label || plan.name}</Badge>}
          </div>
        </CardHeader>

        <p className="muted subtitle">
          Visualize the full building model. Check geometry before submission.
        </p>
        <p className="muted small">
          {mode === 'engineer'
            ? 'Real designed structure, coloured by utilisation (green = safe, red = over capacity).'
            : 'Clean doll-house view of your building.'}
        </p>
        <div className="inline-controls wrap">
          <span className="muted small">Audience:</span>
          {[['engineer', 'Engineer'], ['customer', 'Customer']].map(([k, lbl]) => (
            <Button key={k} size="sm" variant={mode === k ? 'primary' : 'outline'}
                    onClick={() => setMode(k)} aria-pressed={mode === k}>{lbl}</Button>
          ))}
          <span className="muted small">Floor:</span>
          {floorBtns.map((f) => (
            <Button key={f} size="sm" variant={floor === f ? 'primary' : 'outline'}
                    onClick={() => setFloor(f)} aria-pressed={floor === f}>
              {f === 'all' ? 'All' : `L${Number(f) + 1}`}
            </Button>
          ))}
        </div>
        {loading && <p className="muted">Loading building model...</p>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        <div className="viewer-wrap" style={{ position: 'relative' }}>
          <div ref={mountRef} className="viewer-3d" style={{ height: 480 }}
               role="img" aria-label={`Interactive 3D building, ${stories} storeys`} />
          <HoverTip tip={tip} />
          <InspectorPanel projectId={projectId} selection={selection} onClose={() => setSelection(null)} />
        </div>
        {mode === 'engineer' && analysisPresent && (
          <p className="muted small">Utilisation heat-map: green &rarr; lime &rarr; yellow &rarr; orange &rarr; red.</p>
        )}
        {mode === 'engineer' && !analysisPresent && (
          <p className="muted small">Run analysis to see utilisation colours.</p>
        )}
      </Card>


      <NextStep nextLabel="Review &amp; Sign" nextHref={`/project/${projectId}/review`} />
    </div>
  )
}
