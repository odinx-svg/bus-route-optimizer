# Guia de Glassmorphism

## Que es Glassmorphism

Estilo de diseño que usa transparencia y blur para crear efectos de "vidrio esmerilado". Caracteristicas principales:
- Transparencia (fondo semitransparente)
- Backdrop blur (desenfoque del contenido detras)
- Bordes sutiles brillantes
- Sombras suaves
- Fondos vibrantes o con gradientes

## Formula CSS Base

```css
.glass {
  /* Fondo semitransparente */
  background: rgba(255, 255, 255, 0.1);
  
  /* Desenfoque */
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px); /* Safari */
  
  /* Borde brillante sutil */
  border: 1px solid rgba(255, 255, 255, 0.2);
  
  /* Sombra */
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
  
  /* Border radius */
  border-radius: 16px;
}
```

## Variaciones

### Dark Glass

```css
.glass-dark {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -1px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
}
```

### Light Glass

```css
.glass-light {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.8);
}
```

### Colored Glass

```css
.glass-blue {
  background: linear-gradient(
    135deg,
    rgba(59, 130, 246, 0.1) 0%,
    rgba(15, 23, 42, 0.4) 100%
  );
  backdrop-filter: blur(12px);
  border: 1px solid rgba(59, 130, 246, 0.2);
}
```

## Niveles de Blur

| Nivel | Valor | Uso |
|-------|-------|-----|
| xs | 2px | Elementos pequenos, tags |
| sm | 4-6px | Botones, inputs |
| md | 8-12px | Cards, panels |
| lg | 16-20px | Modales, drawers |
| xl | 32px+ | Fondos de seccion |

## Consideraciones de Implementacion

### Soporte de Navegadores
```css
.glass {
  /* Standard */
  backdrop-filter: blur(10px);
  
  /* Safari */
  -webkit-backdrop-filter: blur(10px);
  
  /* Fallback para navegadores sin soporte */
  @supports not (backdrop-filter: blur(10px)) {
    background: rgba(255, 255, 255, 0.95);
  }
}
```

### Performance
- Evitar blur muy grande en areas grandes
- No anidar elementos con blur (blur sobre blur)
- Usar `will-change: backdrop-filter` con cuidado
- Considerar reducir blur en dispositivos moviles

### Contrastes
- Siempre verificar contraste de texto sobre glass
- Agregar sombra de texto para mejor legibilidad:
  ```css
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  ```

## Ejemplos Comunes

### Card Glass
```css
.card-glass {
  background: rgba(30, 41, 59, 0.5);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
}
```

### Navbar Glass
```css
.navbar-glass {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: rgba(11, 17, 32, 0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  z-index: 100;
}
```

### Sidebar Glass
```css
.sidebar-glass {
  width: 240px;
  height: 100vh;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}
```

## Combinaciones con Otros Efectos

### Glass + Glow
```css
.glass-glow {
  background: rgba(59, 130, 246, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(59, 130, 246, 0.3);
  box-shadow: 
    0 0 20px rgba(59, 130, 246, 0.2),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
}
```

### Glass + Gradient Border
```css
.glass-gradient-border {
  position: relative;
  background: rgba(30, 41, 59, 0.5);
  backdrop-filter: blur(10px);
  border-radius: 12px;
}

.glass-gradient-border::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 12px;
  padding: 1px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  -webkit-mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
}
```
