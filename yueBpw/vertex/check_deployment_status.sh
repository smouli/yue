#!/bin/bash

echo "🔍 YuE Deployment Status Check"
echo "==============================="
echo

# Check if deployment process is still running
if ps aux | grep -q "59968.*gcloud"; then
    echo "✅ Deployment process still running (PID: 59968)"
else
    echo "⏹️  Deployment process completed"
fi

echo

# Show recent deployment log
echo "📊 Recent deployment log:"
echo "-------------------------"
if [ -f "deployment.log" ]; then
    tail -10 deployment.log
else
    echo "❌ deployment.log not found"
fi

echo
echo "🔍 Full deployment log: tail -f deployment.log"
echo "🎯 Check endpoints: gcloud ai endpoints list --region=us-central1"
echo "📋 Chat history: cat chat_history_yue_fix.md" 