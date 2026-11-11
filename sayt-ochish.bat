@echo off
rem SOAR GAZ saytini to'g'ri (server orqali) ochadi.
rem index.html ni fayl sifatida ochmang: logo/ikonkalar "/..." yo'li bilan yuklanadi va file:// da topilmaydi.

cd /d "%~dp0backend"

rem SINOV KODI (faqat shu kompyuterda, DEBUG rejimida): quyidagi raqamga SMS yuborilmaydi, kod doim bir xil.
rem Serverga yuklanadigan nusxaga bu fayl KIRMAYDI. Kerak bo'lmasa bu qatorni o'chiring.
set "DJANGO_SINOV_MIJOZ=+998900000002:962857"

if not exist venv\Scripts\python.exe (
    echo XATO: backend\venv topilmadi. Avval backend\start.bat ni bir marta ishga tushiring.
    pause
    exit /b 1
)

rem Server allaqachon ishlayotgan bo'lmasa, yangi oynada ishga tushiramiz
netstat -ano | findstr /r /c:":8001 .*LISTENING" >nul
if errorlevel 1 (
    start "SOAR GAZ server" cmd /k "venv\Scripts\python.exe manage.py runserver 8001"
    timeout /t 4 /nobreak >nul
)

start "" http://localhost:8001/
