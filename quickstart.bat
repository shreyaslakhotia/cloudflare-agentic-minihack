@echo off
echo ========================================
echo Career Advice Platform - Quick Start
echo ========================================
echo.

echo Step 1: Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.10 or higher.
    pause
    exit /b 1
)
python --version
echo.

echo Step 2: Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
echo.

echo Step 3: Activating virtual environment...
call venv\Scripts\activate.bat
echo.

echo Step 4: Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo Dependencies installed.
echo.

echo Step 5: Downloading spaCy model...
python -m spacy download en_core_web_sm --quiet
echo spaCy model installed.
echo.

echo Step 6: Checking Redis...
docker ps | findstr redis >nul 2>&1
if errorlevel 1 (
    echo Starting Redis container...
    docker run -d --name career-redis -p 6379:6379 redis:7-alpine
    timeout /t 3 >nul
) else (
    echo Redis is already running.
)
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To start the API server:
echo   venv\Scripts\activate
echo   python -m uvicorn src.api.main:app --reload --port 8000
echo.
echo To run the test:
echo   python test_system.py
echo.
echo API will be available at: http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.
pause
