---
name: image-ui-analyzer
description: Analisis y extraccion de diseño UI/UX desde imagenes, capturas de pantalla, mockups y fotografias de interfaces. Usar cuando se necesite analizar una imagen de UI para extraer paleta de colores, tipografia, espaciado, layout, componentes, efectos visuales y crear especificaciones para replicar el diseño en codigo. Incluye tecnicas de analisis visual, documentacion de estilos y plantillas de reporte.
---

# Image UI Analyzer Skill

## Proposito

Analizar imagenes de interfaces de usuario (dashboards, apps, websites) para extraer informacion de diseño precisa y reproducible. Esta skill permite:

1. Extraer paleta de colores exacta
2. Identificar tipografia y jerarquia
3. Analizar layout y espaciado
4. Documentar componentes UI
5. Detectar efectos visuales (sombras, blur, gradientes)
6. Crear especificaciones para replicar el diseño

## Proceso de Analisis

### Paso 1: Vision General

Al recibir una imagen de UI:

1. **Identificar el tipo de interfaz**:
   - Dashboard administrativo
   - Aplicacion web
   - Landing page
   - Mobile app
   - Panel de control

2. **Describir la estructura general**:
   - Layout (sidebar + main, header + content, etc.)
   - Navegacion visible
   - Areas de contenido principales
   - Paneles/cards presentes

3. **Tema visual**:
   - Modo claro/oscuro
   - Estilo (minimalista, glassmorphism, neomorfismo, flat)
   - Densidad de informacion

### Paso 2: Analisis de Colores

Extraer toda la paleta de colores:

```
COLORES IDENTIFICADOS:
===================

Fondos:
- Background principal: #0B1120 (azul muy oscuro)
- Background secundario: #151E32 (azul oscuro)
- Background cards: #1E293B80 (con transparencia)
- Background sidebar: #0F172A

Superficies:
- Surface elevate: #1E293B
- Surface hover: #334155

Acentos:
- Primary: #3B82F6 (azul)
- Primary hover: #60A5FA
- Secondary: #8B5CF6 (violeta)
- Success: #10B981
- Warning: #F59E0B
- Error: #EF4444

Texto:
- Text primary: #F8FAFC
- Text secondary: #94A3B8
- Text muted: #64748B
- Text inverse: #0F172A

Bordes:
- Border subtle: #1E293B
- Border default: #334155
- Border focus: #3B82F6

Gradientes:
- Header glow: linear-gradient(135deg, #3B82F620 0%, #8B5CF620 100%)
- Card highlight: linear-gradient(180deg, #1E293B00 0%, #3B82F610 100%)
```

### Paso 3: Tipografia

Analizar fuentes y jerarquia:

```
TIPOGRAFIA:
==========

Fuente principal: Inter (sans-serif)
Fuente monoespaciada: JetBrains Mono (para datos/hora)

Jerarquia:
- H1: 24px / font-bold / line-height 1.2
- H2: 20px / font-semibold / line-height 1.3
- H3: 16px / font-semibold / line-height 1.4
- Body: 14px / font-normal / line-height 1.5
- Caption: 12px / font-medium / line-height 1.4
- Small: 10px / font-medium / uppercase / tracking-wide

Pesos usados:
- 400 (normal) - body text
- 500 (medium) - labels, buttons
- 600 (semibold) - headers, emphasis
- 700 (bold) - main title

Colores de texto por nivel:
- Headings: #F8FAFC
- Body: #E2E8F0
- Secondary: #94A3B8
- Muted: #64748B
```

### Paso 4: Layout y Espaciado

Documentar estructura y dimensiones:

```
LAYOUT:
======

Estructura: Sidebar fijo + Main scrollable

Sidebar:
- Width: 240px (15rem)
- Padding: 16px vertical, 12px horizontal
- Gap entre items: 4px

Main Content:
- Padding: 24px
- Max-width: none (fluido)
- Gap entre secciones: 24px

Grid sistema:
- Columnas: 12-column implicito
- Gap: 16px (gap-4)
- Gutters: 24px

ESPACIADO:
=========

Escala:
- xs: 4px
- sm: 8px
- md: 12px
- lg: 16px
- xl: 24px
- 2xl: 32px
- 3xl: 48px

Padding cards: 16px-20px
Margin entre cards: 16px
Inner gaps: 12px
```

### Paso 5: Componentes Identificados

Listar y describir cada componente:

```
COMPONENTES:
===========

1. Sidebar Navigation
   - Logo en top
   - Menu items con icono + texto
   - Active item: fondo azul semitransparente + borde izquierdo
   - Hover: fondo sutil
   - User profile al final

2. Header
   - Breadcrumbs
   - Titulo principal grande
   - Subtitulo descriptivo
   - Botones de accion a la derecha

3. Cards/Panels
   - Fondo semitransparente (glassmorphism)
   - Border sutil
   - Border-radius: 12px-16px
   - Shadow sutil o glow
   - Header opcional con titulo y acciones

4. Task Cards (dentro de panels)
   - Layout horizontal con icono
   - Titulo + descripcion
   - Metadata (hora, participantes)
   - Badge de estado
   - Acciones (menu, completar)

5. Progress Bar
   - Track: fondo oscuro
   - Fill: gradiente azul-morado
   - Border-radius: full
   - Altura: 8px

6. Buttons
   - Primary: fondo azul, texto blanco
   - Secondary: fondo transparente, borde
   - Ghost: solo texto con hover
   - Icon buttons: circulares

7. Avatars
   - Stack de avatars con overlap
   - Borde sutil
   - Size: 24px-32px

8. Badges/Tags
   - Fondo color semitransparente
   - Texto pequeno uppercase
   - Border-radius: 4px-6px
```

### Paso 6: Efectos Visuales

Documentar efectos especiales:

```
EFECTOS VISUALES:
================

Glassmorphism:
- backdrop-filter: blur(12px)
- background: rgba(30, 41, 59, 0.5)
- border: 1px solid rgba(255, 255, 255, 0.1)

Sombras:
- Card shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
- Elevate shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2)
- Glow azul: 0 0 20px rgba(59, 130, 246, 0.3)

Gradientes:
- Fondo header: radial-gradient desde esquina superior
- Progress bar: linear-gradient 90deg azul a morado
- Overlay cards: linear-gradient desde abajo

Otros:
- Border radius escalonado: 8px, 12px, 16px
- Transiciones suaves: 200ms-300ms
- Hover states: brightness o scale sutil
```

## Plantilla de Reporte

Ver `templates/ui-analysis-template.md` para plantilla completa.

## Ejemplo de Output

```markdown
# Analisis UI Dashboard G.Take

## Vision General
Dashboard de gestion de tareas tipo Notion linear-style.
Tema oscuro con glassmorphism y acentos azul/morado.
Layout: Sidebar izquierda + Main area fluida.

## Paleta de Colores

### Backgrounds
| Nombre | Valor | Uso |
|--------|-------|-----|
| bg-primary | #0B1120 | Fondo principal |
| bg-secondary | #151E32 | Sidebar, secciones |
| bg-card | #1E293B80 | Cards con blur |
| bg-elevated | #1E293B | Cards solidas |

### Acentos
| Nombre | Valor | Uso |
|--------|-------|-----|
| primary | #3B82F6 | Botones, links, activo |
| secondary | #8B5CF6 | Gradientes, highlights |
| success | #10B981 | Estados positivos |

[... continua con tipografia, layout, componentes, codigo ...]
```

## Tecnica de Analisis Visual

### Identificar Colores Precisos

1. **Buscar areas de color plano** (evitar gradientes para muestra)
2. **Notar transparencias** (efecto glass, overlays)
3. **Identificar gradientes** (direccion, colores de inicio/fin)
4. **Verificar consistencia** (mismo azul usado en multiples lugares)

### Medir Proporciones

1. **Establecer unidad base**: Usar texto (14px = base)
2. **Comparar elementos**: Este boton es 2x la altura del texto
3. **Grid implicito**: Notar alineaciones y espaciados regulares

### Detectar Patrones

1. **Repeticion**: Cards identicos, mismos espaciados
2. **Jerarquia**: Tamano de fuente, peso, color indican importancia
3. **Agrupacion**: Proximidad, bordes, backgrounds agrupan elementos
4. **Consistencia**: Mismos estilos aplicados a elementos similares

## Generacion de Codigo

### Tailwind CSS

```jsx
// Ejemplo de card basada en analisis
const Card = ({ children }) => (
  <div className="
    bg-slate-800/50 
    backdrop-blur-xl
    border border-slate-700/50 
    rounded-xl
    p-5
    shadow-lg shadow-black/10
  ">
    {children}
  </div>
);
```

### CSS Custom Properties

```css
:root {
  /* Del analisis de imagen */
  --bg-primary: #0B1120;
  --bg-card: rgba(30, 41, 59, 0.5);
  --accent: #3B82F6;
  --text-primary: #F8FAFC;
  --radius-lg: 12px;
  --blur-card: 12px;
}
```

## Limitaciones y Consideraciones

1. **Colores exactos**: Pueden variar por compresion de imagen
2. **Fuentes**: Identificar familia, pero peso exacto puede requerir prueba
3. **Dimensiones**: Estimar proporciones, no pixeles exactos
4. **Animaciones**: No visibles en imagen estatica
5. **Estados**: Solo se ve un estado (normal, hover, etc.)

## Referencias

- `references/glassmorphism-guide.md`: Guia de efectos glass
- `references/dark-mode-patterns.md`: Patrones de tema oscuro
- `references/color-extraction.md`: Tecnicas de extraccion de color
- `templates/ui-analysis-template.md`: Plantilla de reporte
