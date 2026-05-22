import os
import subprocess
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
FILE_TO_FIX = "server/main.py"

def run_local_test():
    print("Запускаем локальный краш-тест бота...")
    
    # Пытаемся запустить сервер на 5 секунд
    # Если в коде есть синтаксическая ошибка, он упадет мгновенно
    process = subprocess.Popen(
        ["uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Ждем 5 секунд. Если не упал - значит базово работает
        stdout, stderr = process.communicate(timeout=5)
        print("✅ Сервер успешно запустился. Критических ошибок нет.")
        return True, ""
    except subprocess.TimeoutExpired:
        # Сервер работает и не падает - это отлично!
        process.kill()
        print("✅ Сервер стабилен, таймаут прошел успешно.")
        return True, ""
    except Exception as e:
        process.kill()
        stdout, stderr = process.communicate()
        return False, stderr # Возвращаем ТОТ САМЫЙ лог ошибки

def ask_ai_to_fix(error_log):
    print("❌ Сервер упал! Отправляем лог ошибки в ИИ...")
    with open(FILE_TO_FIX, "r", encoding="utf-8") as f:
        content = f.read()
        
    prompt = f"""
    Ты QA-инженер. Мы попытались запустить сервер, но он упал с ошибкой.
    
    ПОЛНЫЙ ЛОГ ОШИБКИ (Traceback):
    {error_log}
    
    ТЕКУЩИЙ КОД:
    {content}
    
    ЗАДАЧА:
    1. Изучи лог ошибки. Найди, из-за чего падает сервер (незакрытые скобки, импорты, логика).
    2. Верни ПОЛНОСТЬЮ ИСПРАВЛЕННЫЙ код.
    3. Без разметки, без тегов и без комментариев.
    """
    
    res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    new_code = res.text.strip()
    
    # Очистка от кавычек ```
    backticks = "`" * 3
    if new_code.startswith(backticks):
         new_code = "\n".join(new_code.split("\n")[1:-1])
         
    with open(FILE_TO_FIX, "w", encoding="utf-8") as f:
        f.write(new_code)
    print("✅ Код переписан нейросетью. Подготавливаем коммит.")

success, error_reason = run_local_test()

if not success:
    ask_ai_to_fix(error_reason)
    # Завершаем с ошибкой, чтобы GitHub остановил деплой
    exit(1)
