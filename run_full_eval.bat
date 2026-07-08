@echo off
cd /d C:\Users\anoth\Documents\myproject\zhixianyunshu
set JUDGE_BACKEND_URL=http://localhost:8080
python -m eval.archive.run_full_only > eval\results\full_mode_opt.log 2>&1
