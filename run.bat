@echo off
echo ========================================
echo  Запуск Async Population Service
echo  Django: 127.0.0.1:8000
echo  Frontend: 127.0.0.1:3000
echo  Async Service: 127.0.0.1:8081
echo ========================================

REM Активируем виртуальное окружение
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Виртуальное окружение активировано
) else (
    echo Создание виртуального окружения...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Установка зависимостей...
    pip install -r requirements.txt
)

echo Запуск сервера...
echo API доступен по адресу: http://127.0.0.1:8081
echo Документация: http://127.0.0.1:8081/docs
echo Health check: http://127.0.0.1:8081/health

python -m uvicorn app.fastapi_app:app --host 127.0.0.1 --port 8081 --reload

pause