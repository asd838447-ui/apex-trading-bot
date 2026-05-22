import os
import time
import requests
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
APP_URL = os.environ.get("RENDER_APP_URL", "https://ТВОЙ-САЙТ.onrender.com") # ВАЖНО: Замени на свой URL!
ENDPOINT_TO_CHECK = f"{APP_URL}/" # Замени на нужный эндпоинт, если бот отдает данные по другому пути, например /api/data
FILE_TO_FIX = "server/main.py"

def check_live_bot():
    print("Даем Render 2 минуты форы на установку библиотек...")
    time.sleep(120)
    
    max_retries = 25
    delay = 20 # 25 * 20 сек = еще ~8 минут ожидания
    
    for i in range(max_retries):
        print(f"Попытка {i+1}/{max_retries}: Пингуем {ENDPOINT_TO_CHECK}...")
        try:
            response = requests.get(ENDPOINT_TO_CHECK, timeout=10)
            
            if response.status_code == 200:
                data = response.text
                # ЩЕПЕТИЛЬНАЯ ПРОВЕРКА: здесь мы проверяем, не отдал ли бот мусор
                if "error" in data.lower() or data.strip() == "":
                    return False, f"Сервер ответил 200, но данные некорректны: {data[:200]}"
                
                print("Деплой успешен! Данные валидны.")
                return True, ""
                
            elif response.status_code >= 500:
                print(f"Сервер упал с ошибкой {response.status_code}!")
                return False, f"Критическая ошибка {response.status_code}: {response.text[:200]}"
                
        except requests.exceptions.RequestException:
            print("Сервер еще не поднялся (идет деплой)...")
            
        time.sleep(delay)
        
    return False, "Таймаут (10 минут). Деплой на Render либо завис, либо сервер не отвечает."

def ask_ai_to_fix(error_msg):
    print("Данные не совпали! Отправляем ошибку в ИИ...")
    with open(FILE_TO_FIX, "r", encoding="utf-8") as f:
        content = f.read()
        
    prompt = f"""
    Ты QA-инженер и архитектор торгового бота. Мы задеплоили код, но на боевом сервере произошел сбой.
    
    РЕАЛЬНАЯ ОШИБКА С СЕРВЕРА (или неверные данные):
    {error_msg}
    
    ТЕКУЩИЙ КОД:
    {content}
    
    ЗАДАЧА:
    1. Найди причину, почему данные не отдаются корректно или почему сервер падает.
    2. Верни ПОЛНОСТЬЮ ИСПРАВЛЕННЫЙ рабочий код от первой до последней строчки. Не обрезай конец файла!
    3. Без разметки, без тегов и без комментариев от себя.
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
    print("Код переписан нейросетью. Подготавливаем коммит.")

success, error_reason = check_live_bot()

if not success:
    print(f"ОБНАРУЖЕНА ПРОБЛЕМА: {error_reason}")
    ask_ai_to_fix(error_reason)
