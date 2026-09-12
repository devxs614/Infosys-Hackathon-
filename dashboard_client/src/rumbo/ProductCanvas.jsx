import { Float, OrbitControls, Sparkles } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useRef } from 'react'

function FloatingProduct({ color, shape, scrollSpin }) {
  const group = useRef()
  useFrame((_, delta) => { if (group.current) group.current.rotation.y += delta * (.42 + scrollSpin * .008) })
  return <Float speed={2.1} rotationIntensity={.45} floatIntensity={.7}><group ref={group}>
    {shape === 'bowl' && <><mesh rotation-x={-.22}><sphereGeometry args={[1.16, 42, 30, 0, Math.PI * 2, 0, 1.28]} /><meshPhysicalMaterial color={color} roughness={.22} metalness={.15} /></mesh><mesh position={[0, .34, 0]} rotation-x={-.2}><torusGeometry args={[.62, .14, 18, 45]} /><meshStandardMaterial color="#f8fafc" /></mesh></>}
    {shape === 'ramen' && <><mesh><cylinderGeometry args={[1, .86, .72, 42]} /><meshPhysicalMaterial color={color} roughness={.16} metalness={.25} /></mesh><mesh position={[0, .42, 0]}><torusGeometry args={[.78, .08, 16, 48]} /><meshStandardMaterial color="#e2e8f0" /></mesh></>}
    {shape === 'box' && <><mesh rotation={[.18, .22, 0]}><boxGeometry args={[1.52, 1.1, 1.42]} /><meshPhysicalMaterial color={color} roughness={.17} metalness={.32} /></mesh><mesh position={[0, .59, 0]} rotation={[.18, .22, 0]}><boxGeometry args={[1.6, .12, 1.5]} /><meshStandardMaterial color="#f8fafc" /></mesh></>}
  </group></Float>
}

export function ProductCanvas({ product, scrollSpin = 0 }) {
  return <div className="h-56 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-white/[.11] to-transparent sm:h-64">
    <Canvas dpr={[1, 1.8]} camera={{ position: [0, .15, 4.3], fov: 42 }}>
      <ambientLight intensity={1.2} /><pointLight position={[3, 2, 3]} intensity={20} color={product.color} /><pointLight position={[-3, -1, 2]} intensity={9} color="#06b6d4" />
      <FloatingProduct color={product.color} shape={product.shape} scrollSpin={scrollSpin} />
      <Sparkles count={38} speed={.45} size={1.8} color={product.color} scale={4} />
      <OrbitControls enablePan={false} enableZoom={false} autoRotate={false} />
    </Canvas>
  </div>
}
