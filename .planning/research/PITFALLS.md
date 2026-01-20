# Pitfalls Research

## Three.js in React

### P1: Memory Leaks on Unmount

**Problem:** Three.js objects (geometries, materials, textures) don't auto-dispose when React unmounts components.

**Warning signs:**
- Memory usage grows over time
- Browser becomes sluggish after navigation
- Console warnings about WebGL context

**Prevention:**
```tsx
// Use R3F's automatic disposal OR manual cleanup
useEffect(() => {
  return () => {
    // Dispose Three.js resources
    geometry.dispose()
    material.dispose()
    texture.dispose()
  }
}, [])

// Better: Let R3F handle it with proper component structure
// Don't create Three.js objects outside Canvas
```

**Phase:** Address in Globe implementation (Phase with 3D work)

---

### P2: Render Loop Conflicts

**Problem:** R3F's render loop vs React's re-render cycle can cause performance issues if state updates trigger unnecessary 3D re-renders.

**Warning signs:**
- Globe stutters when typing in forms
- 60fps drops during UI interactions

**Prevention:**
```tsx
// Isolate R3F state from React state
// Use refs for values that change frequently
const rotationRef = useRef(0)
useFrame(() => {
  rotationRef.current += 0.01
  globe.rotation.y = rotationRef.current
})

// DON'T do this:
const [rotation, setRotation] = useState(0)  // Bad for animation
```

**Phase:** Address in Globe implementation

---

### P3: Blocking Main Thread on Load

**Problem:** Large 3D assets (textures, models) block UI while loading.

**Warning signs:**
- White screen on initial load
- Buttons unresponsive while globe loads

**Prevention:**
```tsx
// Lazy load the entire 3D scene
const GlobeScene = lazy(() => import('./GlobeScene'))

// Use Suspense with loading indicator
<Suspense fallback={<GlobeLoadingSkeleton />}>
  <GlobeScene routes={routes} />
</Suspense>

// Preload textures
import { useTexture } from '@react-three/drei'
const texture = useTexture('/earth-dark.jpg')  // Preloaded
```

**Phase:** Address in Globe implementation

---

## Performance

### P4: Too Many Backdrop-blur Layers

**Problem:** `backdrop-blur` is GPU-intensive. Stacking multiple blurred elements tanks performance.

**Warning signs:**
- Scroll jank
- Low FPS on hover animations
- Fans spin up on laptops

**Prevention:**
- Limit to 3-4 glass cards visible at once
- Use solid backgrounds for nested cards
- Test on mid-range hardware
- Provide `prefers-reduced-motion` fallback

```css
@media (prefers-reduced-motion: reduce) {
  .glass-card {
    backdrop-filter: none;
    background: rgba(0, 0, 0, 0.8);  /* Solid fallback */
  }
}
```

**Phase:** Address in UI foundation phase

---

### P5: Unoptimized Globe Textures

**Problem:** High-res Earth textures (8K) are unnecessary for decorative globe.

**Warning signs:**
- Slow initial load
- High memory usage
- Mobile devices struggle

**Prevention:**
- Use 2K texture maximum (2048x1024)
- Compress to WebP/AVIF
- Use lower res for mobile
- Consider procedural shader instead of texture

**Phase:** Address in Globe implementation

---

## Dark Theme / Glass UI

### P6: Insufficient Contrast

**Problem:** Text unreadable on glass cards with variable backgrounds.

**Warning signs:**
- Squinting to read metrics
- Accessibility audit failures
- User complaints

**Prevention:**
```css
/* Ensure minimum contrast */
.glass-card {
  /* Add subtle dark overlay to guarantee contrast */
  background: linear-gradient(
    rgba(0, 0, 0, 0.4),
    rgba(0, 0, 0, 0.4)
  ), rgba(255, 255, 255, 0.1);
}

/* Or use text shadow */
.glass-text {
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
}
```

- Test with WCAG contrast checker
- Minimum 4.5:1 for body text
- Minimum 3:1 for large text/UI

**Phase:** Address in UI foundation phase

---

### P7: Form Inputs Invisible

**Problem:** Input fields blend into dark/glass background, users can't find them.

**Warning signs:**
- Users clicking wrong areas
- "Where do I type?" questions

**Prevention:**
```css
.dark-input {
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.2);
  /* Clear focus state */
  &:focus {
    border-color: #39FF14;
    box-shadow: 0 0 0 2px rgba(57, 255, 20, 0.2);
  }
}
```

**Phase:** Address in Upload panel phase

---

## WebGL Conflicts

### P8: Leaflet + Three.js Context Issues

**Problem:** Both Leaflet and Three.js use WebGL. Too many contexts can cause browser limits (typically 8-16 contexts).

**Warning signs:**
- "Too many WebGL contexts" error
- Map or globe goes black
- Inconsistent behavior across browsers

**Prevention:**
- Don't render both simultaneously if possible
- Use view toggle (globe OR map, not both)
- If both needed: keep Leaflet in 2D mode (no WebGL plugins)
- Consider: Globe as background (always on), Leaflet as overlay (foreground when needed)

```tsx
// View state approach
const [activeView, setActiveView] = useState<'globe' | 'map'>('globe')

{activeView === 'globe' && <GlobeScene />}
{activeView === 'map' && <MapView />}
```

**Phase:** Address in architecture/layout phase

---

### P9: Canvas Sizing Issues

**Problem:** Three.js canvas doesn't resize properly with CSS, causing stretched/cropped visuals.

**Warning signs:**
- Globe appears stretched
- Aspect ratio wrong after window resize

**Prevention:**
```tsx
// R3F handles this, but ensure container has explicit size
<div className="w-full h-full relative">
  <Canvas
    style={{ position: 'absolute', top: 0, left: 0 }}
    // R3F auto-resizes to parent
  >
    ...
  </Canvas>
</div>
```

**Phase:** Address in Globe implementation

---

## General Dashboard

### P10: No Loading States

**Problem:** User doesn't know if optimization is running or app is frozen.

**Warning signs:**
- Users clicking button multiple times
- "Is it working?" questions

**Prevention:**
- Always show loading indicator for async operations
- Disable buttons while loading
- Show progress if possible

```tsx
<button
  disabled={isOptimizing}
  className={isOptimizing ? 'opacity-50 cursor-wait' : ''}
>
  {isOptimizing ? (
    <>
      <Spinner /> Optimizing...
    </>
  ) : (
    'Run Optimization'
  )}
</button>
```

**Phase:** Address in Control panel phase

---

### P11: Lost Work on Error

**Problem:** API error clears user's uploaded data, forcing re-upload.

**Warning signs:**
- User frustration after errors
- Re-uploading same files repeatedly

**Prevention:**
- Keep routes in state even after optimization error
- Show error toast, don't reset state
- Add retry button

```tsx
try {
  const schedule = await optimize(routes)
  setSchedule(schedule)
} catch (error) {
  // DON'T: setRoutes([])
  // DO: Show error, keep routes
  toast.error('Optimization failed. Your data is preserved.')
}
```

**Phase:** Address in error handling pass

---

## Summary by Phase

| Phase | Pitfalls to Address |
|-------|---------------------|
| UI Foundation | P4 (blur layers), P6 (contrast) |
| Globe Implementation | P1 (memory), P2 (render loop), P3 (loading), P5 (textures), P9 (sizing) |
| Layout/Architecture | P8 (WebGL contexts) |
| Upload Panel | P7 (form inputs) |
| Control Panel | P10 (loading states), P11 (error handling) |

---

*Research date: 2026-01-19*
