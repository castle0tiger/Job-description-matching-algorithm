@echo off
chcp 65001 > nul

if not exist .env (
  echo [ERROR] .env file not found. Please copy .env.example to .env
  echo         copy .env.example .env
  pause
  exit /b 1
)

echo [1/2] Installing packages...
pip install -r requirements.txt -q

echo [2/2] Starting server at http://localhost:8000
echo.
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
