from fastapi import FastAPI, File, UploadFile, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydub import AudioSegment
import os
import uuid
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Converter API",
    description="Сервис для конвертации аудиофайлов между различными форматами",
    version="1.0.0"
)

# Создаем executor для выполнения блокирующих операций
thread_pool = ThreadPoolExecutor()

# Создаем директории для файлов
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "converted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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

# Создаем HTML шаблон
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Аудио Конвертер</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }

        .content {
            padding: 40px;
        }

        .upload-area {
            border: 3px dashed #3498db;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin-bottom: 30px;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .upload-area:hover {
            border-color: #2980b9;
            background: #f8f9fa;
        }

        .upload-area.dragover {
            border-color: #27ae60;
            background: #e8f5e8;
        }

        .upload-icon {
            font-size: 3em;
            color: #3498db;
            margin-bottom: 15px;
        }

        .file-input {
            display: none;
        }

        .format-selector {
            margin: 30px 0;
        }

        .format-selector label {
            display: block;
            margin-bottom: 10px;
            font-weight: bold;
            color: #2c3e50;
        }

        .format-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }

        .format-option {
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: white;
        }

        .format-option:hover {
            border-color: #3498db;
            transform: translateY(-2px);
        }

        .format-option.selected {
            border-color: #27ae60;
            background: #27ae60;
            color: white;
        }

        .convert-btn {
            width: 100%;
            padding: 20px;
            background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1.2em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .convert-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(39, 174, 96, 0.3);
        }

        .convert-btn:disabled {
            background: #bdc3c7;
            cursor: not-allowed;
            transform: none;
        }

        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            display: none;
        }

        .status.info {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .supported-formats {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin-top: 30px;
        }

        .format-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }

        .format-badge {
            background: #3498db;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.9em;
        }

        .file-info {
            margin-top: 15px;
            padding: 15px;
            background: #e8f4fd;
            border-radius: 8px;
            display: none;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            margin-top: 10px;
            overflow: hidden;
            display: none;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
            width: 0%;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 Аудио Конвертер</h1>
            <p>Бесплатное онлайн-преобразование аудиофайлов между 20+ форматами</p>
        </div>

        <div class="content">
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📁</div>
                <h3>Перетащите аудиофайл сюда или нажмите для выбора</h3>
                <p>Поддерживаются все популярные аудиоформаты</p>
                <input type="file" id="fileInput" class="file-input" accept="audio/*,video/*">
            </div>

            <div class="file-info" id="fileInfo">
                <strong>Выбранный файл:</strong> <span id="fileName"></span>
                <br>
                <strong>Размер:</strong> <span id="fileSize"></span>
            </div>

            <div class="format-selector">
                <label>Выберите целевой формат:</label>
                <div class="format-grid" id="formatGrid">
                    <!-- Форматы будут добавлены через JavaScript -->
                </div>
            </div>

            <button class="convert-btn" id="convertBtn" disabled>
                🎯 Начать конвертацию
            </button>

            <div class="progress-bar" id="progressBar">
                <div class="progress-fill" id="progressFill"></div>
            </div>

            <div class="status" id="status"></div>

            <div class="supported-formats">
                <h3>📋 Поддерживаемые форматы конвертации:</h3>
                <div class="format-list" id="formatList">
                    <!-- Список форматов будет добавлен через JavaScript -->
                </div>
            </div>
        </div>
    </div>

    <script>
        // Элементы DOM
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const formatGrid = document.getElementById('formatGrid');
        const formatList = document.getElementById('formatList');
        const convertBtn = document.getElementById('convertBtn');
        const status = document.getElementById('status');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');

        let selectedFile = null;
        let selectedFormat = 'mp3';

        // Поддерживаемые форматы
        const supportedFormats = {
            'mp3': 'MP3', 'wav': 'WAV', 'aac': 'AAC', 'ogg': 'OGG', 
            'flac': 'FLAC', 'aiff': 'AIFF', 'wma': 'WMA', 'm4a': 'M4A',
            'opus': 'Opus', 'amr': 'AMR', 'ac3': 'AC3', 'au': 'AU',
            'raw': 'RAW', 'pcm': 'PCM', 'mp2': 'MP2', 'mp4': 'MP4',
            '3gp': '3GP', 'mov': 'MOV', 'webm': 'WebM', 'mkv': 'MKV'
        };

        // Инициализация форматов
        function initializeFormats() {
            // Сетка выбора формата
            Object.entries(supportedFormats).forEach(([key, name]) => {
                const formatOption = document.createElement('div');
                formatOption.className = `format-option ${key === 'mp3' ? 'selected' : ''}`;
                formatOption.innerHTML = `
                    <div style="font-size: 1.5em; margin-bottom: 5px;">${getFormatIcon(key)}</div>
                    <div>${name}</div>
                `;
                formatOption.addEventListener('click', () => selectFormat(key, formatOption));
                formatGrid.appendChild(formatOption);
            });

            // Список всех форматов
            Object.entries(supportedFormats).forEach(([key, name]) => {
                const formatBadge = document.createElement('span');
                formatBadge.className = 'format-badge';
                formatBadge.textContent = name;
                formatList.appendChild(formatBadge);
            });
        }

        // Получение иконки для формата
        function getFormatIcon(format) {
            const icons = {
                'mp3': '🎵', 'wav': '🎧', 'aac': '🔊', 'ogg': '🎼',
                'flac': '💿', 'aiff': '🎚️', 'wma': '🏷️', 'm4a': '📱',
                'opus': '🌐', 'amr': '📞', 'ac3': '🎬', 'au': '☀️',
                'raw': '⚡', 'pcm': '📊', 'mp2': '🎹', 'mp4': '🎥',
                '3gp': '📹', 'mov': '🎞️', 'webm': '🌍', 'mkv': '📺'
            };
            return icons[format] || '📄';
        }

        // Выбор формата
        function selectFormat(format, element) {
            selectedFormat = format;

            // Убираем выделение у всех элементов
            document.querySelectorAll('.format-option').forEach(opt => {
                opt.classList.remove('selected');
            });

            // Добавляем выделение выбранному элементу
            element.classList.add('selected');
            updateConvertButton();
        }

        // Обновление состояния кнопки конвертации
        function updateConvertButton() {
            convertBtn.disabled = !selectedFile;
        }

        // Форматирование размера файла
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // Обработчики событий для drag and drop
        uploadArea.addEventListener('click', () => fileInput.click());

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');

            if (e.dataTransfer.files.length) {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        // Обработчик выбора файла
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                handleFileSelect(e.target.files[0]);
            }
        });

        // Обработка выбранного файла
        function handleFileSelect(file) {
            // Проверка типа файла
            if (!file.type.startsWith('audio/') && !file.type.startsWith('video/')) {
                showStatus('Пожалуйста, выберите аудио или видео файл', 'error');
                return;
            }

            selectedFile = file;

            // Показываем информацию о файле
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            fileInfo.style.display = 'block';

            updateConvertButton();
            showStatus('Файл готов к конвертации', 'info');
        }

        // Показать статус
        function showStatus(message, type) {
            status.textContent = message;
            status.className = `status ${type}`;
            status.style.display = 'block';
        }

        // Скрыть статус
        function hideStatus() {
            status.style.display = 'none';
        }

        // Обработчик конвертации
        convertBtn.addEventListener('click', async () => {
            if (!selectedFile) return;

            const formData = new FormData();
            formData.append('file', selectedFile);

            showStatus('Конвертация началась...', 'info');
            progressBar.style.display = 'block';
            progressFill.style.width = '30%';
            convertBtn.disabled = true;

            try {
                const response = await fetch(`/convert/${selectedFormat}`, {
                    method: 'POST',
                    body: formData
                });

                progressFill.style.width = '70%';

                if (response.ok) {
                    // Скачиваем файл
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = `converted.${selectedFormat}`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);

                    progressFill.style.width = '100%';
                    showStatus('Конвертация завершена успешно! Файл скачивается...', 'info');

                    setTimeout(() => {
                        progressBar.style.display = 'none';
                        progressFill.style.width = '0%';
                        convertBtn.disabled = false;
                    }, 2000);

                } else {
                    const error = await response.text();
                    throw new Error(error);
                }

            } catch (error) {
                console.error('Error:', error);
                showStatus(`Ошибка конвертации: ${error.message}`, 'error');
                progressBar.style.display = 'none';
                convertBtn.disabled = false;
            }
        });

        // Инициализация при загрузке страницы
        document.addEventListener('DOMContentLoaded', initializeFormats);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def main_page():
    return HTML_TEMPLATE


async def run_in_thread(func, *args, **kwargs):
    """Запускает функцию в отдельном потоке (аналог asyncio.to_thread для Python < 3.9)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, lambda: func(*args, **kwargs))


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

    # Проверяем тип файла
    if not file.content_type.startswith(('audio/', 'video/')):
        raise HTTPException(
            status_code=400,
            detail="Пожалуйста, загрузите аудио или видео файл"
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

        # Загружаем и конвертируем аудиофайл в отдельном потоке
        audio = await run_in_thread(AudioSegment.from_file, input_path)

        # Выполняем экспорт в отдельном потоке
        await run_in_thread(
            audio.export,
            output_path,
            format=SUPPORTED_FORMATS[target_format.lower()]
        )

        logger.info(f"Конвертация завершена: {file.filename} -> {target_format}")

    except Exception as e:
        logger.error(f"Ошибка конвертации: {str(e)}")

        # Удаляем временные файлы при ошибке
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

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
    await asyncio.sleep(1)  # Даем время на скачивание
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Удален временный файл: {file_path}")


@app.get("/formats")
async def get_supported_formats():
    """Получить список поддерживаемых форматов"""
    return JSONResponse({
        "supported_formats": SUPPORTED_FORMATS,
        "total_formats": len(SUPPORTED_FORMATS)
    })


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return JSONResponse({
        "status": "healthy",
        "service": "Audio Converter API",
        "version": "1.0.0"
    })


@app.get("/cleanup")
async def cleanup_temp_files():
    """Очистить все временные файлы (для администрирования)"""
    deleted_files = []

    for directory in [UPLOAD_DIR, OUTPUT_DIR]:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                os.remove(file_path)
                deleted_files.append(filename)
            except Exception as e:
                logger.error(f"Ошибка удаления {file_path}: {e}")

    return JSONResponse({
        "message": "Очистка завершена",
        "deleted_files": deleted_files,
        "total_deleted": len(deleted_files)
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )