# Stack Research

## Recommended Stack

| Layer | Technology | Version | Confidence |
|-------|-----------|---------|------------|
| 3D Globe | React Three Fiber + @react-three/drei | ^8.x | High |
| Globe Component | r3f-globe (vasturiano) | ^2.x | High |
| Charts | Recharts | ^3.0 | High |
| Styling | Tailwind CSS (existing) | ^3.x | High |
| Icons | Lucide React (existing) | ^0.x | High |
| Animations | Framer Motion | ^11.x | Medium |

## 3D Globe: React Three Fiber vs Three.js

**Recommendation: React Three Fiber (R3F)**

| Criteria | Three.js | React Three Fiber |
|----------|----------|-------------------|
| React Integration | Manual bridging | Native hooks/state |
| Learning Curve | Steep (WebGL) | Moderate (if know React) |
| Declarative Syntax | No (imperative) | Yes (JSX) |
| Maintenance | More boilerplate | React patterns |
| Performance | Slightly better | Negligible difference |
| Ecosystem 2026 | Mature | Growing rapidly |

**Why R3F for this project:**
- Already a React app — R3F integrates naturally with existing component model
- Decorative globe (not performance-critical) — don't need low-level Three.js control
- **r3f-globe library** exists specifically for globe visualizations
- Easier to manage with React state (route data → globe visualization)

**Key libraries:**
- `@react-three/fiber` — Core R3F
- `@react-three/drei` — Helpers (OrbitControls, Stars, etc.)
- `r3f-globe` — Pre-built globe component with arc/point visualization

## Charts: Recharts

**Recommendation: Recharts 3.0**

Recharts 3.0 (2025) brings:
- Enhanced TypeScript support
- Better animations
- Auto-sizing axes
- Improved accessibility

**Why Recharts:**
- Most popular React charting library (24K+ GitHub stars)
- Component-based API matches React patterns
- SVG-based — crisp at any resolution
- Built-in responsive container
- Simple for the chart types needed (bar, line, pie)

**Alternatives considered:**
- **Nivo** — More features but steeper learning curve, overkill for this use case
- **ApexCharts** — Good but canvas-based, harder to style with Tailwind
- **Visx** — Too low-level for simple dashboards

## Dark Theme / Glass UI

**Tailwind CSS glassmorphism pattern:**

```css
/* Core glass effect */
bg-white/10 backdrop-blur-lg border border-white/20 rounded-xl shadow-xl

/* Dark variant */
bg-black/20 backdrop-blur-xl border border-white/10
```

**Key Tailwind utilities:**
- `backdrop-blur-lg` / `backdrop-blur-xl` — Frosted glass effect
- `bg-white/10` or `bg-black/20` — Semi-transparent background
- `border border-white/10` — Subtle edge definition
- `shadow-xl` — Depth perception

**Color scheme (green neon / cyan blue):**
```js
// tailwind.config.js extend
colors: {
  neon: {
    green: '#39FF14',
    cyan: '#00FFFF',
    blue: '#00D4FF'
  },
  glass: {
    light: 'rgba(255, 255, 255, 0.1)',
    dark: 'rgba(0, 0, 0, 0.3)'
  }
}
```

**Animation library:**
Framer Motion for smooth transitions on:
- Card hover states
- Data updates
- Page transitions
- Globe rotation

## Integration Notes

**TypeScript + JavaScript coexistence:**
- New components in `*.tsx` files
- Existing JS components stay as-is
- Add `// @ts-check` to JS files for gradual typing
- tsconfig.json with `allowJs: true`

**Vite configuration:**
- Already supports TypeScript out of box
- Add `@vitejs/plugin-react` if not present
- Three.js imports work without additional config

**Performance considerations:**
- Three.js canvas in separate React tree (portal)
- Use `React.memo` on heavy components
- Lazy load 3D globe component

---

*Research date: 2026-01-19*

**Sources:**
- [React Three Fiber vs Three.js 2026](https://graffersid.com/react-three-fiber-vs-three-js/)
- [r3f-globe GitHub](https://github.com/vasturiano/r3f-globe)
- [FlyonUI Glassmorphism Guide](https://flyonui.com/blog/glassmorphism-with-tailwind-css/)
- [Glassmorp Dashboard Template](https://tailwinddashboard.com/glassmorp-template/)
- [Best React Chart Libraries 2025](https://blog.logrocket.com/best-react-chart-libraries-2025/)
