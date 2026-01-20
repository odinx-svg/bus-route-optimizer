# Features Research

## Table Stakes (Must Have)

Command center dashboards have baseline expectations:

**Layout:**
- Dark background (not pure black — use #0a0a0a to #1a1a1a)
- Clear visual hierarchy with cards/panels
- Sidebar(s) for metrics/navigation
- Main content area for primary visualization
- Consistent spacing and alignment

**Typography:**
- Sans-serif, modern fonts (Inter, Geist, SF Pro)
- Bold headings with clear weight contrast
- Monospace for numbers/data (better scanning)
- High contrast text (but not pure white — use #e0e0e0)

**Metrics Display:**
- Large numbers for KPIs
- Trend indicators (up/down arrows, percentages)
- Subtle animations on data updates
- Clear labels with units

**Interactivity:**
- Hover states on all interactive elements
- Loading states for async operations
- Feedback on user actions (button clicks, uploads)
- Tooltips for additional context

## Differentiators (Command Center Feel)

What elevates from "dark dashboard" to "command center":

**Visual Impact:**
- Hero element (3D globe, animated visualization)
- Gradient accents (neon green → cyan transitions)
- Glow effects on key metrics (`shadow-[0_0_15px_rgba(57,255,20,0.5)]`)
- Subtle grid/scan lines in background
- Data streams / pulse animations

**Glass Morphism:**
- Frosted glass cards floating over background
- Layered depth (multiple transparency levels)
- Soft inner shadows for inset effect
- Border glow on focus/hover

**Animation Patterns:**
- Entrance animations (cards slide/fade in)
- Number counting up on load
- Pulse on live data points
- Smooth transitions between states
- Orbit/rotation on 3D elements

**Status Indicators:**
- Color-coded status (green=good, yellow=warning, red=alert)
- Animated dots for "live" status
- Progress rings instead of bars
- Spark lines for trends

## Glass Morphism Patterns

**When to use:**
- Cards containing grouped information
- Modal overlays
- Navigation elements
- Stat blocks

**When NOT to use:**
- Primary content areas (readability issues)
- Dense data tables
- Form inputs (contrast problems)
- Small text areas

**Implementation tiers:**

```
Tier 1 - Light glass (cards):
bg-white/5 backdrop-blur-md border border-white/10

Tier 2 - Medium glass (panels):
bg-white/10 backdrop-blur-lg border border-white/15

Tier 3 - Heavy glass (modals):
bg-black/40 backdrop-blur-xl border border-white/20
```

**Background requirements:**
Glass effect needs interesting background to show through:
- Gradient mesh
- 3D scene (globe)
- Subtle pattern/grid

## Animation Patterns

**Entrance (on mount):**
- Stagger children (0.1s delay between cards)
- Fade + slide up (y: 20 → 0)
- Scale from 0.95 → 1

**Data updates:**
- Number morphing (count up/down)
- Flash highlight then fade
- Pulse ring effect

**Hover states:**
- Scale 1.02 with shadow increase
- Border glow intensify
- Background opacity increase

**Loading:**
- Skeleton with shimmer gradient
- Pulse opacity animation
- Spinner with neon glow

**Timing recommendations:**
- Micro interactions: 150-200ms
- Card transitions: 300ms
- Page transitions: 400-500ms
- Easing: `ease-out` or `[0.4, 0, 0.2, 1]`

## Anti-Features (Avoid)

**Accessibility killers:**
- Pure black (#000) backgrounds — use #0a0a0f minimum
- Low contrast text (< 4.5:1 ratio)
- Relying only on color for status
- Tiny text (< 14px for body)
- Animations without `prefers-reduced-motion` respect

**Visual mistakes:**
- Too many glow effects (overwhelming)
- Inconsistent blur levels
- Mixing glass with solid cards randomly
- Neon on neon (green text on green glow)
- Busy backgrounds under glass

**UX problems:**
- Unclear interactive elements
- No loading states
- Missing hover feedback
- Form inputs hard to see
- Data tables with glass (unreadable)

**Performance:**
- Too many backdrop-blur layers (GPU heavy)
- Large Three.js scenes without optimization
- Animations on scroll without throttling
- Uncompressed textures in 3D

---

*Research date: 2026-01-19*

**Sources:**
- [Glass UI Components (Shadcn)](https://allshadcn.com/components/glass-ui/)
- [Glassmorp Dashboard Template](https://glassmorp.tailwinddashboard.com/)
- [LogRocket Glassmorphism CSS](https://blog.logrocket.com/implement-glassmorphism-css/)
