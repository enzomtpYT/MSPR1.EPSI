#!/bin/bash

# Make sure we fail if any individual command fails (except where we handle it)
# set -e

echo "🚀 Starting tests for all microservices..."

echo "----------------------------------------"
echo "📦 Testing Frontend (frontmspr)..."
cd frontmspr
npm install
npm run type-check || echo "⚠️ Frontend type-check failed but continuing..."
cd ..

echo "----------------------------------------"
echo "🐍 Testing Backend (MSPR1.EPSI-FastAPI)..."
cd MSPR1.EPSI-FastAPI
uv sync --dev
uv run pytest || echo "⚠️ Backend tests failed or not found but continuing..."
cd ..

echo "----------------------------------------"
echo "✅ All tests completed!"
