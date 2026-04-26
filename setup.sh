#!/bin/bash
echo "============================================"
echo " InstaReach v3 - Setup"
echo "============================================"

echo "[1/3] Installing Node.js dependencies..."
npm install || { echo "ERROR: npm install failed"; exit 1; }

echo "[2/3] Installing Python dependencies..."
pip3 install -r requirements.txt || pip install -r requirements.txt || { echo "ERROR: pip install failed. Make sure Python 3 is installed."; exit 1; }

echo "[3/3] Setting up .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from example. Edit .env and set your credentials."
else
    echo ".env already exists, skipping."
fi

echo ""
echo "============================================"
echo " Setup complete!"
echo " Edit .env with your credentials, then run:"
echo "   npm start"
echo " Open: http://localhost:3000"
echo "============================================"
