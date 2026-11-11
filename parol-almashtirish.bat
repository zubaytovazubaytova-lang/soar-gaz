@echo off
rem Admin parolini almashtiradi. Parolni FAQAT siz yozasiz (yozayotganda ekranda ko'rinmaydi).
cd /d "%~dp0backend"

if not exist venv\Scripts\python.exe (
    echo XATO: backend\venv topilmadi.
    pause
    exit /b 1
)

echo.
echo Admin: +998918332249
echo Yangi parolni yozing va Enter bosing (yozayotganda ekranda hech narsa korinmaydi).
echo Keyin xuddi shu parolni yana bir marta yozing.
echo.
venv\Scripts\python.exe manage.py changepassword +998918332249
echo.
pause
