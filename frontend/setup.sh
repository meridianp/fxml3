#!/bin/bash

# FXML4 UI Setup Script
echo "🚀 Setting up FXML4 Trading Platform Frontend..."

# Check Node.js version
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js 18+ is required. Current version: $(node --version)"
    exit 1
fi

echo "✅ Node.js version check passed: $(node --version)"

# Install dependencies
echo "📦 Installing dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed successfully"

# Copy environment file
if [ ! -f .env.local ]; then
    echo "📝 Creating environment configuration..."
    cp .env.example .env.local
    echo "✅ Environment file created (.env.local)"
    echo "⚠️  Please review and update .env.local with your configuration"
else
    echo "ℹ️  Environment file already exists"
fi

# Type check
echo "🔍 Running TypeScript type check..."
npm run type-check

if [ $? -ne 0 ]; then
    echo "❌ TypeScript type check failed"
    exit 1
fi

echo "✅ TypeScript type check passed"

# Lint check
echo "🧹 Running linter..."
npm run lint

if [ $? -ne 0 ]; then
    echo "⚠️  Linter found issues (can be fixed with npm run lint:fix)"
else
    echo "✅ Code quality check passed"
fi

echo ""
echo "🎉 FXML4 UI setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Review and update .env.local with your backend API URL"
echo "2. Ensure FXML4 backend is running on the configured port"
echo "3. Start the development server:"
echo "   npm run dev"
echo ""
echo "The application will be available at:"
echo "   http://localhost:3000"
echo ""
echo "API Documentation:"
echo "   http://localhost:8000/docs (backend API)"
echo ""
echo "Happy trading! 📈"
