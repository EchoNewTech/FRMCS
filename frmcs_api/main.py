import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.app:app", host="192.168.8.149", port=8000, reload=True)


# uv run .\main.py
