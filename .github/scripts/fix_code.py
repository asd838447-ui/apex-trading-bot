import os
from google import genai

# Подключаем новый актуальный клиент
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def fix_file(file_path):
    print(f"Анализирую файл: {file_path}...")
    
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    prompt = f"""
        Ты — Senior AI-инженер и строгий QA-тестировщик. Твоя задача — проверить код торгового бота перед деплоем на Render. а также при обнаружении ошибок какихто недоработак или чегото подобного все исправить и снова проверить как сказана в промте.
    
        КРИТЕРИИ ПРОВЕРКИ (Щепетильно и дотошно):
        1. Синтаксис: Никаких незакрытых скобок (SyntaxError). Весь код должен быть валидным.
        2. Порты и CORS: Приложение должно запускаться на порту из переменной окружения $PORT (0.0.0.0).
        3. Точность данных: Убедись, что логика парсинга, расчетов и выдачи данных работает идеально и соответствует реальным рыночным алгоритмам. API должно отдавать корректные JSON-структуры.
    
        ПРАВИЛО 1: Если код ИДЕАЛЕН по всем пунктам, верни ровно одно слово: PERFECT
        ПРАВИЛО 2: Если есть малейшая ошибка, верни ПОЛНОСТЬЮ ИСПРАВЛЕННЫЙ РАБОЧИЙ КОД от первой до последней строчки. Не обрезай конец файла!
        НЕ используй разметку (```python) и не пиши комментариев от себя.
    
     Исходный код:
    {content}
    """
    
    # Используем современную модель
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    result = response.text.strip()
    
    # Безопасная очистка от markdown-разметки (```python или ```yaml и закрывающие ```)
    backticks = "```"
    if result.startswith(backticks) or result.endswith(backticks):
        lines = result.split("\n")
        if lines and lines[0].startswith(backticks):
            lines = lines[1:]
        if lines and lines[-1].startswith(backticks):
            lines = lines[:-1]
        result = "\n".join(lines)

    if "PERFECT" in result:
        print(f"[{file_path}] Код идеален. Ошибок не найдено.\n")
        return
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(result)
        
    print(f"[{file_path}] Ошибки найдены и исправлены. Файл перезаписан.\n")

files_to_check = ['server/main.py', 'render.yaml']

for file in files_to_check:
    fix_file(file)
