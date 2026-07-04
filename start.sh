#!/bin/bash
# SSM-1.0 — Project Buddy launcher for pb development

echo ""
echo "  ================================================"
echo "  SSM-1.0 — Project Buddy"
echo "  ================================================"

# ── 1. Start Ollama if not running ────────────────────────────────────────────
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
  echo "  [INFO] Ollama not running — starting it..."
  open -a Ollama 2>/dev/null || ollama serve &>/tmp/ollama_serve.log &
  echo "  [INFO] Waiting for Ollama to be ready..."
  for i in {1..15}; do
    sleep 1
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
      echo "  [OK] Ollama is ready."
      break
    fi
    if [ $i -eq 15 ]; then
      echo "  [ERROR] Ollama didn't start in time."
      echo "          Try manually: open -a Ollama"
      exit 1
    fi
  done
else
  echo "  [OK] Ollama already running."
fi

# ── 2. Install Python package if missing ──────────────────────────────────────
if ! python3 -c "import ollama" &>/dev/null; then
  echo "  [INFO] Installing ollama Python package..."
  pip3 install ollama --quiet --break-system-packages 2>/dev/null || \
  pip install ollama --quiet 2>/dev/null || \
  pip3 install ollama --quiet
  echo "  [OK] ollama package installed."
fi

# ── 3. Show available models ──────────────────────────────────────────────────
echo ""
echo "  Available models:"
curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(f'    - ' + m['name'])
" 2>/dev/null || echo "    (could not list models)"
echo ""

# ── 4. Launch SSM-1.0 ─────────────────────────────────────────────────────────
python3 run.py
