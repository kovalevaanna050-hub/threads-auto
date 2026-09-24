# threads-auto

Автовыкладка в Threads через GitHub Actions: 10 постов в 08:00–08:45 и 10 в 19:00–19:45 (Asia/Saigon), каждый с ответом-инструкцией в ветке. Ссылки приходят в Telegram.

- `posts.json` — тексты, фото и ответ в ветке (править здесь)
- `photos/` — фото (репозиторий публичный: Threads берёт картинки по ссылке)
- `post.py` — публикация
- `.github/workflows/post.yml` — расписание; вручную можно запустить с `dry_run`
- `.github/workflows/setup.yml` — один раз: Telegram chat id + проверка токена
- `.github/workflows/refresh-token.yml` — еженедельное продление токена Threads

Секреты: `THREADS_TOKEN`, `THREADS_APP_SECRET` (необяз.), `TG_BOT_TOKEN`, `TG_CHAT_ID` (ставит setup), `GH_PAT`.
Переменная: `TG_USERNAME`.
