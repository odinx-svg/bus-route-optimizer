import React, { useRef, useMemo, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Line, Html } from '@react-three/drei';
import * as THREE from 'three';

// Convert lat/lng to 3D coordinates on sphere
function latLngToVector3(lat: number, lng: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);

  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);

  return new THREE.Vector3(x, y, z);
}

// Create arc points between two coordinates
function createArc(start: THREE.Vector3, end: THREE.Vector3, segments: number = 50): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];

  for (let i = 0; i <= segments; i++) {
    const t = i / segments;

    // Spherical interpolation
    const point = new THREE.Vector3().lerpVectors(start, end, t);

    // Lift the arc above the sphere surface
    const altitude = 1 + Math.sin(t * Math.PI) * 0.3;
    point.normalize().multiplyScalar(altitude);

    points.push(point);
  }

  return points;
}

// Earth sphere component
function Earth() {
  const meshRef = useRef<THREE.Mesh>(null);

  // Slow rotation
  useFrame((state, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.05;
    }
  });

  return (
    <Sphere ref={meshRef} args={[1, 64, 64]}>
      <meshStandardMaterial
        color="#1a1a2e"
        wireframe={false}
        roughness={0.8}
        metalness={0.2}
      />
      {/* Grid lines on globe */}
      <Sphere args={[1.001, 32, 32]}>
        <meshBasicMaterial
          color="#39FF14"
          wireframe={true}
          transparent={true}
          opacity={0.1}
        />
      </Sphere>
    </Sphere>
  );
}

// Animated route arc
interface RouteArcProps {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  color?: string;
}

function RouteArc({ startLat, startLng, endLat, endLng, color = "#39FF14" }: RouteArcProps) {
  const start = latLngToVector3(startLat, startLng, 1);
  const end = latLngToVector3(endLat, endLng, 1);
  const points = useMemo(() => createArc(start, end), [startLat, startLng, endLat, endLng]);

  return (
    <Line
      points={points}
      color={color}
      lineWidth={2}
      transparent
      opacity={0.8}
    />
  );
}

// Location marker (dot on globe)
interface MarkerProps {
  lat: number;
  lng: number;
  label?: string;
  color?: string;
}

function Marker({ lat, lng, label, color = "#00D4FF" }: MarkerProps) {
  const position = latLngToVector3(lat, lng, 1.02);

  return (
    <group position={position}>
      <Sphere args={[0.02, 16, 16]}>
        <meshBasicMaterial color={color} />
      </Sphere>
      {/* Glow effect */}
      <Sphere args={[0.03, 16, 16]}>
        <meshBasicMaterial color={color} transparent opacity={0.3} />
      </Sphere>
      {label && (
        <Html distanceFactor={3}>
          <div className="text-xs text-white bg-black/70 px-1 rounded whitespace-nowrap">
            {label}
          </div>
        </Html>
      )}
    </group>
  );
}

// Main Globe Scene
interface GlobeSceneProps {
  routes: Array<{
    origin_lat?: number;
    origin_lng?: number;
    destination_lat?: number;
    destination_lng?: number;
    origin_coords?: { lat: number; lng: number };
    destination_coords?: { lat: number; lng: number };
    route_id?: string;
    name?: string;
  }>;
}

function GlobeScene({ routes }: GlobeSceneProps) {
  // Extract unique locations for markers
  const markers = useMemo(() => {
    const locations = new Map<string, { lat: number; lng: number; label: string }>();

    routes.forEach((route, idx) => {
      const originLat = route.origin_lat ?? route.origin_coords?.lat;
      const originLng = route.origin_lng ?? route.origin_coords?.lng;
      const destLat = route.destination_lat ?? route.destination_coords?.lat;
      const destLng = route.destination_lng ?? route.destination_coords?.lng;

      if (originLat && originLng) {
        const key = `${originLat.toFixed(3)},${originLng.toFixed(3)}`;
        if (!locations.has(key)) {
          locations.set(key, { lat: originLat, lng: originLng, label: `Origin ${idx + 1}` });
        }
      }

      if (destLat && destLng) {
        const key = `${destLat.toFixed(3)},${destLng.toFixed(3)}`;
        if (!locations.has(key)) {
          locations.set(key, { lat: destLat, lng: destLng, label: `Dest ${idx + 1}` });
        }
      }
    });

    return Array.from(locations.values());
  }, [routes]);

  // Generate arcs from routes
  const arcs = useMemo(() => {
    return routes
      .map((route, idx) => {
        const startLat = route.origin_lat ?? route.origin_coords?.lat;
        const startLng = route.origin_lng ?? route.origin_coords?.lng;
        const endLat = route.destination_lat ?? route.destination_coords?.lat;
        const endLng = route.destination_lng ?? route.destination_coords?.lng;

        if (startLat && startLng && endLat && endLng) {
          return {
            id: route.route_id || `route-${idx}`,
            startLat,
            startLng,
            endLat,
            endLng,
            color: idx % 2 === 0 ? "#39FF14" : "#00D4FF"
          };
        }
        return null;
      })
      .filter(Boolean);
  }, [routes]);

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[10, 10, 10]} intensity={1} />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#39FF14" />

      <Earth />

      {/* Route arcs */}
      {arcs.map((arc: any) => (
        <RouteArc
          key={arc.id}
          startLat={arc.startLat}
          startLng={arc.startLng}
          endLat={arc.endLat}
          endLng={arc.endLng}
          color={arc.color}
        />
      ))}

      {/* Location markers */}
      {markers.map((marker, idx) => (
        <Marker
          key={idx}
          lat={marker.lat}
          lng={marker.lng}
          color={idx % 2 === 0 ? "#39FF14" : "#00D4FF"}
        />
      ))}

      <OrbitControls
        enablePan={false}
        enableZoom={true}
        minDistance={1.5}
        maxDistance={4}
        autoRotate={routes.length === 0}
        autoRotateSpeed={0.5}
      />
    </>
  );
}

// Loading fallback
function GlobeLoader() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="text-neon-green animate-pulse">Loading Globe...</div>
    </div>
  );
}

// Main export
interface Globe3DProps {
  routes?: Array<any>;
  className?: string;
}

export function Globe3D({ routes = [], className = "" }: Globe3DProps) {
  return (
    <div className={`relative w-full h-full bg-dark-bg ${className}`}>
      <Suspense fallback={<GlobeLoader />}>
        <Canvas
          camera={{ position: [0, 0, 2.5], fov: 45 }}
          gl={{ antialias: true, alpha: true }}
        >
          <GlobeScene routes={routes} />
        </Canvas>
      </Suspense>

      {/* Overlay info */}
      <div className="absolute bottom-4 left-4 text-xs text-slate-400">
        <span className="text-neon-green">{routes.length}</span> routes loaded
        <br />
        <span className="text-slate-500">Drag to rotate • Scroll to zoom</span>
      </div>
    </div>
  );
}

export default Globe3D;
