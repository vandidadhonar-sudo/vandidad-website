import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import * as THREE from 'three'

const LABELS = [
  'AI_OS', 'VANTA_CORE', 'AIOS_ENGINE', 'NEURAL_NET',
  'DECISION_LAYER', 'SALES_AGENT', 'LEGAL_OS', 'CRM_MATRIX',
  'PANAH_AI', 'PROF_P_EDU', 'MEMORY_CORE', 'CONTEXT_MESH',
  'AGENT_PROTOCOL', 'INFERENCE_ENGINE', 'VECTOR_CORE', 'SYNAPSE_GRID',
  'SEMANTIC_LAYER', 'TRANSFORMER_XL', 'KERNEL_OPS', 'TENSOR_FLUX',
]

const NEON = ['#00F2FE', '#A855F7', '#22D3EE', '#818CF8', '#06B6D4', '#C084FC']
const SHARD_COUNT = 20
const CORE_RADIUS = 1.9

function fibSphere(n, r) {
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))
  return Array.from({ length: n }, (_, i) => {
    const y = 1 - (i / (n - 1)) * 2
    const radius = Math.sqrt(1 - y * y)
    const theta = goldenAngle * i
    return new THREE.Vector3(
      Math.cos(theta) * radius * r,
      y * r,
      Math.sin(theta) * radius * r,
    )
  })
}

const rng = (min, max) => min + Math.random() * (max - min)
const easeInOut = (t) =>
  t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2

export default function QuantumCore({ scrollProgress, mousePos }) {
  const groupRef = useRef()
  const coreRef = useRef()
  const ring1Ref = useRef()
  const ring2Ref = useRef()
  const cageRef = useRef()
  const shardRefs = useRef([])

  const shards = useMemo(() => {
    const homes = fibSphere(SHARD_COUNT, CORE_RADIUS)
    return homes.map((pos, i) => {
      const preferredUp =
        Math.abs(pos.clone().normalize().y) > 0.85
          ? new THREE.Vector3(1, 0, 0)
          : new THREE.Vector3(0, 1, 0)
      const homeRot = new THREE.Euler().setFromQuaternion(
        new THREE.Quaternion().setFromRotationMatrix(
          new THREE.Matrix4().lookAt(new THREE.Vector3(), pos, preferredUp),
        ),
      )
      const explodePos = new THREE.Vector3(
        pos.x * 2.5 + rng(-0.9, 0.9),
        pos.y * 2.5 + rng(-0.7, 0.7),
        pos.z * 1.1 + rng(2.5, 5.5),
      )
      return {
        homePos: pos.clone(),
        explodePos,
        homeRot,
        explodeRot: new THREE.Euler(
          rng(-Math.PI, Math.PI),
          rng(-Math.PI, Math.PI),
          rng(-Math.PI, Math.PI),
        ),
        color: NEON[i % NEON.length],
        label: LABELS[i],
        scaleX: rng(0.28, 0.44),
        scaleY: rng(0.28, 0.44),
        scaleZ: rng(0.065, 0.115),
        delay: (i / SHARD_COUNT) * 0.38,
        spinSpeed: rng(0.35, 1.1),
      }
    })
  }, [])

  useFrame((state) => {
    const t = state.clock.elapsedTime
    const scroll = scrollProgress.current

    if (groupRef.current) {
      groupRef.current.rotation.y +=
        (mousePos.current.x * 0.28 - groupRef.current.rotation.y) * 0.06
      groupRef.current.rotation.x +=
        (-mousePos.current.y * 0.22 - groupRef.current.rotation.x) * 0.06
    }

    if (coreRef.current) {
      coreRef.current.scale.setScalar(
        (1 + Math.sin(t * 3.2) * 0.07) * Math.max(0.05, 1 - scroll * 1.6),
      )
      coreRef.current.material.emissiveIntensity = 2.5 + Math.sin(t * 5) * 0.45
    }

    if (ring1Ref.current) {
      ring1Ref.current.rotation.z = t * 0.45
      ring1Ref.current.rotation.x = Math.PI / 2 + Math.sin(t * 0.6) * 0.25
      ring1Ref.current.material.opacity = Math.max(0, 1 - scroll * 2.2)
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.z = -t * 0.28
      ring2Ref.current.material.opacity = Math.max(0, 1 - scroll * 2.8)
    }
    if (cageRef.current) {
      cageRef.current.rotation.y = t * 0.15
      cageRef.current.material.opacity = Math.max(0, 0.5 - scroll * 1.2)
    }

    shards.forEach((d, i) => {
      const mesh = shardRefs.current[i]
      if (!mesh) return
      const raw = Math.max(0, (scroll - d.delay) / (1 - d.delay + 0.001))
      const eased = easeInOut(Math.min(1, raw))
      mesh.position.lerpVectors(d.homePos, d.explodePos, eased)
      mesh.rotation.x = THREE.MathUtils.lerp(d.homeRot.x, d.explodeRot.x, eased)
      mesh.rotation.y =
        THREE.MathUtils.lerp(d.homeRot.y, d.explodeRot.y, eased) +
        t * d.spinSpeed * eased * 0.12
      mesh.rotation.z = THREE.MathUtils.lerp(d.homeRot.z, d.explodeRot.z, eased)
      if (mesh.material) {
        const pulse = Math.sin(t * 2.5 + i * 0.9) * 0.12
        mesh.material.emissiveIntensity = THREE.MathUtils.lerp(
          0.25 + pulse,
          1.1 + pulse * 2,
          eased,
        )
      }
    })
  })

  return (
    <group ref={groupRef}>
      <mesh ref={ring1Ref} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.18, 0.018, 8, 128]} />
        <meshStandardMaterial
          color="#A855F7"
          emissive="#A855F7"
          emissiveIntensity={4}
          transparent
          opacity={1}
        />
      </mesh>

      <mesh ref={ring2Ref} rotation={[Math.PI / 3.5, 0.8, 0]}>
        <torusGeometry args={[1.48, 0.012, 8, 128]} />
        <meshStandardMaterial
          color="#00F2FE"
          emissive="#00F2FE"
          emissiveIntensity={3}
          transparent
          opacity={1}
        />
      </mesh>

      <mesh ref={coreRef}>
        <sphereGeometry args={[0.3, 32, 32]} />
        <meshStandardMaterial
          color="#00F2FE"
          emissive="#00F2FE"
          emissiveIntensity={2.5}
        />
      </mesh>

      <mesh ref={cageRef}>
        <icosahedronGeometry args={[0.75, 1]} />
        <meshStandardMaterial
          color="#38BDF8"
          emissive="#38BDF8"
          emissiveIntensity={0.45}
          wireframe
          transparent
          opacity={0.5}
        />
      </mesh>

      {shards.map((d, i) => (
        <mesh
          key={i}
          ref={(el) => (shardRefs.current[i] = el)}
          position={d.homePos}
          rotation={d.homeRot}
          scale={[d.scaleX, d.scaleY, d.scaleZ]}
        >
          <octahedronGeometry args={[1, 0]} />
          <meshPhysicalMaterial
            color={d.color}
            emissive={d.color}
            emissiveIntensity={0.35}
            metalness={0.85}
            roughness={0.08}
            transparent
            opacity={0.88}
            side={THREE.DoubleSide}
          />
          <Html
            position={[0, 1.5, 0]}
            center
            style={{ pointerEvents: 'none', userSelect: 'none' }}
          >
            <span
              style={{
                display: 'inline-block',
                fontFamily: '"Courier New", Courier, monospace',
                fontSize: '8.5px',
                letterSpacing: '0.14em',
                color: d.color,
                textShadow: `0 0 14px ${d.color}, 0 0 28px ${d.color}60`,
                border: `1px solid ${d.color}55`,
                padding: '2px 6px',
                borderRadius: '2px',
                background: 'rgba(1, 11, 24, 0.72)',
                backdropFilter: 'blur(6px)',
                whiteSpace: 'nowrap',
              }}
            >
              {d.label}
            </span>
          </Html>
        </mesh>
      ))}
    </group>
  )
}
