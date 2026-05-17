#!/bin/bash
# 监控季节分析脚本运行状态

echo "=========================================="
echo "季节分析脚本运行监控"
echo "=========================================="
echo ""

LOG_FILE="/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_serial.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ 日志文件不存在"
    exit 1
fi

# 显示最后几行
echo "📊 最新进度:"
echo "---"
tail -5 "$LOG_FILE" | grep -E "(计算季节|事件数|总运行时间|完成)"
echo ""

# 检查进程是否在运行
if ps aux | grep "seasonal_analysis_serial.py" | grep -v grep > /dev/null; then
    echo "✅ 脚本正在运行中..."
    
    # 估算剩余时间
    PROGRESS=$(tail -20 "$LOG_FILE" | grep "计算季节" | tail -1 | sed -n 's/.*\([0-9]\+\)%.*(\([0-9.]\+\)事件\/s).*/\1 \2/p')
    if [ ! -z "$PROGRESS" ]; then
        PERCENT=$(echo $PROGRESS | awk '{print $1}')
        SPEED=$(echo $PROGRESS | awk '{print $2}')
        REMAINING=$((8894899 * (100 - PERCENT) / 100))
        if [ $(echo "$SPEED > 0" | bc) -eq 1 ]; then
            TIME_LEFT=$(echo "$REMAINING / $SPEED / 60" | bc)
            echo "📈 进度: ${PERCENT}%"
            echo "⚡ 速度: ${SPEED} 事件/秒"
            echo "⏱️  预计剩余时间: ~${TIME_LEFT} 分钟"
        fi
    fi
else
    echo "⭕ 脚本已停止或未运行"
    
    # 检查是否完成
    if grep -q "季节性分析完成" "$LOG_FILE"; then
        echo "✅ 分析已完成！"
        RUNTIME=$(grep "总运行时间" "$LOG_FILE" | tail -1)
        echo "$RUNTIME"
    fi
fi

echo ""
echo "要实时查看日志，运行: tail -f $LOG_FILE"
