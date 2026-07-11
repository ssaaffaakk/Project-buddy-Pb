"""
SSM-1.0 → Hugging Face uploader
────────────────────────────────
Finds the LLaMA GGUF file Ollama downloaded, then pushes it to
your Hugging Face account as  <your-username>/SSM-1.0

Usage:
    python upload_to_hf.py

Requirements:
    pip install huggingface_hub
"""

import sys
import subprocess
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

HF_REPO_NAME  = "SSM-1.0"          # will appear as <your-username>/SSM-1.0
GGUF_FILENAME = "ssm-1.0.gguf"     # name it will have on HF

MODEL_CARD = """\
---
language:
- en
library_name: gguf
tags:
- llama
- gguf
- chat
- assistant
- projectbuddy
license: llama3
base_model: meta-llama/Meta-Llama-3-8B-Instruct
---

# SSM-1.0

**SSM-1.0** is the AI assistant powering [ProjectBuddy](https://github.com), a
collaboration platform for university students.

Built on Meta LLaMA 3, customised with the SSM-1.0 identity and system prompt
for academic project assistance.

## Model details

| Property | Value |
|---|---|
| Base model | Meta LLaMA 3 (8B Instruct) |
| Format | GGUF (quantized) |
| Context window | 8 192 tokens |
| Languages | English |

## System prompt

```
You are SSM-1.0, the AI assistant built into ProjectBuddy —
a collaboration platform for university students.
Help users with project planning, finding teammates, managing
deadlines, skill development, and general study advice.
Be concise, warm, and practical.
```

## Usage

```python
from huggingface_hub import InferenceClient

client = InferenceClient("meta-llama/Llama-3.1-8B-Instruct")
response = client.chat_completion(
    messages=[
        {"role": "system", "content": "You are SSM-1.0 ..."},
        {"role": "user",   "content": "Hello, who are you?"},
    ]
)
print(response.choices[0].message.content)
```
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def find_ollama_gguf() -> Path | None:
    """Search common Ollama model storage locations for a GGUF blob."""
    search_roots = [
        Path.home() / ".ollama" / "models" / "blobs",
        Path("/usr/share/ollama/.ollama/models/blobs"),
    ]
    for root in search_roots:
        if not root.exists():
            continue
        # Ollama stores model blobs as sha256-* files; pick the largest (the model weights)
        blobs = sorted(root.glob("sha256-*"), key=lambda p: p.stat().st_size, reverse=True)
        # Filter: real model files are usually >1 GB
        big = [b for b in blobs if b.stat().st_size > 500_000_000]
        if big:
            print(f"  Found model blob: {big[0]}  ({big[0].stat().st_size / 1e9:.1f} GB)")
            return big[0]
    return None


def login_hf():
    """Interactive HF login."""
    try:
        from huggingface_hub import login, whoami
        try:
            info = whoami()
            print(f"  Already logged in as: {info['name']}")
            return info["name"]
        except Exception:
            pass
        print("\n  Go to https://huggingface.co/settings/tokens")
        print("  Create a token with WRITE access, then paste it here.")
        token = input("  HF token: ").strip()
        login(token=token)
        info = whoami()
        print(f"  Logged in as: {info['name']}")
        return info["name"]
    except ImportError:
        print("[ERROR] huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)


def push_to_hf(gguf_path: Path, hf_username: str):
    from huggingface_hub import HfApi, create_repo

    repo_id = f"{hf_username}/{HF_REPO_NAME}"
    api = HfApi()

    print(f"\n  Creating repo: {repo_id}")
    create_repo(repo_id=repo_id, repo_type="model", exist_ok=True, private=False)

    # Upload model card
    print("  Uploading model card (README.md)...")
    api.upload_file(
        path_or_fileobj=MODEL_CARD.encode(),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="model",
        commit_message="Add SSM-1.0 model card",
    )

    # Upload GGUF
    size_gb = gguf_path.stat().st_size / 1e9
    print(f"  Uploading {GGUF_FILENAME} ({size_gb:.1f} GB) — this may take a while...")
    api.upload_file(
        path_or_fileobj=str(gguf_path),
        path_in_repo=GGUF_FILENAME,
        repo_id=repo_id,
        repo_type="model",
        commit_message=f"Add SSM-1.0 GGUF model ({size_gb:.1f} GB)",
    )

    print(f"\n  ✓ Done! Model live at: https://huggingface.co/{repo_id}")
    return repo_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*54)
    print("  SSM-1.0 → Hugging Face uploader")
    print("="*54 + "\n")

    # 1. Install dependency
    try:
        import huggingface_hub
    except ImportError:
        print("  Installing huggingface_hub...")
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "huggingface_hub", "-q"], check=True)
        import huggingface_hub  # noqa

    # 2. Find model
    print("  Looking for Ollama model files...")
    gguf_path = find_ollama_gguf()
    if not gguf_path:
        print("\n  [ERROR] Could not find Ollama model files.")
        print("  Ollama stores models in ~/.ollama/models/blobs/")
        print("  Make sure you've pulled a model first: ollama pull llama3.2")
        sys.exit(1)

    # 3. HF login
    hf_username = login_hf()

    # 4. Push
    repo_id = push_to_hf(gguf_path, hf_username)

    print("\n  Next step:")
    print("  Add this to your .env / Render environment variables:")
    print("    HF_MODEL_ID = meta-llama/Llama-3.1-8B-Instruct")
    print("    HF_TOKEN    = <your read token from huggingface.co/settings/tokens>")
    print(f"\n  Your SSM-1.0 model page: https://huggingface.co/{repo_id}")


if __name__ == "__main__":
    main()
