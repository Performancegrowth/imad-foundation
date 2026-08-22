import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { getVisualizationData } from '../platformApi.js'

const GREEN = 0x0A5C36
const GOLD = 0xC9A227

export default function Building3DWorkspace() {
  const mountRef = useRef(null)
  const storeRef = useRef(null)
  const [scene, setScene] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState('all')   // all | skeleton | finished
  const [floor, setFloor] = useState('all')

  useEffect(() => {
    let alive = true
    getVisualizationData(1)
      .then((s) => { if (alive) setScene(s) })
      .catch((e) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const env = scene?.envelope ?? scene ?? {}
  const L = Number(env.length_m ?? 20)
  const W = Number(env.width_m ?? 12)
  const N = Math.max(2, Number(env.stories ?? 2))
  const H = Number(env.floor_height ?? 3.2)

  useEffect(() => {
    const mount = mountRef.current; if (!mount) return
    const w = mount.clientWidth || 760, h = mount.clientHeight || 460
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(w, h); renderer.setClearColor(0xf5f7fa)
    mount.appendChild(renderer.domElement)
    const scene3d = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 600)
    scene3d.add(new THREE.HemisphereLight(0xffffff, 0xcccccc, 0.9))
    const sun = new THREE.DirectionalLight(0xffffff, 1); sun.position.set(40, 60, 30); scene3d.add(sun)
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(L * 6, W * 6), new THREE.MeshLambertMaterial({ color: 0xe7ebf1 }))
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.02; scene3d.add(ground)
    scene3d.add(new THREE.GridHelper(Math.max(L, W) * 6, 40, GREEN, 0xc9d2dd))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, (N * H) / 2, 0); controls.enableDamping = true
    camera.position.set(L * 1.4, N * H * 1.1, L * 1.4); controls.update()

    const m = {
      slab: new THREE.MeshLambertMaterial({ color: 0xdfe4ea }),
      col: new THREE.MeshLambertMaterial({ color: GREEN }),
      beam: new THREE.MeshLambertMaterial({ color: GOLD }),
      wall: new THREE.MeshLambertMaterial({ color: 0xffffff }),
      glass: new THREE.MeshLambertMaterial({ color: 0xbfdcf0 }),
      roof: new THREE.MeshLambertMaterial({ color: 0x374151 }),
    }
    const floors = []
    for (let lvl = 0; lvl < N; lvl += 1) {
      const y = lvl * H
      const g = new THREE.Group()
      const slab = new THREE.Mesh(new THREE.BoxGeometry(L + 0.4, 0.18, W + 0.4), m.slab); slab.position.y = y; g.add(slab)
      const cols = [[-L/2, -W/2], [L/2, -W/2], [-L/2, W/2], [L/2, W/2], [0, 0]]
      const colGeo = new THREE.BoxGeometry(0.3, H, 0.3)
      for (const [cx, cz] of cols) { const c = new THREE.Mesh(colGeo, m.col); c.position.set(cx, y + H/2, cz); g.add(c) }
      for (const cz of [-W/2 + 0.4, W/2 - 0.4]) { const b = new THREE.Mesh(new THREE.BoxGeometry(L, 0.3, 0.26), m.beam); b.position.set(0, y + H, cz); g.add(b) }
      for (const cx of [-L/2 + 0.4, L/2 - 0.4]) { const b = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.3, W), m.beam); b.position.set(cx, y + H, 0); g.add(b) }
      const mk = (sx, sz, cx, cz) => { const wl = new THREE.Mesh(new THREE.BoxGeometry(sx, H - 0.5, sz), m.wall); wl.position.set(cx, y + H/2, cz); g.add(wl) }
      mk(L, 0.14, 0, -W/2); mk(L, 0.14, 0, W/2); mk(0.14, W, -L/2, 0); mk(0.14, W, L/2, 0)
      const nWin = Math.max(3, Math.round(L / 4))
      for (let i = 0; i < nWin; i += 1) {
        const x = -L/2 + (L / nWin) * (i + 0.5)
        for (const cz of [-W/2 - 0.02, W/2 + 0.02]) { const win = new THREE.Mesh(new THREE.BoxGeometry(Math.min(1.6, L/nWin - 0.4), 1.2, 0.05), m.glass); win.position.set(x, y + H/2 + 0.3, cz); g.add(win) }
      }
      floors.push(g); scene3d.add(g)
    }
    const roof = new THREE.Mesh(new THREE.BoxGeometry(L + 0.6, 0.25, W + 0.6), m.roof)
    roof.position.y = N * H; scene3d.add(roof)
    storeRef.current = { floors, roof, m }

    const raf = requestAnimationFrame(function loop() { controls.update(); renderer.render(scene3d, camera); requestAnimationFrame(loop) })
    const onResize = () => { const w2 = mount.clientWidth || w, h2 = mount.clientHeight || h; camera.aspect = w2/h2; camera.updateProjectionMatrix(); renderer.setSize(w2, h2) }
    window.addEventListener('resize', onResize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); controls.dispose(); renderer.dispose(); if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [L, W, N, H])

  useEffect(() => {
    const s = storeRef.current; if (!s) return
    const isStructural = (o) => o.material === s.m.col || o.material === s.m.beam || o.material === s.m.slab
    const isSkin = (o) => o.material === s.m.wall || o.material === s.m.glass
    s.floors.forEach((g, i) => g.traverse((o) => {
      if (o.isMesh) { const show = mode === 'all' ? true : mode === 'skeleton' ? isStructural(o) : isSkin(o); o.visible = show && (floor === 'all' || String(i) === floor) }
    }))
    s.roof.visible = mode !== 'skeleton' && (floor === 'all' || String(N - 1) === floor)
  }, [mode, floor, N])

  const floorBtns = ['all', ...Array.from({ length: N }, (_, i) => String(i))]
  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <div className="card-header">
          <h2>3D Building View</h2>
          <span className="badge">{N} storeys · {L}×{W} m</span>
        </div>
        <p className="muted small">Multi-storey structural model with architectural finishes — orbit · pan · zoom.</p>
        <div className="inline-controls wrap">
          <span className="muted small">Mode:</span>
          {[['all', 'Combined'], ['skeleton', 'Structural Skeleton'], ['finished', 'Finished Building']].map(([k, lbl]) => (
            <button key={k} className={`btn small ${mode === k ? 'primary' : ''}`} onClick={() => setMode(k)} aria-pressed={mode === k}>{lbl}</button>
          ))}
          <span className="muted small">Floor:</span>
          {floorBtns.map((f) => (
            <button key={f} className={`btn small ${floor === f ? 'primary' : ''}`} onClick={() => setFloor(f)} aria-pressed={floor === f}>{f === 'all' ? 'All' : `L${Number(f) + 1}`}</button>
          ))}
        </div>
        {loading && <p className="muted">Loading building model…</p>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        <div ref={mountRef} className="viewer-3d" style={{ height: 480 }} role="img" aria-label={`Interactive 3D building, ${N} storeys`} />
        <p className="muted small">Columns in Imad green · beams in gold. Toggle structure vs finished finishes.</p>
      </section>
    </div>
  )
}