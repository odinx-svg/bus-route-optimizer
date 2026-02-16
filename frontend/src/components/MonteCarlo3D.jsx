import { useRef, useMemo, useState } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import * as THREE from 'three';

// Labels de los ejes usando Html
function AxisLabels() {
  return (
    <>
      <Html position={[26, 0, 0]} center>
        <div className="text-white text-xs bg-black/50 px-2 py-1 rounded whitespace-nowrap">
          Desviación Tiempo
        </div>
      </Html>
      <Html position={[0, 26, 0]} center>
        <div className="text-white text-xs bg-black/50 px-2 py-1 rounded whitespace-nowrap">
          Duración Total
        </div>
      </Html>
      <Html position={[0, 0, 16]} center>
        <div className="text-white text-xs bg-black/50 px-2 py-1 rounded whitespace-nowrap">
          Factibilidad
        </div>
      </Html>
    </>
  );
}

// Leyenda en el canvas explicando las dimensiones
function CanvasLegend() {
  return (
    <Html position={[-35, 35, 0]}>
      <div className="bg-black/70 p-3 rounded text-xs text-white border border-white/20">
        <div className="font-bold mb-2 text-sm">📊 Ejes del Gráfico:</div>
        <div className="space-y-1">
          <div><span className="text-red-400 font-bold">X:</span> Desviación de tiempos</div>
          <div><span className="text-green-400 font-bold">Y:</span> Duración del horario</div>
          <div><span className="text-blue-400 font-bold">Z:</span> 0=No factible, 1=Factible</div>
        </div>
        <div className="mt-2 pt-2 border-t border-white/20 text-[10px] text-gray-300">
          <div className="flex items-center gap-1 mb-1">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            Escenarios factibles
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            Escenarios no factibles
          </div>
        </div>
      </div>
    </Html>
  );
}

// Planos de referencia
function ReferencePlanes() {
  return (
    <group>
      {/* Plano en Z=0 (límite factible/no factible) */}
      <mesh position={[0, 0, 0]} rotation={[0, 0, 0]}>
        <planeGeometry args={[80, 80]} />
        <meshBasicMaterial color="#333" transparent opacity={0.15} side={THREE.DoubleSide} />
      </mesh>
      
      {/* Línea divisoria horizontal en Z=0 */}
      <mesh position={[0, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.08, 0.08, 80, 8]} />
        <meshBasicMaterial color="#555" transparent opacity={0.5} />
      </mesh>
      
      {/* Línea divisoria vertical en Z=0 */}
      <mesh position={[0, 0, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.08, 0.08, 80, 8]} />
        <meshBasicMaterial color="#555" transparent opacity={0.5} />
      </mesh>
      
      {/* Indicador de nivel factible (Z>0) */}
      <mesh position={[0, 0, 8]}>
        <cylinderGeometry args={[0.05, 0.05, 80, 8]} rotation={[Math.PI / 2, 0, 0]} />
        <meshBasicMaterial color="#00aa00" transparent opacity={0.3} />
      </mesh>
      
      {/* Indicador de nivel no factible (Z<0) */}
      <mesh position={[0, 0, -8]}>
        <cylinderGeometry args={[0.05, 0.05, 80, 8]} rotation={[Math.PI / 2, 0, 0]} />
        <meshBasicMaterial color="#aa0000" transparent opacity={0.3} />
      </mesh>
    </group>
  );
}

// Puntos usando BufferGeometry para mejor performance
function ScatterPoints({ scenarios }) {
  const meshRef = useRef();
  
  const { positions, colors, sizes } = useMemo(() => {
    if (!scenarios || scenarios.length === 0) {
      return { positions: new Float32Array(0), colors: new Float32Array(0), sizes: new Float32Array(0) };
    }
    
    const positions = [];
    const colors = [];
    const sizes = [];
    
    // Encontrar rangos para normalizar
    const xValues = scenarios.map(s => s.x || 0);
    const yValues = scenarios.map(s => s.y || 0);
    const xMin = Math.min(...xValues), xMax = Math.max(...xValues);
    const yMin = Math.min(...yValues), yMax = Math.max(...yValues);
    
    // Contar puntos por celda para ajustar opacidad/tamaño por densidad
    const gridSize = 5;
    const densityMap = new Map();
    
    scenarios.forEach((s) => {
      const x = Math.floor((((s.x || 0) - xMin) / (xMax - xMin || 1) * 40 - 20) / gridSize);
      const y = Math.floor((((s.y || 0) - yMin) / (yMax - yMin || 1) * 40 - 20) / gridSize);
      const z = Math.floor(((s.z || 0) * 20 - 10) / gridSize);
      const key = `${x},${y},${z}`;
      densityMap.set(key, (densityMap.get(key) || 0) + 1);
    });
    
    scenarios.forEach((s) => {
      // Normalizar a un rango visible [-20, 20]
      const x = ((s.x || 0) - xMin) / (xMax - xMin || 1) * 40 - 20;
      const y = ((s.y || 0) - yMin) / (yMax - yMin || 1) * 40 - 20;
      const z = (s.z || 0) * 20 - 10; // 0→-10, 1→10
      
      positions.push(x, y, z);
      
      // Calcular densidad para este punto
      const gridX = Math.floor(x / gridSize);
      const gridY = Math.floor(y / gridSize);
      const gridZ = Math.floor(z / gridSize);
      const key = `${gridX},${gridY},${gridZ}`;
      const density = densityMap.get(key) || 1;
      
      // Color según factibilidad con intensidad basada en densidad
      if (s.feasible) {
        // Verde con variación de intensidad
        const intensity = Math.min(1, 0.5 + (1 / density) * 0.5);
        colors.push(0, intensity, 0.2 * intensity);
      } else {
        // Rojo con variación de intensidad
        const intensity = Math.min(1, 0.5 + (1 / density) * 0.5);
        colors.push(intensity, 0.1 * intensity, 0);
      }
      
      // Tamaño según densidad (puntos más pequeños en áreas densas)
      const baseSize = 1.5;
      const sizeAdjustment = Math.max(0.5, 1 - (density - 1) * 0.1);
      sizes.push(baseSize * sizeAdjustment);
    });
    
    return {
      positions: new Float32Array(positions),
      colors: new Float32Array(colors),
      sizes: new Float32Array(sizes)
    };
  }, [scenarios]);
  
  if (scenarios.length === 0) {
    return null;
  }
  
  return (
    <points ref={meshRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          count={colors.length / 3}
          array={colors}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-size"
          count={sizes.length}
          array={sizes}
          itemSize={1}
        />
      </bufferGeometry>
      <pointsMaterial
        size={1.5}
        vertexColors
        transparent
        opacity={0.75}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// Ejes de referencia mejorados
function Axes() {
  return (
    <group>
      {/* Eje X - Rojo */}
      <mesh position={[25, 0, 0]}>
        <cylinderGeometry args={[0.2, 0.2, 50, 8]} rotation={[0, 0, Math.PI / 2]} />
        <meshBasicMaterial color="#ff4444" />
      </mesh>
      {/* Punta del eje X */}
      <mesh position={[50, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
        <coneGeometry args={[0.5, 1.5, 8]} />
        <meshBasicMaterial color="#ff4444" />
      </mesh>
      
      {/* Eje Y - Verde */}
      <mesh position={[0, 25, 0]}>
        <cylinderGeometry args={[0.2, 0.2, 50, 8]} />
        <meshBasicMaterial color="#44ff44" />
      </mesh>
      {/* Punta del eje Y */}
      <mesh position={[0, 50, 0]}>
        <coneGeometry args={[0.5, 1.5, 8]} />
        <meshBasicMaterial color="#44ff44" />
      </mesh>
      
      {/* Eje Z - Azul */}
      <mesh position={[0, 0, 15]}>
        <cylinderGeometry args={[0.2, 0.2, 30, 8]} rotation={[Math.PI / 2, 0, 0]} />
        <meshBasicMaterial color="#4444ff" />
      </mesh>
      {/* Punta del eje Z */}
      <mesh position={[0, 0, 30]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.5, 1.5, 8]} />
        <meshBasicMaterial color="#4444ff" />
      </mesh>
    </group>
  );
}

// Componente de cámara con rotación automática suave
function CameraController({ autoRotate }) {
  const { camera } = useThree();
  
  return (
    <OrbitControls 
      autoRotate={autoRotate} 
      autoRotateSpeed={0.5}
      enableZoom 
      enablePan
      minDistance={30}
      maxDistance={150}
      target={[0, 0, 0]}
    />
  );
}

// Componente principal
export function MonteCarlo3D({ scenarios, progress, grade }) {
  const [autoRotate, setAutoRotate] = useState(true);
  
  const feasibleCount = scenarios.filter(s => s.feasible).length;
  const feasibleRate = scenarios.length > 0 ? (feasibleCount / scenarios.length * 100).toFixed(1) : 0;
  
  return (
    <div className="relative w-full h-[500px] bg-black rounded-lg overflow-hidden">
      {/* Info overlay */}
      <div className="absolute top-4 left-4 z-10 text-white bg-black/70 p-4 rounded max-w-xs border border-white/20">
        <div className="text-2xl font-bold mb-2">
          Grado: <span className={getGradeColor(grade)}>{grade || '-'}</span>
        </div>
        <div className="text-sm">Simulaciones: {scenarios.length} / {progress?.total || '...'}</div>
        <div className="text-sm">Tasa factible: {feasibleRate}%</div>
        <div className="mt-2 flex gap-2 text-xs">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-500"></span>Factible ({feasibleCount})</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-500"></span>No factible ({scenarios.length - feasibleCount})</span>
        </div>
        {grade === 'F' && (
          <div className="mt-2 text-xs text-red-300 bg-red-900/30 p-2 rounded">
            ⚠️ Menos del 50% de escenarios son válidos.<br/>
            El horario tiene muchos conflictos.
          </div>
        )}
      </div>
      
      {/* Controles */}
      <div className="absolute bottom-4 left-4 z-10 flex gap-2">
        <button 
          onClick={() => setAutoRotate(!autoRotate)} 
          className="px-3 py-2 bg-white/10 text-white rounded hover:bg-white/20 transition-colors border border-white/20"
        >
          {autoRotate ? '⏸ Pausar' : '▶ Rotar'}
        </button>
      </div>
      
      {/* Indicador de estado */}
      <div className="absolute bottom-4 right-4 z-10 text-xs text-gray-400 bg-black/50 px-3 py-2 rounded border border-white/10">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${scenarios.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'}`}></div>
          {scenarios.length > 0 ? `${scenarios.length} puntos cargados` : 'Esperando datos...'}
        </div>
      </div>
      
      {/* Mensaje cuando no hay datos */}
      {scenarios.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-500 z-0 pointer-events-none">
          <div className="text-center">
            <p className="text-lg">Esperando simulaciones...</p>
            <p className="text-sm text-gray-600 mt-2">Los datos aparecerán aquí automáticamente</p>
          </div>
        </div>
      )}
      
      {/* Canvas 3D */}
      <Canvas camera={{ position: [70, 70, 70], fov: 45 }}>
        <color attach="background" args={['#0a0a0a']} />
        <ambientLight intensity={0.6} />
        <directionalLight position={[10, 10, 10]} intensity={0.5} />
        
        {/* Grid de referencia */}
        <gridHelper args={[80, 40, 0x444444, 0x222222]} position={[0, -10, 0]} />
        
        {/* Planos de referencia en Z=0 */}
        <ReferencePlanes />
        
        {/* Ejes con flechas */}
        <Axes />
        
        {/* Labels de los ejes */}
        <AxisLabels />
        
        {/* Leyenda en canvas */}
        <CanvasLegend />
        
        {/* Puntos de datos */}
        <ScatterPoints scenarios={scenarios} />
        
        {/* Controles de cámara */}
        <CameraController autoRotate={autoRotate} />
      </Canvas>
    </div>
  );
}

function getGradeColor(grade) {
  const colors = { 
    'A': 'text-green-400', 
    'B': 'text-green-300', 
    'C': 'text-yellow-400', 
    'D': 'text-orange-400', 
    'F': 'text-red-400' 
  };
  return colors[grade] || 'text-white';
}
