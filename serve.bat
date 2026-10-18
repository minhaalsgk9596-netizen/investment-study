@echo off
REM 로컬 미리보기: 데이터를 docs 로 복사한 뒤 http://localhost:8000 에서 연다
cd /d "%~dp0"
robocopy data docs\data /E /NFL /NDL /NJH /NJS >nul
robocopy content docs\content /E /NFL /NDL /NJH /NJS >nul
start "" http://localhost:8000
python -m http.server 8000 -d docs
