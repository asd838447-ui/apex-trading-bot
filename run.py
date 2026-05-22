import os
import uvicorn

if __name__ == "__main__":
    # Dynamically read the PORT environment variable injected by cloud PaaS (Railway/Render)
    # Default to 8000 if not specified.
    port_env = os.environ.get("PORT", "8000")
    try:
        port = int(port_env)
    except ValueError:
        # Fallback to 8000 if PORT is a literal string like "$PORT" or invalid
        port = 8000

    print(f"[START] Launching FastAPI Backend on http://0.0.0.0:{port}...")
    uvicorn.run("server.main:app", host="0.0.0.0", port=port, workers=1)
