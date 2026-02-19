# Patrones de Dark Mode

## Niveles de Fondo

```
L0 (Base):         #000000 - Fondo absoluto
L1 (Primary):      #0B0F19 - App background
L2 (Secondary):    #151926 - Sidebar, cards
L3 (Tertiary):     #1E2330 - Elevated surfaces
L4 (Quaternary):   #2A3142 - Inputs, hover states
```

## Paleta de Grises

| Token | Valor | Uso |
|-------|-------|-----|
| gray-50 | #F8FAFC | Texto principal |
| gray-100 | #F1F5F9 | Titulos |
| gray-200 | #E2E8F0 | Subtitulos |
| gray-300 | #CBD5E1 | Texto secundario |
| gray-400 | #94A3B8 | Texto terciario |
| gray-500 | #64748B | Placeholders |
| gray-600 | #475569 | Deshabilitado |
| gray-700 | #334155 | Bordes hover |
| gray-800 | #1E293B | Bordes default |
| gray-900 | #0F172A | Superficies |

## Superficies Elevadas

### Elevation mediante Luz

En dark mode, la elevacion se representa con mayor luminosidad:

```css
/* Base */
--surface-1: #0F172A;  /* Fondo */

/* Elevado 1 - Cards */
--surface-2: #1E293B;

/* Elevado 2 - Modales, dropdowns */
--surface-3: #334155;

/* Elevado 3 - Tooltips, popovers */
--surface-4: #475569;
```

### Sombras en Dark Mode

Las sombras en dark mode usan color y opacidad:

```css
/* Sombra sutil */
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);

/* Sombra media */
box-shadow: 
  0 4px 6px -1px rgba(0, 0, 0, 0.4),
  0 2px 4px -1px rgba(0, 0, 0, 0.2);

/* Sombra fuerte */
box-shadow: 
  0 20px 25px -5px rgba(0, 0, 0, 0.5),
  0 10px 10px -5px rgba(0, 0, 0, 0.3);

/* Glow (para destacar) */
box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
```

## Jerarquia Visual

### Contraste Recomendado

| Elemento | Contraste minimo | Ratio WCAG |
|----------|------------------|------------|
| Texto principal | Alto | 7:1 |
| Texto secundario | Medio-alto | 4.5:1 |
| Placeholders | Medio | 3:1 |
| Decorativo | Bajo | Sin requisito |

### Gradientes Comunes

```css
/* Fondo con gradiente sutil */
background: linear-gradient(
  180deg,
  #0B1120 0%,
  #151E32 100%
);

/* Card con highlight */
background: linear-gradient(
  135deg,
  rgba(59, 130, 246, 0.1) 0%,
  rgba(30, 41, 59, 0.8) 50%,
  rgba(15, 23, 42, 0.9) 100%
);

/* Superficie elevada */
background: linear-gradient(
  180deg,
  #1E293B 0%,
  #334155 100%
);
```

## Estados de Componentes

### Hover States

```css
/* Boton hover - aumentar luminosidad */
.btn:hover {
  background: rgba(59, 130, 246, 0.8);
  filter: brightness(1.1);
}

/* Card hover - elevar */
.card:hover {
  background: #334155;
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
}

/* Item de lista hover */
.list-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
```

### Active/Selected States

```css
/* Item seleccionado */
.item-selected {
  background: rgba(59, 130, 246, 0.15);
  border-left: 3px solid #3B82F6;
}

/* Tab activo */
.tab-active {
  color: #F8FAFC;
  border-bottom: 2px solid #3B82F6;
}

/* Card seleccionada */
.card-selected {
  border: 1px solid rgba(59, 130, 246, 0.5);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
```

### Focus States

```css
/* Focus visible */
*:focus-visible {
  outline: 2px solid #3B82F6;
  outline-offset: 2px;
}

/* Input focus */
.input:focus {
  border-color: #3B82F6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}
```

## Accesibilidad

### Evitar Pure Black

```css
/* NO usar */
background: #000000;

/* USAR en su lugar */
background: #0B0F19;  /* Azul muy oscuro */
```

### Saturacion de Acentos

```css
/* En dark mode, acentos pueden ser mas saturados */
--primary-500: #3B82F6;  /* Azul brillante */
--success-500: #22C55E;  /* Verde brillante */
--warning-500: #F59E0B;  /* Amarillo brillante */
--error-500: #EF4444;    /* Rojo brillante */
```

### Reducir Brillo para Descanso Visual

```css
/* Opcion: Filtro de brillo general */
@media (prefers-color-scheme: dark) {
  body {
    filter: brightness(0.95);
  }
}
```

## Ejemplos de Implementacion

### Dashboard Dark Theme

```css
:root {
  /* Backgrounds */
  --bg-app: #0B1120;
  --bg-sidebar: #0F172A;
  --bg-card: #1E293B;
  --bg-input: #334155;
  
  /* Text */
  --text-primary: #F8FAFC;
  --text-secondary: #94A3B8;
  --text-muted: #64748B;
  
  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.05);
  --border-default: rgba(255, 255, 255, 0.1);
  --border-focus: #3B82F6;
  
  /* Accents */
  --accent-primary: #3B82F6;
  --accent-success: #10B981;
  --accent-warning: #F59E0B;
  --accent-error: #EF4444;
}
```
