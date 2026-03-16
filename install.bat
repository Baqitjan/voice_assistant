@echo off
REM =============================================================================
REM LOQ-GENESIS | install.bat
REM Установка зависимостей для Windows 11 + CUDA 12.4
REM =============================================================================

echo ===========================================
echo    LOQ-GENESIS: ОРНАТУ БАСТАЛДЫ...
echo ===========================================
echo.

REM 1. Виртуалды орта құру
if not exist venv (
    echo [1/8] Виртуалды орта құрылуда (venv)...
    python -m venv venv
) else (
    echo [1/8] Виртуалды орта бар, өткізіп жібереміз.
)

REM Виртуалды ортаны белсендіру
call venv\Scripts\activate

REM 2. Pip-ті жаңарту
echo [2/8] Pip жаңартылуда...
python -m pip install --upgrade pip

REM 3. PyTorch + CUDA 12.4 (Ең басты бөлім)
echo [3/8] PyTorch 2.6.0 + CUDA 12.4 орнатылуда...
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

REM 4. NumPy 1.x (Маңызды! 2.x нұсқасы қате береді)
echo [4/8] NumPy 1.26.4 орнатылуда...
pip install numpy==1.26.4

REM 5. Faster-Whisper және ONNX (GPU қолдауымен)
echo [5/8] Faster-Whisper және ONNX-GPU орнатылуда...
pip install faster-whisper==1.0.3 onnxruntime-gpu==1.18.1

REM 6. TTS модульдері (Kokoro және Coqui)
echo [6/8] TTS модульдері орнатылуда...
pip install transformers==4.45.0 tokenizers==0.20.3 huggingface_hub==0.25.2
pip install kokoro-onnx==0.4.6 TTS==0.22.0

REM 7. Басқа қажетті құралдар
echo [7/8] Басқа кітапханалар (OpenCV, PyAutoGUI және т.б.)...
pip install Pillow==10.4.0 sounddevice==0.4.7 soundfile==0.12.1 requests==2.32.3 pyautogui==0.9.54 duckduckgo-search==6.3.7 schedule==1.2.2 pywin32 opencv-python

REM 8. Тексеру
echo.
echo [8/8] GPU тексерілуде...
python -c "import torch; print('CUDA қолжетімді:' if torch.cuda.is_available() else 'ҚАТЕ: CUDA табылмады!'); print('Қолданыстағы GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Жоқ')"

echo.
echo ===========================================
echo    ОРНАТУ АЯҚТАЛДЫ!
echo ===========================================
echo.
echo МАҢЫЗДЫ: Kokoro файлдарын (onnx және voices.bin) жобаның ішіне қоюды ұмытпа!
echo Енді ассистентті іске қосу үшін: python main.py
echo.
pause