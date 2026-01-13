# Локальный бот документов

## Запуск
1) Создайте `.env` рядом с `README.md` и добавьте:
   `BOT_TOKEN=...`
2) Установите зависимости:
   `pip install -r requirements.txt`
3) Запустите бота:
   `python -m src.main`

## Документы и шаблоны
- Шаблоны находятся в `src/documents/templates/`.
- Для PDF на Windows требуется установленный Microsoft Word (используется `docx2pdf`).
- При ошибке конвертации бот уведомит и отправит DOCX как fallback.
