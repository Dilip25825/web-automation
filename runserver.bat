@echo off
color 2
cls
:: 1024 se 49151 ke beech random port generate karne ke liye logic
set /a "PORT=%RANDOM% * (49151 - 1024 + 1) / 32768 + 1024"

python manage.py runserver %PORT%


