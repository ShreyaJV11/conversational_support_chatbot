@echo off
echo Starting MPS Support Chatbot...

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Build containers
echo Building containers...
docker-compose build

REM Start services
echo Starting services...
docker-compose up -d

REM Wait for services
echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Check health
echo Checking service health...
docker-compose ps

echo.
echo Deployment complete!
echo.
echo Access your services:
echo   - Backend API:  http://localhost:8000
echo   - Admin Panel:  http://localhost:3000
echo   - Chat Widget:  http://localhost:5173
echo   - API Docs:     http://localhost:8000/docs
echo.
echo Useful commands:
echo   - View logs:    docker-compose logs -f
echo   - Stop all:     docker-compose down
echo   - Restart:      docker-compose restart
echo.
pause
