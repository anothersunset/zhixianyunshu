@echo off
rem 在脚本所在目录（仓库根）运行消融实验
cd /d %~dp0
set PYTHONPATH=%~dp0
python -m eval.ablation --per-case --fast --cooldown 15 --pair all --force %*
