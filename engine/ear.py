
import logging
import queue
import re
import threading
import time

import numpy as np
import sounddevice as sd
import torch

from faster_whisper import WhisperModel
from config.settings import (
    VAD_THRESHOLD, VAD_SAMPLE_RATE, VAD_CHUNK_SIZE,
    SILENCE_DURATION_SEC, MAX_RECORD_SEC,
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    WHISPER_LANGUAGE, WHISPER_BEAM_SIZE,
    WHISPER_CONDITION_ON_PREV, WHISPER_VAD_FILTER,
    AUDIO_DEVICE_INDEX, WAKE_WORD,
)

logger = logging.getLogger(__name__)


class Ear:
    """
    Модуль слуха LOQ Agent.

    Поток EarCapture: sounddevice → _audio_queue (float32 chunks).
    Вызывающая сторона: VAD фильтрует → Whisper транскрибирует.
    """

    def __init__(self, mouth_ref=None):
        """
        mouth_ref — ссылка на Mouth для реализации interrupt logic.
        Передаётся из main.py после инициализации обоих модулей.
        """
        self._mouth = mouth_ref
        self._audio_queue: queue.Queue = queue.Queue(maxsize=200)
        self._is_listening = False
        self._stream_thread: threading.Thread | None = None
        self._overflow_count = 0   # счётчик overflow для диагностики

        # ── Silero VAD ────────────────────────────────────────────────────────
        logger.info("Загрузка Silero VAD...")
        self._vad_model, self._vad_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
        (_, _, _, self._VADIterator, _) = self._vad_utils
        self._vad_model.eval()

        # ── Faster-Whisper ────────────────────────────────────────────────────
        logger.info(
            f"Загрузка Faster-Whisper [{WHISPER_MODEL_SIZE}] "
            f"на {WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE}..."
        )
        self._whisper = WhisperModel(
            model_size_or_path=WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        logger.info("Ear инициализирован.")

    # ──────────────────────────────────────────────────────────────────────────
    # Управление
    # ──────────────────────────────────────────────────────────────────────────

    def set_mouth(self, mouth):
        """Установить ссылку на Mouth после инициализации."""
        self._mouth = mouth

    def start(self):
        self._is_listening = True
        self._stream_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="EarCapture"
        )
        self._stream_thread.start()
        logger.info("Ear: прослушка запущена.")

    def stop(self):
        self._is_listening = False

    # ──────────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────────

    def listen_for_wake_word(self) -> str | None:
        """
        Блокирует до обнаружения WAKE_WORD.
        Возвращает:
          str  — текст попутной команды (если была после wake-word)
          ""   — wake-word найден, команды нет
        """
        logger.debug("Ожидание wake-word...")
        self._clear_queue()

        while True:
            text = self._listen_once(timeout=None)
            if not text:
                continue
            if WAKE_WORD.lower() not in text.lower():
                continue

            logger.info(f"Wake-word '{WAKE_WORD}' обнаружен!")

            # Извлекаем попутную команду — всё после wake-word
            parts = re.split(WAKE_WORD, text, flags=re.IGNORECASE, maxsplit=1)
            command = parts[1].strip().strip(",.?! ") if len(parts) > 1 else ""

            if len(command) > 2:
                logger.info(f"Попутная команда: '{command}'")
                return command
            return ""   # wake-word без команды

    def listen_command(self, timeout: float = 12.0) -> str | None:
        """Слушать одну команду. Возвращает текст или None."""
        self._clear_queue()
        return self._listen_once(timeout=timeout)

    # ──────────────────────────────────────────────────────────────────────────
    # Внутренняя логика
    # ──────────────────────────────────────────────────────────────────────────

    def _capture_loop(self):
        """Фоновый поток: sounddevice → очередь."""

        def _cb(indata, frames, time_info, status):
            if status:
                if "input overflow" in str(status).lower():
                    self._overflow_count += 1
                    self._clear_queue()
                    return

            # float32 форматына көшіру
            chunk = indata[:, 0].astype(np.float32).copy()

            # --- INTERRUPT LOGIC ---
            if self._mouth and self._mouth.is_speaking:
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms > 0.05:  # Сезімталдықты аздап төмендеттік (фондық шуға реакция бермеу үшін)
                    self._mouth.interrupt()

            # --- CHUNK SPLITTING (FIX) ---
            # Егер блок үлкен болса (мыс: 1024), оны 512-ден бөліп кезекке саламыз
            # Бұл Silero VAD-тың ValueError қатесін толық жояды
            step = VAD_CHUNK_SIZE # 512
            for i in range(0, len(chunk), step):
                sub_chunk = chunk[i : i + step]
                if len(sub_chunk) == step:
                    try:
                        self._audio_queue.put_nowait(sub_chunk)
                    except queue.Full:
                        pass

        # Блок өлшемін 1024 немесе 2048 қоямыз (CPU-ны жеңілдету үшін)
        # Бірақ VAD-қа жоғарыдағы split арқылы 512-ден барады
        with sd.InputStream(
            samplerate=VAD_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=1024,  # Микрофоннан 1024-пен оқимыз
            device=AUDIO_DEVICE_INDEX,
            callback=_cb,
        ):
            while self._is_listening:
                time.sleep(0.1)
                

    def _listen_once(self, timeout: float | None) -> str | None:
        """
        Накапливает речевые чанки через Silero VADIterator.
        После паузы SILENCE_DURATION_SEC → транскрибирует Whisper.
        """
        vad_iter = self._VADIterator(
            model=self._vad_model,
            threshold=VAD_THRESHOLD,
            sampling_rate=VAD_SAMPLE_RATE,
            min_silence_duration_ms=int(SILENCE_DURATION_SEC * 1000),
            speech_pad_ms=150,
        )

        speech_buf = []
        speaking = False
        silence_ts: float | None = None
        start_ts = time.time()

        while True:
            if timeout and (time.time() - start_ts) > timeout:
                return None

            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            ev = vad_iter(chunk, return_seconds=False)

            if ev:
                if "start" in ev:
                    speaking = True
                    silence_ts = None
                if "end" in ev:
                    silence_ts = time.time()

            if speaking:
                speech_buf.append(chunk)

                if silence_ts and (time.time() - silence_ts) >= SILENCE_DURATION_SEC:
                    break
                if (time.time() - start_ts) > MAX_RECORD_SEC:
                    logger.warning("Ear: достигнут MAX_RECORD_SEC.")
                    break

        if not speech_buf:
            return None

        return self._transcribe(np.concatenate(speech_buf))


    def _transcribe(self, audio: np.ndarray) -> str | None:
        try:
            # 1. Аудионың бар екенін тексеру (empty sequence қатесінен қорғаныс)
            if audio is None or len(audio) == 0:
                return None
            # 2. Транскрипция процесі
            segments, info = self._whisper.transcribe(
                audio,
                language=WHISPER_LANGUAGE,
                beam_size=WHISPER_BEAM_SIZE,
                vad_filter=WHISPER_VAD_FILTER,
                condition_on_previous_text=WHISPER_CONDITION_ON_PREV,
                initial_prompt="Сәлем, ассистент. Открой блокнот. Қалайсың?", # Контекст беру
                no_speech_threshold=0.5,
             )
            # 3. Сегменттерді тізімге жинау (генераторды босату)
            text_parts = []
            for s in segments:
                text_parts.append(s.text.strip())
            text = " ".join(text_parts).strip()
            # 4. Қысқа немесе мағынасыз дыбыстарды өткізбеу
            if len(text) < 2:
                return None
            # 5. Бөтен тілдерден қорғаныс (Испан, португал тілдерін блоктайды)
            allowed_langs = ['ru', 'kk', 'en']
            if info.language not in allowed_langs and info.language_probability < 0.5:
                logger.warning(f"Игнорируем подозрительный язык: {info.language} (p={info.language_probability:.2f})")
                return None
            logger.info(f"[Whisper/{info.language} p={info.language_probability:.2f}] {text}")
            return text
        except Exception as e:
            logger.error(f"Whisper ошибка: {e}")
            return None
    
    def _clear_queue(self):
        """Очистить накопившиеся старые аудио-чанки."""
        cleared = 0
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
                cleared += 1
            except queue.Empty:
                break
        if cleared > 5:
            logger.debug(f"Очередь очищена: {cleared} чанков.")
