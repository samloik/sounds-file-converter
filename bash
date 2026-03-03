# Создайте структуру папок
mkdir -p templates static

# Создайте файл requirements.txt
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
pydub==0.25.1
python-multipart==0.0.6
EOF

# Создайте файл запуска
cat > run.py << 'EOF'
import uvicorn
ls
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
EOF

pip install -r requirements.txt

sudo apt update && sudo apt install ffmpeg

