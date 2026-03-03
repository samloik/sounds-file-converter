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

# Улучшенная конфигурация форматов с кодеком и параметрами
SUPPORTED_FORMATS: Dict[str, Dict[str, Any]] = {
    'mp3': {'format': 'mp3', 'codec': 'libmp3lame', 'bitrate': '192k'},
    'wav': {'format': 'wav', 'codec': 'pcm_s16le'},
    'aac': {'format': 'adts', 'codec': 'aac', 'bitrate': '192k'},
    'ogg': {'format': 'ogg', 'codec': 'libvorbis', 'bitrate': '192k'},
    'flac': {'format': 'flac', 'codec': 'flac'},
    'aiff': {'format': 'aiff', 'codec': 'pcm_s16be'},
    'wma': {'format': 'asf', 'codec': 'wmav2', 'bitrate': '192k'},
    'm4a': {'format': 'ipod', 'codec': 'aac', 'bitrate': '192k'},
    'opus': {'format': 'ogg', 'codec': 'libopus', 'bitrate': '128k'},
    'amr': {'format': 'amr', 'codec': 'libopencore_amrnb'},
    'ac3': {'format': 'ac3', 'codec': 'ac3', 'bitrate': '192k'},
    'au': {'format': 'au', 'codec': 'pcm_mulaw'},
    'raw': {'format': 's16le', 'codec': 'pcm_s16le'},
    'pcm': {'format': 'wav', 'codec': 'pcm_s16le'},
    'mp2': {'format': 'mp2', 'codec': 'mp2', 'bitrate': '192k'},
    # Видеоформаты с аудио дорожкой
    'mp4': {'format': 'mp4', 'codec': 'aac', 'bitrate': '192k', 'video_codec': 'libx264'},
    'webm': {'format': 'webm', 'codec': 'libvorbis', 'bitrate': '192k', 'video_codec': 'libvpx'},
}

# Форматы только для аудио (без видео)
AUDIO_ONLY_FORMATS = ['mp3', 'wav', 'aac', 'ogg', 'flac', 'aiff', 'wma', 'm4a', 'opus', 'amr', 'ac3', 'au', 'raw',
                      'pcm', 'mp2']


async def run_in_thread(func, *args, **kwargs):
    """Запускает функцию в отдельном потоке"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, lambda: func(*args, **kwargs))


def convert_audio_file(input_path: str, output_path: str, target_format: str) -> None:
    """Конвертирует аудиофайл с использованием pydub с обработкой ошибок"""
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

        # Для видеоформатов добавляем черный экран
        if target_format in ['mp4', 'webm']:
            # Создаем простой черный видеофон
            duration_sec = len(audio) / 1000.0  # pydub работает в миллисекундах

            # Используем ffmpeg для создания видео с аудио
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c=black:s=640x480:d={duration_sec}',
                '-i', input_path,
                '-c:v', format_config.get('video_codec', 'libx264'),
                '-c:a', codec,
                '-shortest',
                output_path
            ]

            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                return
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg error: {e.stderr.decode()}")
                raise Exception(f"Ошибка создания видео: {e.stderr.decode()}")

        # Для аудиоформатов используем стандартный экспорт
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
            'type': 'video' if fmt in ['mp4', 'webm'] else 'audio'
        })
    return formats


# HTML шаблон (упрощенная версия)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Аудио Конвертер</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .content { padding: 40px; }
        .upload-area { border: 3px dashed #3498db; border-radius: 10px; padding: 40px; text-align: center; margin-bottom: 30px; transition: all 0.3s ease; cursor: pointer; }
        .upload-area:hover { border-color: #2980b9; background: #f8f9fa; }
        .format-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; margin: 20px 0; }
        .format-option { padding: 15px; border: 2px solid #e0e0e0; border-radius: 8px; text-align: center; cursor: pointer; transition: all 0.3s ease; }
        .format-option.selected { border-color: #27ae60; background: #27ae60; color: white; }
        .format-option.video { border-color: #e74c3c; }
        .convert-btn { width: 100%; padding: 20px; background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; border: none; border-radius: 10px; font-size: 1.2em; cursor: pointer; }
        .convert-btn:disabled { background: #bdc3c7; cursor: not-allowed; }
        .status { margin-top: 20px; padding: 15px; border-radius: 8px; text-align: center; }
        .status.info { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .file-info { margin: 15px 0; padding: 15px; background: #e8f4fd; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 Аудио Конвертер</h1>
            <p>Конвертация между 15+ аудиоформатами и 2 видеоформатами</p>
        </div>
        <div class="content">
            <div class="upload-area" id="uploadArea">
                <div style="font-size: 3em; margin-bottom: 15px;">📁</div>
                <h3>Перетащите аудиофайл сюда или нажмите для выбора</h3>
                <p>Поддерживаются: MP3, WAV, AAC, OGG, FLAC, M4A, WMA, OPUS и другие</p>
                <input type="file" id="fileInput" style="display: none;" accept="audio/*,video/*">
            </div>

            <div class="file-info" id="fileInfo" style="display: none;">
                <strong>Выбранный файл:</strong> <span id="fileName"></span><br>
                <strong>Размер:</strong> <span id="fileSize"></span>
            </div>

            <div>
                <label><strong>Выберите целевой формат:</strong></label>
                <div class="format-grid" id="formatGrid"></div>
            </div>

            <button class="convert-btn" id="convertBtn" disabled>🎯 Начать конвертацию</button>
            <div class="status" id="status" style="display: none;"></div>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-top: 30px;">
                <h3>📋 Поддерживаемые форматы:</h3>
                <p><strong>Аудио:</strong> MP3, WAV, AAC, OGG, FLAC, AIFF, WMA, M4A, OPUS, AMR, AC3, AU, RAW, PCM, MP2</p>
                <p><strong>Видео (с черным экраном):</strong> MP4, WebM</p>
            </div>
        </div>
    </div>

    <script>
        const formats = """ + str(get_supported_formats_list()) + """;

        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const formatGrid = document.getElementById('formatGrid');
        const convertBtn = document.getElementById('convertBtn');
        const status = document.getElementById('status');

        let selectedFile = null;
        let selectedFormat = 'mp3';

        // Инициализация форматов
        function initializeFormats() {
            formats.forEach(format => {
                const formatOption = document.createElement('div');
                formatOption.className = `format-option ${format.key === 'mp3' ? 'selected' : ''} ${format.type === 'video' ? 'video' : ''}`;
                formatOption.innerHTML = `
                    <div style="font-size: 1.5em;">${format.type === 'video' ? '🎥' : '🎵'}</div>
                    <div>${format.name}</div>
                `;
                formatOption.addEventListener('click', () => selectFormat(format.key, formatOption));
                formatGrid.appendChild(formatOption);
            });
        }

        function selectFormat(format, element) {
            selectedFormat = format;
            document.querySelectorAll('.format-option').forEach(opt => opt.classList.remove('selected'));
            element.classList.add('selected');
            updateConvertButton();
        }

        function updateConvertButton() {
            convertBtn.disabled = !selectedFile;
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // Обработчики событий
        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.style.background = '#e8f5e8'; });
        uploadArea.addEventListener('dragleave', () => { uploadArea.style.background = ''; });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.background = '';
            if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleFileSelect(e.target.files[0]);
        });

        function handleFileSelect(file) {
            if (!file.type.startsWith('audio/') && !file.type.startsWith('video/')) {
                showStatus('Пожалуйста, выберите аудио или видео файл', 'error');
                return;
            }

            selectedFile = file;
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            fileInfo.style.display = 'block';
            updateConvertButton();
            showStatus('Файл готов к конвертации', 'info');
        }

        function showStatus(message, type) {
            status.textContent = message;
            status.className = `status ${type}`;
            status.style.display = 'block';
        }

        convertBtn.addEventListener('click', async () => {
            if (!selectedFile) return;

            const formData = new FormData();
            formData.append('file', selectedFile);

            showStatus('Конвертация началась... Это может занять несколько минут для больших файлов', 'info');
            convertBtn.disabled = true;

            try {
                const response = await fetch(`/convert/${selectedFormat}`, { method: 'POST', body: formData });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `converted.${selectedFormat}`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                    showStatus('Конвертация завершена успешно! Файл скачивается...', 'info');
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || 'Неизвестная ошибка');
                }
            } catch (error) {
                showStatus(`Ошибка: ${error.message}`, 'error');
            } finally {
                convertBtn.disabled = false;
            }
        });

        document.addEventListener('DOMContentLoaded', initializeFormats);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def main_page():
    return HTML_TEMPLATE


@app.post("/convert/{target_format}")
async def convert_audio(
        target_format: str,
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
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
    await asyncio.sleep(10)  # Даем больше времени на скачивание
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Удален временный файл: {file_path}")


@app.get("/formats")
async def get_supported_formats():
    """Получить список поддерживаемых форматов"""
    return JSONResponse({
        "audio_formats": AUDIO_ONLY_FORMATS,
        "video_formats": ['mp4', 'webm'],
        "all_formats": list(SUPPORTED_FORMATS.keys())
    })


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return JSONResponse({"status": "healthy", "service": "Audio Converter API"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")