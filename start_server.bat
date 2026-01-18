@echo off
echo ============================================
echo  Запуск Async Population Service
echo ============================================
echo.

REM Проверяем Python
py --version
if errorlevel 1 (
    echo Python не найден! Установите Python 3.8+
    pause
    exit /b 1
)

REM Создаем виртуальное окружение если его нет
if not exist "venv" (
    echo Создание виртуального окружения...
    python -m venv venv
)

REM Активируем окружение
echo Активация виртуального окружения...
call venv\Scripts\activate.bat

REM Устанавливаем зависимости
echo Установка зависимостей...
pip install fastapi uvicorn httpx python-dotenv

echo.
echo ============================================
echo  Сервис запускается на:
echo  http://127.0.0.1:8081
echo  Документация: http://127.0.0.1:8081/docs
echo  Health check: http://127.0.0.1:8081/health
echo ============================================
echo.

REM Запускаем сервер
py -m uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload

pause