import { useEffect, useRef } from 'react'
import * as THREE from 'three'

/**
 * Lightweight 3D structural viewer built on Three.js.
 * Renders a simple frame from plan + member forces with colour coding:
 * green = lightly loaded, gold = moderate, red = highly utilized.
 */
export default function StructureViewer({ plan, forces }) {
  const mountRef = useRef(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    let width = mount.clientWidth || 640
    let height = mount.clientHeight || 420
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#F5F7FA')

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000)
    camera.position.set(18, 14, 20)
    camera.lookAt(0, 0, 0)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(window.devicePixelRatio || 1)
    mount.appendChild(renderer.domElement)

    // Ground grid helper
    const grid = new THREE.GridHelper(30, 20, 0xC9A227, 0xC9A227)
    grid.material.opacity = 0.25
    grid.material.transparent = true
    scene.add(grid)

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.7))
    const dir = new THREE.DirectionalLight(0xffffff, 0.9)
    dir.position.set(10, 20, 10)
    scene.add(dir)

    // Axis helper + origin marker
    scene.add(new THREE.AxesHelper(2))

    // Draw columns as vertical boxes at each plan column
    const utilization = new Map((forces || []).filter((f) => f.kind === 'column')
      .map((f) => [f.element_id, f.axial_kN || 0]))

    const colsByCenter = new Map()
    ;(plan.columns || []).forEach((col) => {
      const center = `${Math.round(col.cx)}:${Math.round(col.cy)}`
      colsByCenter.set(center, col)
    })

    const storeyHeight = 3.0
    const stories = Math.max(1, plan.stories || 1)
    const materialFor = (util, fallback) => {
      const u = util || 0
      const color = u > 0.9 ? 0xB42318 : u > 0.6 ? 0xC9A227 : 0x0A5C36
      return new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.1 })
    }

    ;(plan.columns || []).forEach((col, i) => {
      for (let s = 0; s < stories; s++) {
        const size = col.size_m || 0.3
        const geo = new THREE.BoxGeometry(size, size, storeyHeight)
        const util = utilization.get(col.id) || 0
        const mesh = new THREE.Mesh(geo, materialFor(util, 0x0A5C36))
        mesh.position.set(col.cx, s * storeyHeight + storeyHeight / 2, col.cy)
        scene.add(mesh)
      }
    })

    // Draw beams as gold cylinders/boxes between columns per level
    ;(plan.beams || []).forEach((b) => {
      for (let s = 0; s < stories; s++) {
        const dx = b.x2 - b.x1
        const dz = b.y2 - b.y1
        const len = Math.hypot(dx, dz) || 1
        const geo = new THREE.CylinderGeometry(0.12, 0.12, len, 8)
        const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
          color: 0xC9A227, roughness: 0.5, metalness: 0.2,
        }))
        mesh.rotation.x = Math.PI / 2
        mesh.rotation.z = -Math.atan2(dz, dx)
        mesh.position.set((b.x1 + b.x2) / 2, s * storeyHeight + storeyHeight - 0.15, (b.y1 + b.y2) / 2)
        scene.add(mesh)
      }
    })

    // Orbit-like drag
    let isDragging = false
    let prevX = 0
    let prevY = 0
    let azimuth = 0.6
    let elevation = 0.5
    let radius = 26

    const render = () => {
      camera.position.x = radius * Math.cos(elevation) * Math.sin(azimuth)
      camera.position.y = radius * Math.sin(elevation)
      camera.position.z = radius * Math.cos(elevation) * Math.cos(azimuth)
      camera.lookAt(0, storeyHeight / 2, 0)
      renderer.render(scene, camera)
    }

    const onDown = (e) => { isDragging = true; prevX = e.clientX; prevY = e.clientY }
    const onMove = (e) => {
      if (!isDragging) return
      azimuth += (e.clientX - prevX) * 0.01
      elevation = Math.max(0.1, Math.min(1.4, elevation + (e.clientY - prevY) * 0.01))
      prevX = e.clientX
      prevY = e.clientY
      render()
    }
    const onUp = () => { isDragging = false }
    const onWheel = (e) => {
      radius = Math.max(8, Math.min(60, radius + e.deltaY * 0.02))
      render()
    }

    renderer.domElement.addEventListener('mousedown', onDown)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    renderer.domElement.addEventListener('wheel', onWheel)

    const onResize = () => {
      width = mount.clientWidth || 640
      height = mount.clientHeight || 420
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
      render()
    }
    window.addEventListener('resize', onResize)
    render()

    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      window.removeEventListener('resize', onResize)
      renderer.domElement.removeEventListener('mousedown', onDown)
      renderer.domElement.removeEventListener('wheel', onWheel)
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [plan, forces])

  return <div className="viewer-3d" ref={mountRef} style={{ height: 440 }} />
}