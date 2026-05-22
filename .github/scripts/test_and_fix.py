import os
import time
import requests
import subprocess
from google import genai
client = None
def get_ai_client():
    global client
    if client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        client = genai.Client(api_key=api_key)
    return client

FILE_TO_FIX = "server/main.py"

def run_local_test():
    print("Запускаем локальный краш-тест бота...")
    
    # 1. Запускаем сервер локально, перенаправляя вывод в файл, чтобы избежать deadlock
    log_file = open("server_test.log", "w", encoding="utf-8")
    process = subprocess.Popen(
        ["uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=log_file,
        stderr=log_file,
        text=True
    )
    
    # Даем серверу 3 секунды на то, чтобы загрузиться
    time.sleep(3)
    
    # 2. ПРОВЕРКА НА КРАШ: Не упал ли сервер сразу?
    if process.poll() is not None:
        log_file.close()
        with open("server_test.log", "r", encoding="utf-8") as f:
            logs = f.read()
        return False, f"КРИТИЧЕСКАЯ ОШИБКА (Crash). Сервер не запустился:\n{logs}"

    # 3. ПРОВЕРКА ДАННЫХ: Делаем запрос к нашему запущенному боту
    try:
        print("Сервер работает. Проверяем выдачу реальных данных...")
        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        
        if response.status_code == 200:
            data = response.text
            
            # ЩЕПЕТИЛЬНАЯ ПРОВЕРКА: Ищем признаки кривых данных
            if "error" in data.lower() or "traceback" in data.lower() or data.strip() == "":
                process.kill()
                log_file.close()
                with open("server_test.log", "r", encoding="utf-8") as f:
                    logs = f.read()
                return False, f"ЛОГИЧЕСКАЯ ОШИБКА. Сервер отдал 200 OK, но данные кривые:\n{data[:500]}\n\nLogs:\n{logs}"
            
            print("✅ Данные валидны! Деплой разрешен.")
            process.kill()
            log_file.close()
            return True, ""
            
        else:
            process.kill()
            log_file.close()
            with open("server_test.log", "r", encoding="utf-8") as f:
                logs = f.read()
            return False, f"ОШИБКА API (Код {response.status_code}). Ответ сервера:\n{response.text[:500]}\n\nLogs:\n{logs}"
            
    except requests.exceptions.RequestException as e:
        process.kill()
        log_file.close()
        with open("server_test.log", "r", encoding="utf-8") as f:
            logs = f.read()
        return False, f"СЕТЕВАЯ ОШИБКА. Сервер висит, но не отвечает на запросы:\n{str(e)}\n\nLogs:\n{logs}"

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
    
    client = get_ai_client()
    res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    new_code = res.text.strip()
    
    backticks = "```"
    if new_code.startswith(backticks) or new_code.endswith(backticks):
         lines = new_code.split("\n")
         if lines and lines[0].startswith(backticks):
             lines = lines[1:]
         if lines and lines[-1].startswith(backticks):
             lines = lines[:-1]
         new_code = "\n".join(lines)
         
    with open(FILE_TO_FIX, "w", encoding="utf-8") as f:
        f.write(new_code)
    print("✅ Код переписан нейросетью. Подготавливаем коммит.")

success, error_reason = run_local_test()

if not success:
    ask_ai_to_fix(error_reason)
    exit(1)
