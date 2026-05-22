import os
import time
import requests
import subprocess
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
FILE_TO_FIX = "server/main.py"

def run_local_test():
    print("Запускаем локальный краш-тест бота...")
    
    # 1. Запускаем сервер локально
    process = subprocess.Popen(
        ["uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Даем серверу 3 секунды на то, чтобы загрузиться
    time.sleep(3)
    
    # 2. ПРОВЕРКА НА КРАШ: Не упал ли сервер сразу?
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        return False, f"КРИТИЧЕСКАЯ ОШИБКА (Crash). Сервер не запустился:\n{stderr}"

    # 3. ПРОВЕРКА ДАННЫХ: Делаем запрос к нашему запущенному боту
    try:
        print("Сервер работает. Проверяем выдачу реальных данных...")
        # Если твой бот отдает данные по другому адресу, поменяй "/" на "/api/data" и т.д.
        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        
        if response.status_code == 200:
            data = response.text
            
            # ЩЕПЕТИЛЬНАЯ ПРОВЕРКА: Ищем признаки кривых данных
            if "error" in data.lower() or "traceback" in data.lower() or data.strip() == "":
                process.kill()
                return False, f"ЛОГИЧЕСКАЯ ОШИБКА. Сервер отдал 200 OK, но данные кривые:\n{data[:500]}"
            
            print("✅ Данные валидны! Деплой разрешен.")
            process.kill()
            return True, ""
            
        else:
            process.kill()
            return False, f"ОШИБКА API (Код {response.status_code}). Ответ сервера:\n{response.text[:500]}"
            
    except requests.exceptions.RequestException as e:
        process.kill()
        return False, f"СЕТЕВАЯ ОШИБКА. Сервер висит, но не отвечает на запросы:\n{str(e)}"

def ask_ai_to_fix(error_log):
    print("❌ Найдена проблема! Отправляем лог ошибки в ИИ...")
    with open(FILE_TO_FIX, "r", encoding="utf-8") as f:
        content = f.read()
        
    prompt = f"""
    Ты QA-инженер и архитектор торгового бота. Во время локального тестирования перед деплоем найдена проблема.
    
    ЛОГ ОШИБКИ ИЛИ КРИВЫХ ДАННЫХ:
    {error_log}
    
    ТЕКУЩИЙ КОД БОТА:
    {content}
    
    ЗАДАЧА:
    1. Изучи ошибку. Если это краш — исправь синтаксис/импорты. Если это логическая ошибка — исправь алгоритм расчета или формирования JSON/ответа.
    2. Верни ПОЛНОСТЬЮ ИСПРАВЛЕННЫЙ код от первой до последней строчки.
    3. Без разметки, без тегов и без комментариев.
    """
    
    res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    new_code = res.text.strip()
    
    backticks = "`" * 3
    if new_code.startswith(backticks):
         new_code = "\n".join(new_code.split("\n")[1:-1])
         
    with open(FILE_TO_FIX, "w", encoding="utf-8") as f:
        f.write(new_code)
    print("✅ Код переписан нейросетью. Подготавливаем коммит.")

success, error_reason = run_local_test()

if not success:
    ask_ai_to_fix(error_reason)
    exit(1)
