@echo off
cd /d C:\Users\anoth\Documents\myproject\zhixianyunshu
set PYTHONPATH=C:\Users\anoth\Documents\myproject\zhixianyunshu
python -m eval.archive.quick_ablation --force %*
