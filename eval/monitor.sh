#!/bin/bash
# 实时监控消融实验进度
# 用法: bash eval/monitor.sh

LOG_FILE="/tmp/ablation.log"
RESULTS_DIR="eval/results"

echo "=== 消融实验实时监控 ==="
echo "日志文件: $LOG_FILE"
echo ""

while true; do
    clear
    echo "=== 消融实验实时监控 ($(date '+%H:%M:%S')) ==="
    echo ""

    # 从日志提取进度
    if [ -f "$LOG_FILE" ]; then
        TOTAL=$(grep -c "\[.*\/96\]" "$LOG_FILE" 2>/dev/null || echo 0)
        OK_COUNT=$(grep -c "\[.*\/96\] OK" "$LOG_FILE" 2>/dev/null || echo 0)
        FAIL_COUNT=$(grep -c "\[.*\/96\] FAIL" "$LOG_FILE" 2>/dev/null || echo 0)

        echo "进度: $TOTAL/96 (OK: $OK_COUNT, FAIL: $FAIL_COUNT)"
        if [ $TOTAL -gt 0 ]; then
            RATE=$(echo "scale=1; $OK_COUNT * 100 / $TOTAL" | bc 2>/dev/null || echo "?")
            echo "成功率: ${RATE}%"
        fi
        echo ""

        # 最近 5 条结果
        echo "最近结果:"
        grep "\[.*\/96\]" "$LOG_FILE" | tail -5
        echo ""

        # 当前模式
        CURRENT_MODE=$(grep -o "\[./5\].*:" "$LOG_FILE" | tail -1)
        echo "当前模式: $CURRENT_MODE"
    else
        echo "等待日志文件..."
    fi

    echo ""
    echo "按 Ctrl+C 退出监控"
    sleep 10
done
