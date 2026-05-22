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
    print("[INFO] Запускаем локальный краш-тест бота с глубокой сверкой цен...")
    
    # 1. Запускаем сервер локально, перенаправляя вывод в файл, чтобы избежать deadlock
    log_file = open("server_test.log", "w", encoding="utf-8")
    process = subprocess.Popen(
        ["uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=log_file,
        stderr=log_file,
        text=True
    )
    
    # Запрашиваем эталонную цену BTC/USDT напрямую с Binance FUTURES REST API,
    # так как бот работает на фьючерсном рынке. Это гарантирует отсутствие расхождения спот-фьючерс.
    public_price = None
    try:
        print("[INFO] Запрашиваем эталонную биржевую цену BTCUSDT с Binance Futures REST API...")
        public_res = requests.get("https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT", timeout=5)
        if public_res.status_code == 200:
            public_price = float(public_res.json()["price"])
            print(f"[INFO] Эталонная цена фьючерса Binance: ${public_price:.2f}")
        else:
            print(f"[WARNING] Binance Futures REST API ответил с кодом {public_res.status_code}")
    except Exception as pe:
        print(f"[WARNING] Не удалось получить эталонную цену с Binance Futures REST API: {pe}")

    # Резолвим проблему с таймаутом старта: опрашиваем сервер в течение 15 секунд,
    # давая HMM классификатору обучиться, а WebSocket - подключиться и обновить цену.
    server_ready = False
    bot_price = 93250.0
    for attempt in range(1, 16):
        if process.poll() is not None:
            log_file.close()
            with open("server_test.log", "r", encoding="utf-8") as f:
                logs = f.read()
            return False, f"КРИТИЧЕСКАЯ ОШИБКА (Crash). Сервер не запустился:\n{logs}"
            
        print(f"[INFO] Попытка подключения к серверу и проверки котировок {attempt}/15...")
        try:
            # Делаем GET-запрос к эндпоинту статуса бота
            response = requests.get("http://127.0.0.1:8000/api/status", timeout=2)
            if response.status_code == 200:
                data_json = response.json()
                bot_price = float(data_json.get("btc_price", 0))
                # Если цена изменилась с дефолтных 93250.00, значит WebSocket успешно поставляет реальные тики
                if bot_price != 93250.0:
                    server_ready = True
                    break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
        
    if not server_ready:
        process.kill()
        log_file.close()
        with open("server_test.log", "r", encoding="utf-8") as f:
            logs = f.read()
        
        # Если сервер ответил, но цена осталась статичной/дефолтной
        if bot_price == 93250.0:
            return False, f"ЛОГИЧЕСКАЯ ОШИБКА. Сервер успешно запущен, но WebSocket-коллектор не обновил цену! Цена осталась дефолтной: ${bot_price:.2f}. Logs:\n{logs}"
        return False, f"СЕТЕВАЯ ОШИБКА. Сервер не ответил или WebSocket не заработал за 15 секунд.\n\nLogs:\n{logs}"

    # 3. СВЕРКА ДАННЫХ: Сопоставляем цену в боте с реальной биржевой
    try:
        print("[INFO] Сервер успешно поставляет котировки. Производим детальную сверку...")
        response = requests.get("http://127.0.0.1:8000/api/status", timeout=5)
        
        if response.status_code == 200:
            data_json = response.json()
            bot_price = float(data_json.get("btc_price", 0))
            
            # Сопоставляем с реальной биржевой ценой с максимально строгим допуском (0.1%),
            # так как оба источника берут данные с одного и того же рынка (Binance Futures).
            # Небольшое отклонение до 0.1% возможно исключительно из-за миллисекундной разницы во времени запросов в постоянно движущемся стакане.
            if public_price:
                diff_pct = (abs(bot_price - public_price) / public_price) * 100
                print(f"[INFO] Сверка: Цена бота = ${bot_price:.2f}, Биржевая цена = ${public_price:.2f}, Отклонение = {diff_pct:.4f}%")
                
                if diff_pct > 0.1:
                    process.kill()
                    log_file.close()
                    return False, f"ЛОГИЧЕСКАЯ ОШИБКА. Обнаружено расхождение цен! Цена в боте (${bot_price:.2f}) отличается от реальной цены Binance Futures (${public_price:.2f}) более чем на 0.1% (отклонение: {diff_pct:.2f}%). Проверьте стабильность соединения."
            
            print("[SUCCESS] Все проверки пройдены! Котировки бота идеально соответствуют реальному фьючерсному рынку. Деплой разрешен.")
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
    print("[FAIL] Найдена проблема! Отправляем лог ошибки в ИИ...")
    with open(FILE_TO_FIX, "r", encoding="utf-8") as f:
        content = f.read()
        
    prompt = f"""
    Ты QA-инженер и архитектор торгового бота. Во время локального тестирования перед деплоем найдена проблема.
    
    ЛОГ ОШИБКИ ИЛИ КРИВЫХ ДАННЫХ:
    {error_log}
    
    ТЕКУЩИЙ КОД БОТА:
    {content}
    
    ЗАДАЧА:
    1. Изучи ошибку. Если это краш — исправь синтаксис/импорты. Если это логическая ошибка или расхождение с биржей — исправь алгоритм расчета, WebSocket-коннекторы или формирование ответа.
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
    print("[SUCCESS] Код переписан нейросетью. Подготавливаем коммит.")

success, error_reason = run_local_test()

if not success:
    ask_ai_to_fix(error_reason)
    exit(1)
