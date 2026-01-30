#!/bin/bash
set -e

echo "======================================"
echo "Reprocessing all items with concise pain points"
echo "======================================"

cd ~/Documents/vibing/hermes

echo ""
echo "Step 1: Rebuilding backend container..."
podman-compose down backend
podman-compose build backend
podman-compose up -d backend

echo ""
echo "Step 2: Waiting for backend to be ready..."
sleep 10

# Wait for health check
until curl -sf http://localhost:8000/api/health > /dev/null 2>&1; do
    echo "Waiting for backend..."
    sleep 2
done
echo "✓ Backend is ready"

echo ""
echo "Step 3: Marking items for reprocessing..."
podman exec -i $(podman ps -q -f name=backend) python mark_for_pain_points.py <<EOF
yes
EOF

echo ""
echo "Step 4: Starting batch reprocessing (100 items at a time)..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/jobs/reprocess-incomplete?max_items=100")
echo "$RESPONSE"

JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', 'null'))")

if [ "$JOB_ID" != "null" ]; then
    echo ""
    echo "✓ Reprocessing started with job ID: $JOB_ID"
    echo ""
    echo "Monitor progress with:"
    echo "  curl http://localhost:8000/api/jobs/$JOB_ID"
    echo ""
    echo "Run more batches with:"
    echo "  curl -X POST 'http://localhost:8000/api/jobs/reprocess-incomplete?max_items=100'"
else
    echo ""
    echo "No items to reprocess or error occurred"
fi

echo ""
echo "======================================"
echo "Done!"
echo "======================================"
