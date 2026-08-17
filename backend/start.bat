@echo off
echo ========================================
echo  SOAR GAZ Backend ishga tushirilmoqda...
echo ========================================

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo XATO: Python topilmadi. Python 3.10+ o'rnating.
    pause
    exit /b 1
)

if not exist venv (
    echo Virtual muhit yaratilmoqda...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Kutubxonalar o'rnatilmoqda...
pip install -r requirements.txt -q

echo Ma'lumotlar bazasi sozlanmoqda...
python manage.py migrate --run-syncdb -v 0

echo Admin foydalanuvchi tekshirilmoqda...
python create_admin.py

echo.
echo ========================================
echo  Server ishga tushdi: http://localhost:8001
echo  Admin panel:         http://localhost:8001/admin/
echo  API:                 http://localhost:8001/api/
echo ========================================
echo.

python manage.py runserver 8001
pause
