#!/bin/bash
set -e

echo "🚀 Publishing takopi-engine-kimi to PyPI..."

# Clean previous builds
rm -rf dist/

# Build the package
uv build

# Check the distribution
uv run twine check dist/*

# Upload to PyPI
if [ -z "$TWINE_PASSWORD" ]; then
    echo "⚠️  TWINE_PASSWORD not set. Please export your PyPI API token:"
    echo "   export TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE"
    exit 1
fi

uv run twine upload dist/*

echo "✅ Published successfully!"
