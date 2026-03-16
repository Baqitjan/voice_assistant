@echo off
REM =============================================================================
REM LOQ-GENESIS | install.bat
REM Установка зависимостей для Windows 11 + CUDA 12.4
REM Запускать из корня проекта: .\install.bat
REM =============================================================================

echo === LOQ-GENESIS INSTALLER ===
echo.

REM 1. PyTorch с CUDA 12.4 (должен быть установлен ПЕРВЫМ)
echo [1/7] Установка PyTorch 2.6.0 + CUDA 12.4...
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

REM 2. Базовые зависимости (совместимые версии)
echo [2/7] Установка базовых зависимостей...
pip install numpy==1.26.4 Pillow==10.4.0 sounddevice==0.4.7 soundfile==0.12.1

REM 3. Faster-Whisper (GPU)
echo [3/7] Установка Faster-Whisper...
pip install faster-whisper==1.0.3 onnxruntime-gpu==1.18.1

REM 4. Transformers (строго 4.45.0 для совместимости с TTS)
echo [4/7] Установка Transformers 4.45.0...
pip install transformers==4.45.0 tokenizers==0.20.3 huggingface_hub==0.25.2

REM 5. TTS (XTTS v2)
echo [5/7] Установка Coqui TTS (XTTS v2)...
pip install TTS==0.22.0

REM 6. Kokoro ONNX TTS
echo [6/7] Установка kokoro-onnx...
pip install kokoro-onnx==0.4.6

REM 7. Прочие зависимости
echo [7/7] Установка прочих зависимостей...
pip install requests==2.32.3 pyautogui==0.9.54 duckduckgo-search==6.3.7 schedule==1.2.2 pywin32

echo.
echo === Установка завершена! ===
echo.
echo ВАЖНО: Скачайте вручную файлы Kokoro:
echo   - kokoro-v0_19.onnx
echo   - voices.bin
echo   Ссылка: https://github.com/thewh1teagle/kokoro-onnx/releases
echo   Положите их в корень проекта LOQ-GENESIS.
echo.
echo Для проверки GPU: python -c "import torch; print(torch.cuda.is_available())"
pause
