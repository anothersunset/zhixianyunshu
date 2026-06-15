@echo off
cd /d C:\Users\anoth\Documents\myproject\zhixianyunshu
set PYTHONPATH=C:\Users\anoth\Documents\myproject\zhixianyunshu
python -m eval.ablation --per-case --fast --cooldown 15 --pair all --force %*
