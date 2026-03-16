import logging
import os
import subprocess
import time
import pyautogui
import pyperclip
import pygetwindow as gw
logger = logging.getLogger(__name__)

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True

class PCControl:
    def __init__(self):
        self._DISPATCH = {
            "open_app":   self.open_app,
            "close_app":  self.close_app,
            "type_text":  self.type_text,
            "press_key":  self.press_key,
            "move_mouse": self.move_mouse,
            "click":      self.click,
            "screenshot": self.take_screenshot,
            "hotkey":     self.hotkey,
            "run_cmd":    self.run_cmd,
        }
        logger.info("PCControl инициализирован.")

    def execute(self, action: dict) -> str:
        cmd  = action.get("cmd", "").lower()
        args = action.get("args", "")
        text_to_type = action.get("text", "") 

        handler = self._DISPATCH.get(cmd)
        if not handler:
            return f"Неизвестная команда: {cmd}"

        try:
            if cmd == "type_text":
                # Егер 'text' кілті болса соны, болмаса 'args'-ты қолданамыз
                result = self.type_text(text_to_type if text_to_type else args)
            else:
                result = handler(args)
            return result or f"Команда '{cmd}' выполнена."
        except Exception as e:
            return f"Ошибка: {e}"

    def type_text(self, text: str) -> str:
        """Кириллицаны (қаз/орыс) қолдау үшін Clipboard арқылы жазу."""
        logger.info(f"Ввод текста через буфер: {text[:30]}...")
        try:
            pyperclip.copy(text)
            time.sleep(0.3) # Блокнотқа үлгеру үшін сәл күтеміз
            pyautogui.hotkey('ctrl', 'v')
            return f"Текст введён успешно."
        except Exception as e:
            pyautogui.write(text) # Егер қате болса, ескі әдіс
            return f"Текст введён (через pyautogui): {e}"

    def open_app(self, app_name: str) -> str:
        try:
            os.startfile(app_name)
        except OSError:
            subprocess.Popen(app_name, shell=True)
        return f"Открываю {app_name}."

    def close_app(self, app_name: str) -> str:
        subprocess.run(["taskkill", "/F", "/IM", f"{app_name}.exe"], shell=True)
        return f"Процесс {app_name} завершён."

    def press_key(self, key: str) -> str:
        pyautogui.press(key)
        return f"Клавиша {key} нажата."

    def hotkey(self, keys_str: str) -> str:
        keys = [k.strip() for k in keys_str.split("+")]
        pyautogui.hotkey(*keys)
        return f"Комбинация {keys_str} выполнена."

    def move_mouse(self, coords: str) -> str:
        parts = [p.strip() for p in coords.split(",")]
        x, y = int(parts[0]), int(parts[1])
        pyautogui.moveTo(x, y, duration=0.3)
        return f"Мышь в ({x}, {y})."

    def click(self, coords: str) -> str:
        parts = [p.strip() for p in coords.split(",")]
        x, y = int(parts[0]), int(parts[1])
        pyautogui.click(x, y)
        return f"Клик по ({x}, {y})."

    def take_screenshot(self, _args: str = "") -> str:
        from config.settings import SCREENSHOT_PATH
        pyautogui.screenshot().save(SCREENSHOT_PATH)
        return f"Скриншот сохранён."

    def run_cmd(self, command: str) -> str:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding="utf-8")
        return (result.stdout + result.stderr)[:500]
    def type_text(self, text: str) -> str:
        """Терезені тауып алып, соған жазу (Clipboard арқылы)."""
        logger.info(f"Ввод текста через буфер: {text[:30]}...")
        try:
            # 1. Блокнот терезесін іздеу
            windows = gw.getWindowsWithTitle('Блокнот') or gw.getWindowsWithTitle('Notepad')
            
            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate() # Терезені алға шығару (ФОКУС)
                time.sleep(0.5) # Терезе ашылғанша азғантай күту
            else:
                # Егер блокнот табылмаса, жаңасын ашу
                self.open_app("notepad")
                time.sleep(1.0)

            # 2. Мәтінді жазу
            pyperclip.copy(text)
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'v')
            
            return f"Текст успешно введён в Блокнот."
        except Exception as e:
            logger.error(f"Ошибка в type_text: {e}")
            # Егер терезені таба алмаса, тұрған жерге жаза салу (failsafe)
            pyautogui.write(text)
            return f"Текст введён (стандартный метод): {e}"
