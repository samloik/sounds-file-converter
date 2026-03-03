from fastapi import FastAPI, File, UploadFile, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydub import AudioSegment
import os
import uuid
import asyncio
import logging
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Converter API",
    description="Сервис для конвертации аудиофайлов между различными форматами",
    version="1.0.0"
)

# Создаем executor для выполнения блокирующих операций
thread_pool = ThreadPoolExecutor(max_workers=4)

# Создаем директории для файлов
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "converted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Улучшенная конфигурация форматов
SUPPORTED_FORMATS: Dict[str, Dict[str, Any]] = {
    'mp3': {'format': 'mp3', 'codec': 'libmp3lame', 'bitrate': '192k', 'reliable': True},
    'wav': {'format': 'wav', 'codec': 'pcm_s16le', 'reliable': True},
    'aac': {'format': 'adts', 'codec': 'aac', 'bitrate': '192k', 'reliable': True},
    'ogg': {'format': 'ogg', 'codec': 'libvorbis', 'bitrate': '192k', 'reliable': True},
    'flac': {'format': 'flac', 'codec': 'flac', 'reliable': True},
    'aiff': {'format': 'aiff', 'codec': 'pcm_s16be', 'reliable': True},
    'wma': {'format': 'asf', 'codec': 'wmav2', 'bitrate': '192k', 'reliable': True},
    'm4a': {'format': 'ipod', 'codec': 'aac', 'bitrate': '192k', 'reliable': True},
    'opus': {'format': 'ogg', 'codec': 'libopus', 'bitrate': '128k', 'reliable': True},
}


async def run_in_thread(func, *args, **kwargs):
    """Запускает функцию в отдельном потоке"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, lambda: func(*args, **kwargs))


def convert_audio_file(input_path: str, output_path: str, target_format: str) -> None:
    """Конвертирует аудиофайл с использованием pydub"""
    try:
        # Загружаем аудиофайл
        audio = AudioSegment.from_file(input_path)

        # Получаем параметры формата
        format_config = SUPPORTED_FORMATS[target_format]
        format_name = format_config['format']
        codec = format_config.get('codec')

        # Параметры экспорта
        export_params = {'format': format_name}
        if codec:
            export_params['codec'] = codec
        if 'bitrate' in format_config:
            export_params['bitrate'] = format_config['bitrate']

        # Экспортируем файл
        audio.export(output_path, **export_params)

    except Exception as e:
        logger.error(f"Ошибка конвертации: {str(e)}")
        raise


def get_supported_formats_list() -> list:
    """Возвращает список поддерживаемых форматов для отображения"""
    formats = []
    for fmt, config in SUPPORTED_FORMATS.items():
        formats.append({
            'key': fmt,
            'name': fmt.upper(),
            'reliable': config.get('reliable', True)
        })
    return formats


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Главная страница с формой загрузки"""
    formats_list = get_supported_formats_list()
    return templates.TemplateResponse("index6.html", {
        "request": request,
        "formats": formats_list,
        "formats_json": json.dumps(formats_list)
    })


@app.post("/convert/{target_format}")
async def convert_audio(
        target_format: str,
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
    """Конвертирует загруженный аудиофайл в указанный формат"""
    # Проверяем поддерживается ли формат
    if target_format.lower() not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат. Используйте: {list(SUPPORTED_FORMATS.keys())}"
        )

    # Генерируем уникальные имена файлов
    file_id = str(uuid.uuid4())
    input_path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    output_path = f"{OUTPUT_DIR}/{file_id}.{target_format}"

    logger.info(f"Начата конвертация файла {file.filename} в формат {target_format}")

    try:
        # Сохраняем загруженный файл
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Выполняем конвертацию в отдельном потоке
        await run_in_thread(convert_audio_file, input_path, output_path, target_format.lower())

        logger.info(f"Конвертация завершена: {file.filename} -> {target_format}")

    except Exception as e:
        logger.error(f"Ошибка конвертации: {str(e)}")

        # Удаляем временные файлы при ошибке
        for path in [input_path, output_path]:
            if os.path.exists(path):
                os.remove(path)

        raise HTTPException(
            status_code=500,
            detail=f"Ошибка конвертации: {str(e)}"
        )

    finally:
        # Удаляем исходный файл
        if os.path.exists(input_path):
            os.remove(input_path)

    # Фоновая задача для очистки выходного файла после отправки
    if background_tasks:
        background_tasks.add_task(cleanup_file, output_path)

    # Возвращаем сконвертированный файл
    return FileResponse(
        output_path,
        media_type='application/octet-stream',
        filename=f"converted_{file.filename.rsplit('.', 1)[0]}.{target_format}"
    )


async def cleanup_file(file_path: str):
    """Удалить файл после отправки"""
    await asyncio.sleep(10)
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Удален временный файл: {file_path}")


@app.get("/formats")
async def get_supported_formats():
    """Получить список поддерживаемых форматов"""
    return JSONResponse({
        "supported_formats": list(SUPPORTED_FORMATS.keys()),
        "total_formats": len(SUPPORTED_FORMATS)
    })


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return JSONResponse({"status": "healthy", "service": "Audio Converter API"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")