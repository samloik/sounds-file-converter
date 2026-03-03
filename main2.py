from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pydub import AudioSegment
import os
import uuid
import asyncio

app = FastAPI(title="Audio Converter API")

# Поддерживаемые форматы
SUPPORTED_FORMATS = {
    'mp3': 'mp3',
    'wav': 'wav',
    'aac': 'adts',
    'ogg': 'ogg',
    'flac': 'flac',
    'aiff': 'aiff',
    'wma': 'wma',
    'm4a': 'mp4',
    'opus': 'opus',
    'amr': 'amr_nb',
    'ac3': 'ac3',
    'au': 'au',
    'raw': 'raw',
    'pcm': 'pcm_s16le',
    'mp2': 'mp2',
    'mp4': 'mp4',
    '3gp': '3gp',
    'mov': 'mov',
    'webm': 'webm',
    'mkv': 'mkv'
}

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "converted"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/")
async def root():
    return {"message": "Audio Converter API", "supported_formats": list(SUPPORTED_FORMATS.keys())}


@app.post("/convert/{target_format}")
async def convert_audio(
        target_format: str,
        file: UploadFile = File(...)
):
    if target_format.lower() not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported format. Use: {list(SUPPORTED_FORMATS.keys())}")

    # Генерируем уникальные имена файлов
    file_id = str(uuid.uuid4())
    input_path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    output_path = f"{OUTPUT_DIR}/{file_id}.{target_format}"

    # Сохраняем загруженный файл
    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # Загружаем аудиофайл
        audio = AudioSegment.from_file(input_path)

        # Конвертируем в целевой формат
        await asyncio.to_thread(
            audio.export,
            output_path,
            format=SUPPORTED_FORMATS[target_format.lower()]
        )

    except Exception as e:
        # Удаляем временные файлы при ошибке
        os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        raise HTTPException(500, f"Conversion error: {str(e)}")

    finally:
        # Удаляем исходный файл
        if os.path.exists(input_path):
            os.remove(input_path)

    return FileResponse(
        output_path,
        media_type='application/octet-stream',
        filename=f"converted.{target_format}"
    )


@app.get("/formats")
async def get_supported_formats():
    return {"supported_formats": SUPPORTED_FORMATS}
