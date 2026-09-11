import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { getVisualizationData } from '../platformApi.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'

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
  const projectId = useProjectId()

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
      mesh.userData = { kind: node.type, utilization: node.utilization || 0, floor: node.floor || 0 }
      group.add(mesh); meshes.push(mesh)
    }
    scene3d.add(group)
    storeRef.current = { group, meshes }

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

  const floorBtns = ['all', ...Array.from({ length: stories }, (_, i) => String(i))]

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <div className="card-header">
          <h2>3D Building View</h2>
          <span className="badge">{stories} storey{stories > 1 ? 'ies' : 'y'} ( {nodes.length} elements</span>
        </div>
        <p className="muted small">
          {mode === 'engineer'
            ? 'Real designed structure, coloured by utilisation (green = safe, red = over capacity).'
            : 'Clean doll-house view of your building.'}
        </p>
        <div className="inline-controls wrap">
          <span className="muted small">Audience:</span>
          {[['engineer', 'Engineer'], ['customer', 'Customer']].map(([k, lbl]) => (
            <button key={k} className={`btn small ${mode === k ? 'primary' : ''}`}
                    onClick={() => setMode(k)} aria-pressed={mode === k}>{lbl}</button>
          ))}
          <span className="muted small">Floor:</span>
          {floorBtns.map((f) => (
            <button key={f} className={`btn small ${floor === f ? 'primary' : ''}`}
                    onClick={() => setFloor(f)} aria-pressed={floor === f}>
              {f === 'all' ? 'All' : `L${Number(f) + 1}`}
            </button>
          ))}
        </div>
        {loading && <p className="muted">Loading building model...</p>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        <div ref={mountRef} className="viewer-3d" style={{ height: 480 }}
             role="img" aria-label={`Interactive 3D building, ${stories} storeys`} />
        {mode === 'engineer' && analysisPresent && (
          <p className="muted small">Utilisation heat-map: green &rarr; lime &rarr; yellow &rarr; orange &rarr; red.</p>
        )}
        {mode === 'engineer' && !analysisPresent && (
          <p className="muted small">Run analysis to see utilisation colours.</p>
        )}
      </section>
    </div>
  )
}
