import google.generativeai as genai
import os

# Подключаем ключ
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Используем flash (быструю и бесплатную версию)
model = genai.GenerativeModel('gemini-1.5-flash')

def fix_file(file_path):
    print(f"Анализирую файл: {file_path}...")
    
    # Проверяем, существует ли файл
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден, пропускаю.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Промпт (инструкция) для AI. Здесь мы жестко запрещаем писать лишнее.
    prompt = f"""
    Ты строгий AI-инженер. Твоя задача — проверить код на архитектурные баги, утечки памяти, конфликты портов и синтаксические ошибки.

    ПРАВИЛО 1: Если код ИДЕАЛЕН, в нем нет багов и он готов к деплою на Render, верни ровно одно слово: PERFECT. Больше ни одного символа.
    ПРАВИЛО 2: Если есть ошибки, верни ТОЛЬКО исправленный рабочий код. НЕ пиши "Вот исправленный код", НЕ используй разметку (```python ... 
```), не пиши никаких комментариев от себя внизу или вверху. Только голый код, который можно сразу сохранить в файл.

    Исходный код для анализа:
    {content}
    """
    
    # Отправляем запрос
    response = model.generate_content(prompt)
    result = response.text.strip()
    
    # Очищаем от случайных маркдаун-блоков, если бот всё же их вставил
    if result.startswith("```"):
        result = "\n".join(result.split("\n")[1:-1])
        
    # Проверяем, нашел ли бот ошибки
    if "PERFECT" in result:
        print(f"[{file_path}] Код идеален. Ошибок не найдено. Файл не изменен.\n")
        return
    
    # Если бот прислал код, перезаписываем файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(result)
        
    print(f"[{file_path}] Ошибки найдены и исправлены. Файл перезаписан.\n")

# Список файлов, за которыми будет следить бот
files_to_check = [
    'server/main.py',
    'render.yaml'
]

# Запускаем проверку для каждого файла
for file in files_to_check:
    fix_file(file)
