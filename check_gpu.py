"""Скрипт проверки окружения перед запуском LOQ-GENESIS."""
import sys

def check():
    print("=" * 50)
    print("LOQ-GENESIS | Проверка окружения")
    print("=" * 50)

    # Python
    print(f"Python: {sys.version}")

    # PyTorch + CUDA
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA доступна: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            mem = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"VRAM: {mem:.1f} GB")
    except ImportError:
        print("❌ PyTorch НЕ установлен!")

    # Faster-Whisper
    try:
        from faster_whisper import WhisperModel
        print("✅ faster-whisper установлен")
    except ImportError:
        print("❌ faster-whisper НЕ установлен")

    # Kokoro
    try:
        from kokoro_onnx import Kokoro
        print("✅ kokoro-onnx установлен")
    except ImportError:
        print("❌ kokoro-onnx НЕ установлен")

    # TTS (XTTS)
    try:
        from TTS.api import TTS
        print("✅ TTS (Coqui XTTS) установлен")
    except ImportError:
        print("❌ TTS НЕ установлен")

    # Ollama
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"✅ Ollama доступен. Модели: {models}")
    except Exception as e:
        print(f"❌ Ollama недоступен: {e}")

    # sounddevice
    try:
        import sounddevice as sd
        print(f"✅ sounddevice. Микрофоны: {len(sd.query_devices())} устройств")
    except ImportError:
        print("❌ sounddevice НЕ установлен")

    # pyautogui
    try:
        import pyautogui
        print("✅ pyautogui установлен")
    except ImportError:
        print("❌ pyautogui НЕ установлен")

    # DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        print("✅ duckduckgo-search установлен")
    except ImportError:
        print("❌ duckduckgo-search НЕ установлен")

    # Kokoro файлы
    import os
    for fname in ["kokoro-v0_19.onnx", "voices.bin"]:
        status = "✅" if os.path.exists(fname) else "❌ ОТСУТСТВУЕТ"
        print(f"{status} {fname}")

    # Голосовой файл
    voice_path = "data/my_voice.wav"
    status = "✅" if os.path.exists(voice_path) else "⚠️  НЕ ЗАПИСАН"
    print(f"{status} {voice_path}")

    print("=" * 50)

if __name__ == "__main__":
    check()
