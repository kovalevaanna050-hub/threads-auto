"""Публикует утренние или вечерние посты в Threads и шлёт ссылки в Telegram.

Запуск: python post.py morning|evening [--dry-run] [--no-wait]
Секреты (env): THREADS_TOKEN, TG_BOT_TOKEN, TG_CHAT_ID
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"
TZ = dt.timezone(dt.timedelta(hours=7))  # Asia/Saigon
START = {"morning": (8, 0), "evening": (19, 0)}
GAP_MIN = 5  # минут между постами

DRY = "--dry-run" in sys.argv
NO_WAIT = "--no-wait" in sys.argv


def call(method, path, **params):
    params["access_token"] = os.environ["THREADS_TOKEN"]
    data = urllib.parse.urlencode(params)
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data}")
    else:
        req = urllib.request.Request(url, data=data.encode(), method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code >= 500 and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"{e.code} {path}: {body}") from None


def wait_ready(cid):
    for _ in range(30):
        st = call("GET", cid, fields="status,error_message")
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"контейнер {cid}: {st}")
        time.sleep(5)
    raise RuntimeError(f"контейнер {cid} не готов за 150 с")


def publish(cid):
    wait_ready(cid)
    return call("POST", "me/threads_publish", creation_id=cid)["id"]


def post_one(post, photo_url, reply_text):
    urls = [photo_url(k) for k in post["photos"]]
    if DRY:
        print(f"[dry] #{post['n']}: {post['text'][:40]!r} + {urls}")
        return f"https://www.threads.net/(dry-run)/{post['n']}"
    if len(urls) == 1:
        cid = call("POST", "me/threads", media_type="IMAGE", image_url=urls[0], text=post["text"])["id"]
    else:
        kids = [call("POST", "me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"] for u in urls]
        for k in kids:
            wait_ready(k)
        cid = call("POST", "me/threads", media_type="CAROUSEL", children=",".join(kids), text=post["text"])["id"]
    media_id = publish(cid)
    rid = call("POST", "me/threads", media_type="TEXT", text=reply_text, reply_to_id=media_id)["id"]
    publish(rid)
    return call("GET", media_id, fields="permalink").get("permalink", media_id)


def telegram(text):
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not tok or not chat:
        print("Telegram не настроен:\n" + text)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=30)
    except Exception as e:  # отчёт не должен ронять публикацию
        print("Telegram error:", e)


def main():
    slot = sys.argv[1]
    cfg = json.load(open("posts.json", encoding="utf-8"))
    repo = os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    photo_url = lambda k: f"https://raw.githubusercontent.com/{repo}/{branch}/{cfg['photos'][str(k)]}"
    posts = [p for p in cfg["posts"] if p["slot"] == slot]

    today = dt.datetime.now(TZ).date()
    h, m = START[slot]
    base = dt.datetime(today.year, today.month, today.day, h, m, tzinfo=TZ)
    base = max(base, dt.datetime.now(TZ))  # если GitHub запустил с опозданием — сдвигаем всё расписание

    links, errors = [], []
    for i, post in enumerate(posts):
        target = base + dt.timedelta(minutes=GAP_MIN * i)
        delay = (target - dt.datetime.now(TZ)).total_seconds()
        if delay > 0 and not NO_WAIT and not DRY:
            time.sleep(delay)
        try:
            links.append(post_one(post, photo_url, cfg["reply"]))
            print(f"ok #{post['n']}: {links[-1]}")
        except Exception as e:
            errors.append(f"#{post['n']}: {e}")
            print("ERROR", errors[-1])

    title = "Утро" if slot == "morning" else "Вечер"
    msg = f"✅ {title} {today:%d.%m}: опубликовано {len(links)}/{len(posts)}\n\n" + "\n".join(links)
    if errors:
        msg += "\n\n⚠️ Ошибки:\n" + "\n".join(e[:300] for e in errors)
    telegram(msg)

    if not DRY:
        os.makedirs("logs", exist_ok=True)
        with open(f"logs/{today:%Y-%m}.md", "a", encoding="utf-8") as f:
            f.write(f"\n## {today} {title}\n" + "\n".join(f"- {l}" for l in links)
                    + "".join(f"\n- ⚠️ {e[:300]}" for e in errors) + "\n")
    if errors and not links:
        sys.exit(1)


if __name__ == "__main__":
    main()
