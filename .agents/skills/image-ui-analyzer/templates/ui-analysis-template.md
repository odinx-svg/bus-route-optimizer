# Plantilla de Analisis UI

## 1. Informacion General

- **Nombre del proyecto/sistema**: 
- **Tipo de interfaz**: (Dashboard / App / Website / Landing)
- **Estilo visual**: (Glassmorphism / Flat / Neumorphism / Skeuomorphic)
- **Modo**: Claro / Oscuro / Ambos
- **Densidad**: Alta / Media / Baja

---

## 2. Paleta de Colores

### Backgrounds

| Nombre | Color | Uso |
|--------|-------|-----|
| bg-primary | `#000000` | Fondo principal |
| bg-secondary | `#000000` | Sidebar, areas secundarias |
| bg-card | `#000000` | Superficies elevadas |
| bg-hover | `#000000` | Estados hover |
| bg-active | `#000000` | Estados activos/seleccionados |

### Superficies Elevadas

| Nombre | Color | Uso |
|--------|-------|-----|
| surface-1 | `#000000` | Cards nivel 1 |
| surface-2 | `#000000` | Cards nivel 2 |
| surface-3 | `#000000` | Dropdowns, modales |

### Acentos

| Nombre | Color | Uso |
|--------|-------|-----|
| primary | `#000000` | Botones primarios, links |
| primary-hover | `#000000` | Hover de primario |
| secondary | `#000000` | Botones secundarios |
| success | `#000000` | Estados exito |
| warning | `#000000` | Estados advertencia |
| error | `#000000` | Estados error |
| info | `#000000` | Estados informacion |

### Texto

| Nombre | Color | Uso |
|--------|-------|-----|
| text-primary | `#000000` | Titulos, texto principal |
| text-secondary | `#000000` | Subtitulos, descripciones |
| text-muted | `#000000` | Placeholders, hints |
| text-disabled | `#000000` | Texto deshabilitado |
| text-inverse | `#000000` | Texto sobre fondos oscuros |

### Bordes

| Nombre | Color | Uso |
|--------|-------|-----|
| border-subtle | `#000000` | Bordes sutiles |
| border-default | `#000000` | Bordes estandar |
| border-focus | `#000000` | Estados focus |
| border-error | `#000000` | Estados error |

### Gradientes

```css
/* Gradiente 1 */
--gradient-primary: linear-gradient(135deg, #000000 0%, #000000 100%);

/* Gradiente 2 */
--gradient-glow: radial-gradient(circle at center, #00000020 0%, transparent 70%);
```

---

## 3. Tipografia

### Familias de Fuente

- **Primaria**: Font Name (sans-serif/serif/mono)
- **Secundaria**: Font Name (usada en...)
- **Monoespaciada**: Font Name (usada en...)

### Jerarquia

| Elemento | Tamano | Peso | Line-height | Letter-spacing | Color |
|----------|--------|------|-------------|----------------|-------|
| H1 | 32px | 700 | 1.2 | -0.02em | text-primary |
| H2 | 24px | 600 | 1.3 | -0.01em | text-primary |
| H3 | 20px | 600 | 1.4 | 0 | text-primary |
| H4 | 16px | 600 | 1.4 | 0 | text-primary |
| Body | 14px | 400 | 1.5 | 0 | text-secondary |
| Caption | 12px | 500 | 1.4 | 0.02em | text-muted |
| Small | 10px | 500 | 1.4 | 0.05em | text-muted |

### Estilos Especiales

- **Labels uppercase**: 10px, medium, tracking-wide, uppercase
- **Monospace**: 13px, regular (para datos, horas, codigo)
- **Links**: Color primary, hover underline

---

## 4. Layout y Espaciado

### Estructura General

```
[DESCRIPCION DEL LAYOUT]
Ejemplo:
- Sidebar fijo 240px izquierda
- Header 64px fijo arriba
- Main content area scrollable
- Panel derecho opcional 320px
```

### Breakpoints

| Nombre | Ancho | Comportamiento |
|--------|-------|----------------|
| Mobile | < 640px | Sidebar colapsa, stack vertical |
| Tablet | 640-1024px | Sidebar narrow, grid 2-col |
| Desktop | > 1024px | Layout completo, grid 3-4 col |

### Sistema de Espaciado

| Token | Valor | Uso tipico |
|-------|-------|------------|
| space-1 | 4px | Gaps pequenos, iconos |
| space-2 | 8px | Padding interno elementos |
| space-3 | 12px | Gap entre items relacionados |
| space-4 | 16px | Padding cards, gaps |
| space-5 | 20px | Margins secciones pequenas |
| space-6 | 24px | Padding secciones |
| space-8 | 32px | Margins secciones grandes |
| space-10 | 40px | Hero sections |
| space-12 | 48px | Espaciado mayor |

### Dimensiones de Componentes

| Componente | Width | Height | Padding |
|------------|-------|--------|---------|
| Button sm | auto | 32px | 8px 12px |
| Button md | auto | 40px | 10px 16px |
| Button lg | auto | 48px | 12px 24px |
| Input | 100% | 40px | 10px 12px |
| Card | 100% | auto | 16px-24px |
| Sidebar item | 100% | 40px | 8px 12px |
| Avatar sm | 24px | 24px | 0 |
| Avatar md | 32px | 32px | 0 |
| Avatar lg | 40px | 40px | 0 |

---

## 5. Componentes Identificados

### Lista de Componentes

#### 1. [Nombre del Componente]
- **Proposito**: [Breve descripcion]
- **Ubicacion**: [Donde aparece en la UI]
- **Estados**: Default / Hover / Active / Disabled

**Especificaciones visuales:**
- Background: [color]
- Border: [color] [width] [radius]
- Shadow: [descripcion]
- Padding: [valor]
- Typography: [estilo aplicado]

**Contenido:**
- [Lista de elementos que contiene]

---

#### 2. [Nombre del Componente]
[Repetir estructura...]

---

## 6. Efectos Visuales

### Sombras

```css
/* Shadow sm */
box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);

/* Shadow DEFAULT */
box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);

/* Shadow md */
box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);

/* Shadow lg */
box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);

/* Shadow glow (colored) */
box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
```

### Blur / Backdrop Filter

```css
/* Glassmorphism leve */
backdrop-filter: blur(8px);
background: rgba(255, 255, 255, 0.05);

/* Glassmorphism medio */
backdrop-filter: blur(12px);
background: rgba(255, 255, 255, 0.1);

/* Glassmorphism fuerte */
backdrop-filter: blur(20px) saturate(180%);
background: rgba(255, 255, 255, 0.15);
```

### Gradientes

```css
/* Header background */
background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);

/* Card highlight */
background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, transparent 100%);

/* Progress bar */
background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);

/* Glow effect */
background: radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.2) 0%, transparent 70%);
```

### Border Radius

| Token | Valor | Uso |
|-------|-------|-----|
| radius-sm | 4px | Botones, tags |
| radius-md | 6px | Inputs, small cards |
| radius-lg | 8px | Cards, modales |
| radius-xl | 12px | Panels, large cards |
| radius-2xl | 16px | Feature cards |
| radius-full | 9999px | Pills, avatares |

### Transiciones

```css
/* Rapida - para micro-interacciones */
transition: all 150ms ease-out;

/* Normal - para hover states */
transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);

/* Lenta - para elementos grandes */
transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);

/* Especificas */
transition: color 150ms ease, background-color 150ms ease, border-color 150ms ease;
```

---

## 7. Iconografia

### Set de Iconos
- **Familia**: [Phosphor / Lucide / Heroicons / Feather / etc.]
- **Estilo**: [Outline / Fill / Duotone]
- **Tamanos**: 16px (sm), 20px (md), 24px (lg), 32px (xl)

### Iconos Identificados
| Nombre | Uso | Tamano tipico |
|--------|-----|---------------|
| [icon-name] | [donde se usa] | 20px |

---

## 8. Assets y Media

### Imagenes
- **Tipo**: [Fotos / Ilustraciones / Iconos]
- **Tratamiento**: [Filtros, opacidad, etc.]
- **Border radius**: [Si aplica]

### Ilustraciones
- **Estilo**: [Flat / 3D / Line art]
- **Colores**: [Paleta usada]

---

## 9. Implementacion (Codigo)

### Tailwind Config

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: '#0B1120',
          secondary: '#151E32',
        },
        surface: {
          DEFAULT: '#1E293B',
          hover: '#334155',
        },
        // ... mas colores
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    }
  }
}
```

### Variables CSS

```css
:root {
  /* Backgrounds */
  --bg-primary: #0B1120;
  --bg-secondary: #151E32;
  --bg-card: rgba(30, 41, 59, 0.5);
  
  /* Colors */
  --accent-primary: #3B82F6;
  --accent-secondary: #8B5CF6;
  
  /* Text */
  --text-primary: #F8FAFC;
  --text-secondary: #94A3B8;
  --text-muted: #64748B;
  
  /* Effects */
  --blur-card: blur(12px);
  --shadow-card: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --radius-card: 12px;
  
  /* Spacing */
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
}
```

### Componente React Ejemplo

```jsx
const Card = ({ 
  children, 
  title,
  actions,
  className 
}) => (
  <div className={`
    bg-slate-800/50 
    backdrop-blur-xl 
    border border-slate-700/50 
    rounded-xl
    overflow-hidden
    ${className}
  `}>
    {title && (
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/50">
        <h3 className="font-semibold text-slate-100">{title}</h3>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    )}
    <div className="p-5">
      {children}
    </div>
  </div>
);
```

---

## 10. Notas y Observaciones

### Elementos Destacados
- [Lista de elementos visuales interesantes]

### Patrones Unicos
- [Describir patrones especificos del diseño]

### Posibles Mejoras
- [Ideas de mejora basadas en el analisis]

### Referencias Similares
- [Otros sistemas de diseno similares]

---

*Analisis generado el: [FECHA]*
*Imagen analizada: [NOMBRE_ARCHIVO]*
