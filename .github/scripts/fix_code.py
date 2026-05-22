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
    Ты строгий AI-инженер. Твоя задача — проверить код на архитектурные баги, утечки памяти, конфликты портов и настройки CORS.
    ПРАВИЛО 1: Если код ИДЕАЛЕН, верни ровно одно слово: PERFECT
    ПРАВИЛО 2: Если есть ошибки, верни ТОЛЬКО исправленный рабочий код. НЕ используй разметку и не пиши комментариев.
    
    Исходный код:
    {content}
    """
    
    # Используем современную модель
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    result = response.text.strip()
    
    # Безопасная очистка (без использования трех кавычек в тексте)
    backticks = "" * 3
    if result.startswith(backticks):
        result = "\n".join(result.split("\n")[1:-1])
        
    if "PERFECT" in result:
        print(f"[{file_path}] Код идеален. Ошибок не найдено.\n")
        return
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(result)
        
    print(f"[{file_path}] Ошибки найдены и исправлены. Файл перезаписан.\n")

files_to_check = ['server/main.py', 'render.yaml']

for file in files_to_check:
    fix_file(file)
