'use client';

import { useRef, useEffect, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF, Environment } from '@react-three/drei';
import * as THREE from 'three';

interface Avatar3DProps {
  modelUrl?: string;
  isSpeaking?: boolean;
  emotion?: 'neutral' | 'happy' | 'thinking' | 'surprised';
  className?: string;
}

function AvatarModel({
  modelUrl,
  isSpeaking,
  emotion,
}: {
  modelUrl?: string;
  isSpeaking?: boolean;
  emotion?: string;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [mouthOpen, setMouthOpen] = useState(0);

  // Simple animation for speaking
  useFrame((state) => {
    if (meshRef.current) {
      // Idle animation - gentle floating
      meshRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.5) * 0.05;

      // Speaking animation - mouth movement
      if (isSpeaking) {
        const newMouthOpen = Math.abs(Math.sin(state.clock.elapsedTime * 8)) * 0.3;
        setMouthOpen(newMouthOpen);
      } else {
        setMouthOpen(0);
      }
    }
  });

  // If no model URL, render a simple avatar
  return (
    <group>
      {/* Head */}
      <mesh ref={meshRef} position={[0, 0.5, 0]}>
        <sphereGeometry args={[0.5, 32, 32]} />
        <meshStandardMaterial color="#8B7355" />
      </mesh>

      {/* Eyes */}
      <mesh position={[-0.15, 0.6, 0.4]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial color="white" />
      </mesh>
      <mesh position={[0.15, 0.6, 0.4]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial color="white" />
      </mesh>

      {/* Pupils */}
      <mesh position={[-0.15, 0.6, 0.47]}>
        <sphereGeometry args={[0.04, 16, 16]} />
        <meshStandardMaterial color="#1a1a1a" />
      </mesh>
      <mesh position={[0.15, 0.6, 0.47]}>
        <sphereGeometry args={[0.04, 16, 16]} />
        <meshStandardMaterial color="#1a1a1a" />
      </mesh>

      {/* Mouth */}
      <mesh position={[0, 0.35, 0.45]} scale={[1, 0.3 + mouthOpen, 1]}>
        <boxGeometry args={[0.2, 0.05, 0.05]} />
        <meshStandardMaterial color="#cc6666" />
      </mesh>

      {/* Body */}
      <mesh position={[0, -0.3, 0]}>
        <cylinderGeometry args={[0.35, 0.4, 0.8, 32]} />
        <meshStandardMaterial color="#4a90d9" />
      </mesh>

      {/* Arms */}
      <mesh position={[-0.5, -0.2, 0]} rotation={[0, 0, 0.5]}>
        <cylinderGeometry args={[0.08, 0.08, 0.5, 16]} />
        <meshStandardMaterial color="#8B7355" />
      </mesh>
      <mesh position={[0.5, -0.2, 0]} rotation={[0, 0, -0.5]}>
        <cylinderGeometry args={[0.08, 0.08, 0.5, 16]} />
        <meshStandardMaterial color="#8B7355" />
      </mesh>
    </group>
  );
}

function Scene({
  modelUrl,
  isSpeaking,
  emotion,
}: {
  modelUrl?: string;
  isSpeaking?: boolean;
  emotion?: string;
}) {
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 5, 5]} intensity={1} />
      <directionalLight position={[-5, 5, -5]} intensity={0.5} />

      <AvatarModel modelUrl={modelUrl} isSpeaking={isSpeaking} emotion={emotion} />

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        minPolarAngle={Math.PI / 3}
        maxPolarAngle={Math.PI / 2}
      />
      <Environment preset="studio" />
    </>
  );
}

export function Avatar3D({
  modelUrl,
  isSpeaking = false,
  emotion = 'neutral',
  className = '',
}: Avatar3DProps) {
  return (
    <div className={`w-full h-full ${className}`}>
      <Canvas
        camera={{ position: [0, 0, 2.5], fov: 50 }}
        style={{ background: 'transparent' }}
      >
        <Scene modelUrl={modelUrl} isSpeaking={isSpeaking} emotion={emotion} />
      </Canvas>
    </div>
  );
}
