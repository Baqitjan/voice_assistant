
import time
import logging
import os
import re
import threading

import numpy as np
import sounddevice as sd
import torch

from config.settings import (
    SILERO_SAMPLE_RATE, SILERO_SPEAKER, SILERO_LANGUAGE, SILERO_MODEL_ID,
    XTTS_MODEL_NAME, XTTS_DEVICE, XTTS_LANGUAGE,
    MY_VOICE_WAV, CLONE_VOICE_TRIGGER, STD_VOICE_TRIGGER,
)

logger = logging.getLogger(__name__)


def _register_xtts_safe_globals():
    """
    PyTorch 2.6 fix: XTTS checkpoint содержит конфиги в pickle.
    Регистрируем классы как доверенные ДО загрузки модели.
    """
    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import XttsAudioConfig
        from TTS.config.shared_configs import BaseDatasetConfig
        torch.serialization.add_safe_globals([
            XttsConfig, XttsAudioConfig, BaseDatasetConfig,
        ])
        logger.info("XTTS safe globals зарегистрированы (PyTorch 2.6 fix).")
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать XTTS safe globals: {e}")


class Mouth:
    """
    Модуль речи LOQ Agent.

    Режимы:
      clone_mode=False  → Silero TTS (быстро, ~200ms, подтверждён в работе)
      clone_mode=True   → XTTS v2 (голос  из data/my_voice.wav)

    speak()       — неблокирующий (отдельный поток)
    speak_sync()  — блокирующий
    interrupt()   — прервать текущее воспроизведение (для interrupt logic)
    is_speaking   — флаг для Ear (interrupt detection)
    """

    def __init__(self):
        self._clone_mode = False
        self._speak_lock = threading.Lock()
        self.is_speaking = False        # флаг для interrupt logic в Ear
        self._interrupt_flag = False    # сигнал прерывания

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Silero TTS — основной движок
        self._silero_model = None
        self._load_silero()

        # XTTS v2 — ленивая загрузка
        self._xtts = None

        logger.info(f"Mouth инициализирован. Устройство: {self.device}. Режим: Silero.")

    # ──────────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────────

    def speak(self, text: str):
        """Неблокирующая озвучка в отдельном потоке."""
        clean = _strip_action(text)
        if not clean:
            return
        t = threading.Thread(
            target=self._speak_locked,
            args=(clean,),
            daemon=True,
            name="MouthSpeak",
        )
        t.start()

    def speak_sync(self, text: str):
        """Блокирующая озвучка (ждёт окончания)."""
        clean = _strip_action(text)
        if clean:
            self._speak_locked(clean)

    def interrupt(self):
        """
        Прервать текущее воспроизведение.
        Вызывается из Ear._capture_loop при обнаружении речи пользователя.
        """
        if self.is_speaking:
            self._interrupt_flag = True
            try:
                sd.stop()
            except Exception:
                pass
            logger.info("Mouth: воспроизведение прервано пользователем.")

    def check_and_switch_mode(self, text: str) -> bool:
        """
        Проверяет текст на триггер смены голоса.
        Возвращает True если режим переключился (команда обработана).
        """
        tl = text.lower()
        if CLONE_VOICE_TRIGGER in tl:
            if not self._clone_mode:
                self._clone_mode = True
                self._load_xtts()
                self.speak_sync("Переключаюсь на ваш голос.")
                logger.info("Mouth → XTTS v2 (clone mode).")
            return True
        if STD_VOICE_TRIGGER in tl:
            if self._clone_mode:
                self._clone_mode = False
                self.speak_sync("Переключаюсь на стандартный голос.")
                logger.info("Mouth → Silero (standard mode).")
            return True
        return False

    @property
    def mode(self) -> str:
        return "XTTS-clone" if self._clone_mode else "Silero"

    # ──────────────────────────────────────────────────────────────────────────
    # Загрузка движков
    # ──────────────────────────────────────────────────────────────────────────

    def _load_silero(self):
        try:
            self._silero_model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language=SILERO_LANGUAGE,
                speaker=SILERO_MODEL_ID,
            )
            self._silero_model.to(self.device)
            logger.info("Silero TTS загружен.")
        except Exception as e:
            logger.error(f"Ошибка загрузки Silero TTS: {e}")

    def _load_xtts(self):
        if self._xtts is not None:
            return
        try:
            _register_xtts_safe_globals()
            from TTS.api import TTS
            logger.info("Загрузка XTTS v2 (~30–60 сек первый раз)...")
            self._xtts = TTS(model_name=XTTS_MODEL_NAME, progress_bar=True).to(XTTS_DEVICE)
            logger.info("XTTS v2 загружен.")
        except ImportError:
            logger.error("TTS не установлен. pip install TTS==0.22.0")
        except Exception as e:
            logger.error(f"Ошибка загрузки XTTS v2: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Синтез
    # ──────────────────────────────────────────────────────────────────────────

    def _speak_locked(self, text: str):
        with self._speak_lock:
            self.is_speaking = True
            self._interrupt_flag = False
            try:
                if self._clone_mode and self._xtts:
                    self._synth_xtts(text)
                else:
                    self._synth_silero(text)
            except Exception as e:
                logger.error(f"Ошибка синтеза речи: {e}")
            finally:
                self.is_speaking = False
                self._interrupt_flag = False

    def _synth_silero(self, text: str):
        if not self._silero_model:
            logger.warning("Silero не загружен — пропуск озвучки.")
            return
        try:
            audio = self._silero_model.apply_tts(
                text=text,
                speaker=SILERO_SPEAKER,
                sample_rate=SILERO_SAMPLE_RATE,
            )
            _play(audio.cpu().numpy(), SILERO_SAMPLE_RATE, self)
        except Exception as e:
            logger.error(f"Silero синтез ошибка: {e}")

    def _synth_xtts(self, text: str):
        if not os.path.exists(MY_VOICE_WAV):
            logger.error(
                f"Референс голоса не найден: {MY_VOICE_WAV}\n"
                "Запустите record_voice.py для записи."
            )
            self._synth_silero(text)
            return
        try:
            wav = self._xtts.tts(
                text=text,
                speaker_wav=MY_VOICE_WAV,
                language=XTTS_LANGUAGE,
            )
            _play(np.array(wav, dtype=np.float32), 24000, self)
        except Exception as e:
            logger.error(f"XTTS синтез ошибка: {e}")
            self._synth_silero(text)


# ──────────────────────────────────────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────────────────────────────────────

def _play(audio: np.ndarray, sr: int, mouth_ref: "Mouth"):
    """Воспроизводит float32 audio. Проверяет interrupt_flag."""
    try:
        if audio.ndim > 1:
            audio = audio.flatten()
        
        # Нормализация
        peak = np.max(np.abs(audio))
        if peak > 1.0:
            audio = audio / peak

        sd.stop() # Алдыңғы дыбысты тоқтату
        sd.play(audio, samplerate=sr)
        
        while sd.get_stream().active:
            if mouth_ref._interrupt_flag:
                sd.stop()
                break
            time.sleep(0.1)
    except Exception as e:
        logger.error(f"Ошибка воспроизведения: {e}")


def _strip_action(text: str) -> str:
    """Убирает [ACTION: {...}] из текста перед озвучкой."""
    return re.sub(r"\[ACTION:\s*\{.*?\}\]", "", text, flags=re.DOTALL).strip()
