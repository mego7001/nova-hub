# Nova Hub (NH) — Single-host Platform (Plugins + Approvals)

## Setup
```bash
cd nova_hub
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

## Configure secrets
Copy `.env.example` -> `.env` and fill keys (never commit `.env`).

## Run
```bash
python main.py
```
