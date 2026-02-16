# Frontend Dockerfile - Tutti React App
# Multi-stage build para desarrollo y producción

# ============================================================================
# Base Stage - Dependencias comunes
# ============================================================================
FROM node:20-alpine AS base

# Instalar dependencias de sistema necesarias
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copiar archivos de dependencias
COPY package*.json ./

# ============================================================================
# Development Stage - Hot reload para desarrollo local
# ============================================================================
FROM base AS development

# Instalar TODAS las dependencias (incluyendo devDependencies)
RUN npm ci

# Copiar código fuente
COPY . .

# Puerto de Vite
EXPOSE 5173

# Variable para permitir conexiones externas
ENV HOST=0.0.0.0

# Comando de desarrollo con hot reload
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================================================
# Production Build Stage - Compilación estática
# ============================================================================
FROM base AS build

# Instalar dependencias
RUN npm ci

# Copiar código fuente
COPY . .

# Build de producción
RUN npm run build

# ============================================================================
# Production Stage - Servidor Nginx para archivos estáticos
# ============================================================================
FROM nginx:alpine AS production

# Copiar configuración personalizada de nginx
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://backend:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
    } \
}' > /etc/nginx/conf.d/default.conf

# Copiar build estático desde stage anterior
COPY --from=build /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
