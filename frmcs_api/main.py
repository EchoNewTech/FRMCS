import uvicorn
from fastapi.staticfiles import StaticFiles

if __name__ == "__main__":
    uvicorn.run("app.app:app", host="192.168.1.219", port=8000, reload=True)


# uv run .\main.py
