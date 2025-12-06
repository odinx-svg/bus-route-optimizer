@echo off
echo Starting Tutti System...

start "Tutti Backend" cmd /k "cd backend && pip install -r requirements.txt && uvicorn main:app --reload"
start "Tutti Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo System starting...
echo Backend will be at http://localhost:8000
echo Frontend will be at http://localhost:5173
pause
