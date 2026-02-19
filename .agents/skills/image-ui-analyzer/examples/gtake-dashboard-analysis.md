# Analisis UI - Dashboard G.Take

## 1. Informacion General

- **Nombre del sistema**: G.Take
- **Tipo de interfaz**: Dashboard de gestion de tareas
- **Estilo visual**: Glassmorphism + Dark Mode + Gradientes vibrantes
- **Modo**: Oscuro
- **Densidad**: Media-Alta

---

## 2. Paleta de Colores

### Backgrounds

| Nombre | Color | Uso |
|--------|-------|-----|
| bg-primary | `#0B1120` | Fondo principal muy oscuro azulado |
| bg-sidebar | `#0D1321` | Sidebar izquierda ligeramente mas claro |
| bg-card | `rgba(30, 41, 59, 0.6)` | Cards con glassmorphism |
| bg-card-solid | `#151E32` | Cards sin transparencia |
| bg-elevated | `#1E293B` | Botones, elementos elevados |
| bg-input | `#0F172A` | Fondos de inputs |

### Acentos

| Nombre | Color | Uso |
|--------|-------|-----|
| primary | `#3B82F6` | Azul brillante - botones, links |
| primary-light | `#60A5FA` | Hover de primario |
| secondary | `#8B5CF6` | Violeta - gradientes, highlights |
| accent-glow | `rgba(59, 130, 246, 0.3)` | Glows y sombras coloridas |
| success | `#10B981` | Estados positivos |
| warning | `#F59E0B` | Advertencias (usado en nota) |

### Texto

| Nombre | Color | Uso |
|--------|-------|-----|
| text-primary | `#F8FAFC` | Titulos, texto principal |
| text-secondary | `#E2E8F0` | Subtitulos, descripciones |
| text-muted | `#94A3B8` | Metadata, captions |
| text-subtle | `#64748B` | Placeholders, textos terciarios |
| text-accent | `#60A5FA` | Numeros, datos importantes |

### Gradientes

```css
/* Header background glow */
background: linear-gradient(
  135deg,
  rgba(59, 130, 246, 0.15) 0%,
  rgba(139, 92, 246, 0.1) 50%,
  transparent 100%
);

/* Progress bar */
background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
```

---

## 3. Tipografia

- **Primaria**: Inter (sans-serif)
- **H1**: 28px, font-bold
- **Body**: 13-14px, font-normal
- **Captions**: 11-12px, text-muted

---

## 4. Layout

- Sidebar: 220px fijo izquierda
- Main: Fluido con padding 24px
- Grid: 12-column con gap 16px
- Cards: Border-radius 16px

---

## 5. Efectos Visuales

### Glassmorphism
```css
.glass-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
}
```

### Glow
```css
.header-glow {
  background: radial-gradient(
    ellipse at 50% 0%,
    rgba(59, 130, 246, 0.15) 0%,
    transparent 50%
  );
}
```

---

## 6. Componentes Principales

1. **Sidebar**: Nav items con iconos, active state con barra azul
2. **Cards**: Glassmorphism con padding 20px
3. **Task Cards**: Icono gradiente + titulo + metadata
4. **Progress Bar**: Gradiente azul-morado
5. **Avatar Stack**: Overlap con borde
6. **Activity Chart**: Barras verticales con gradiente

---

*Analisis completo disponible en la skill image-ui-analyzer*
