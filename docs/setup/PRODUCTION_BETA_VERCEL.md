# Producción Beta Paso a Paso (Vercel + Render)

Esta guía está escrita para hacerla sin dudas: copiar/pegar y validar.

## Objetivo final

1. Frontend en Vercel.
2. Backend en Render.
3. PostgreSQL y Redis en Render.
4. Guardado de optimizaciones/horarios persistente en base de datos.

---

## Paso 0: Ten esto a mano

Necesitas:

1. Cuenta en GitHub con este repo subido.
2. Cuenta en Render: `https://dashboard.render.com/`
3. Cuenta en Vercel: `https://vercel.com/dashboard`

---

## Paso 1: Crear PostgreSQL en Render

1. Abre: `https://dashboard.render.com/`
2. Pulsa `New +` -> `PostgreSQL`.
3. Nombre recomendado: `tutti-postgres`.
4. Crea la base.
5. Cuando termine, entra en la DB y copia el valor de `Internal Database URL`.

Nota:
- Si empieza por `postgres://`, cámbialo a `postgresql://` antes de usarlo.

---

## Paso 2: Crear Redis en Render

1. En Render: `New +` -> `Redis`.
2. Nombre recomendado: `tutti-redis`.
3. Crea Redis.
4. Copia el valor de `Internal Redis URL`.

---

## Paso 3: Crear Backend en Render

1. En Render: `New +` -> `Web Service`.
2. Conecta tu repo de GitHub.
3. Configura:
   - `Root Directory`: `backend`
   - `Runtime`: `Python`
   - `Build Command`: `pip install -r requirements.txt`
   - `Start Command`: `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
4. Antes de desplegar, en `Environment` añade estas variables (copiar/pegar):

```env
USE_DATABASE=true
CELERY_ENABLED=false
WEBSOCKET_ENABLED=true
APP_RUNTIME_MODE=stable
OPTIMIZER_PROGRESS_INTERVAL=1.0
SQLALCHEMY_ECHO=false
DATABASE_URL=PEGA_AQUI_DATABASE_URL_DE_RENDER
REDIS_URL=PEGA_AQUI_REDIS_URL_DE_RENDER
OSRM_URL=http://187.77.33.218:5000/route/v1/driving
OSRM_TABLE_URL=http://187.77.33.218:5000/table/v1/driving
CORS_ORIGINS=https://TU_APP.vercel.app
CORS_ALLOW_VERCEL_PREVIEWS=true
```

5. Pulsa `Create Web Service`.

Cuando acabe, copia la URL pública del backend, por ejemplo:
- `https://tutti-backend.onrender.com`

---

## Paso 4: Ejecutar migraciones de DB

Hay que crear tablas, incluida `manual_schedules`.

En Render:

1. Entra en tu servicio backend.
2. Pulsa `Shell`.
3. Ejecuta exactamente:

```bash
cd db/migrations
alembic upgrade head
```

Si termina sin error, la DB ya está lista.

---

## Paso 5: Verificar backend

Abre en navegador:

1. `https://TU_BACKEND.onrender.com/health`
2. `https://TU_BACKEND.onrender.com/docs`

Si abre `health` y `docs`, backend OK.

---

## Paso 6: Desplegar frontend en Vercel

1. Abre: `https://vercel.com/dashboard`
2. Pulsa `Add New...` -> `Project`.
3. Importa el mismo repo.
4. En configuración del proyecto:
   - Si te pide root, usa `frontend`
5. En `Environment Variables` añade:

```env
VITE_API_URL=https://TU_BACKEND.onrender.com
VITE_WS_URL=wss://TU_BACKEND.onrender.com
```

6. Pulsa `Deploy`.

---

## Paso 7: Arreglar CORS con URL real de Vercel

Cuando Vercel termine:

1. Copia la URL final del frontend (ejemplo: `https://tutti-optimizer.vercel.app`).
2. Vuelve a Render -> backend -> `Environment`.
3. Edita `CORS_ORIGINS` y pega:

```env
CORS_ORIGINS=https://tutti-optimizer.vercel.app
```

Si usas dominio propio y preview, separa por comas:

```env
CORS_ORIGINS=https://tutti-optimizer.vercel.app,https://www.tu-dominio.com
```

4. Guarda y redeploy automático.

---

## Paso 8: Prueba funcional mínima (importante)

Haz esta prueba en tu app en Vercel:

1. Sube excels.
2. Ejecuta optimización.
3. Pulsa `Guardar` o `Publicar`.
4. Reinicia backend en Render (`Manual Deploy` o `Restart`).
5. Vuelve a abrir el día guardado.

Resultado esperado:
- El horario sigue ahí (persistido en DB).
- No se pierde por reinicio.

---

## Errores típicos y solución rápida

1. `CORS error` en navegador:
- Revisa `CORS_ORIGINS` en backend.
- Debe incluir exactamente la URL de Vercel (https).

2. `405 Method Not Allowed` al publicar:
- Este backend ya soporta:
  - `POST /api/schedules/update`
  - `POST /api/schedules/manual` (alias)

3. `No module named ...` o arranque fallido:
- Verifica `Root Directory = backend` en Render.

4. DB conectada pero no guarda:
- Ejecuta migración otra vez:
  - `cd db/migrations && alembic upgrade head`

---

## Checklist final (marca todo antes de abrir beta)

- [ ] `health` backend responde OK
- [ ] `/docs` backend abre
- [ ] frontend en Vercel carga sin errores
- [ ] upload + optimize funciona
- [ ] guardar/publicar funciona
- [ ] reinicio backend no borra horarios guardados
