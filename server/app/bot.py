from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.filters import ChatMemberUpdatedFilter, Command
from aiogram.filters.chat_member_updated import JOIN_TRANSITION
from aiogram.types import ChatMemberUpdated, ChatPermissions, Message

from app.models import NlpJob
from app.parse import (
    contains_forbidden,
    extract_term_query,
    glossary_lookup,
    parse_schedule,
)
from app.store import Store

router = Router()


def _mention(message: Message) -> str:
    user = message.from_user
    if not user:
        return "участник"
    name = escape(user.full_name)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def _uname(message: Message) -> str:
    user = message.from_user
    if not user:
        return "unknown"
    return user.username or str(user.id)


async def _kick_if_blacklisted(bot: Bot, store: Store, user_id: int, chat_id: int) -> bool:
    if user_id in store.config.blacklist:
        try:
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
        except Exception:
            pass
        await store.log_line(f"{time.time():.0f}\tkick_blacklist\t{user_id}")
        return True
    return False


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_join(event: ChatMemberUpdated, bot: Bot, store: Store) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return
    chat_id = event.chat.id
    if store.config.chat_id is None:
        store.config.chat_id = chat_id
        await store.persist()
    if await _kick_if_blacklisted(bot, store, user.id, chat_id):
        return
    sent = await bot.send_message(chat_id, store.config.welcome_text, reply_to_message_id=None)
    store.pending_questionnaires[str(user.id)] = {
        "user_id": user.id,
        "username": user.username or "",
        "full_name": user.full_name,
        "joined_at": time.time(),
        "welcome_message_id": sent.message_id,
        "fragments": [],
        "done": False,
    }
    store.activity.setdefault(
        str(user.id),
        {"count": 0, "last": time.time(), "name": user.full_name, "username": user.username},
    )
    await store.log_line(f"{time.time():.0f}\tjoin\t{user.id}\t{user.full_name}")
    await store.persist()


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot, store: Store) -> None:
    if message.chat.id not in store.config.channel_ids:
        return
    dest = store.config.chat_id
    if not dest:
        return
    try:
        await bot.copy_message(dest, message.chat.id, message.message_id)
        await store.log_line(f"{time.time():.0f}\trepost\t{message.chat.id}\t{message.message_id}")
    except Exception as exc:
        await store.log_line(f"{time.time():.0f}\trepost_fail\t{exc}")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Я админ закрытого чата. Настройки — в локальном GUI. "
        "В чате: анкеты, термины («что такое …»), «запланировать …», «сделаю …»."
    )


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(message: Message, bot: Bot, store: Store) -> None:
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id
    chat_id = message.chat.id
    if store.config.chat_id is None:
        store.config.chat_id = chat_id
        await store.persist()
    if await _kick_if_blacklisted(bot, store, uid, chat_id):
        return

    text = message.text or message.caption or ""
    name = message.from_user.full_name
    rec = store.activity.setdefault(
        str(uid),
        {"count": 0, "last": 0, "name": name, "username": message.from_user.username},
    )
    rec["count"] = int(rec.get("count", 0)) + 1
    rec["last"] = time.time()
    rec["name"] = name

    if store.config.logging_enabled:
        await store.log_line(
            f"{datetime.now(timezone.utc).isoformat()}\t{uid}\t{_uname(message)}\t{text[:2000]}"
        )

    if text and contains_forbidden(text, store.config.forbidden_words):
        try:
            await message.delete()
        except Exception:
            pass
        until = int(time.time()) + store.config.mute_seconds
        try:
            await bot.restrict_chat_member(
                chat_id,
                uid,
                ChatPermissions(can_send_messages=False),
                until_date=until,
            )
        except Exception:
            pass
        notice = store.config.mute_notice.format(minutes=store.config.mute_seconds // 60)
        await bot.send_message(chat_id, notice)
        await store.log_line(f"{time.time():.0f}\tmute\t{uid}")
        return

    if store.config.nlp_profanity and text and store.local_connected:
        await store.enqueue_nlp(
            NlpJob(
                id=str(uuid.uuid4()),
                kind="profanity",
                payload={"user_id": uid, "chat_id": chat_id, "message_id": message.message_id, "text": text},
                created_at=time.time(),
            )
        )

    await _handle_questionnaire(message, store, text)
    await _handle_long_post(message, store, text)
    await _handle_todo(message, store, text)
    await _handle_schedule(message, store, text)
    await _handle_terms(message, store, bot, text)


async def _handle_questionnaire(message: Message, store: Store, text: str) -> None:
    uid = str(message.from_user.id)
    pending = store.pending_questionnaires.get(uid)
    if not pending or pending.get("done") or not text:
        return
    reply_ok = bool(
        message.reply_to_message
        and message.reply_to_message.message_id == pending.get("welcome_message_id")
    )
    if reply_ok:
        pending["fragments"].append(text)
        pending["last_fragment"] = time.time()
        if len("\n".join(pending["fragments"])) >= 40 or len(pending["fragments"]) >= 2:
            await complete_questionnaire(store, uid)
        else:
            await store.persist()
        return
    if store.local_connected:
        await store.enqueue_nlp(
            NlpJob(
                id=str(uuid.uuid4()),
                kind="questionnaire",
                payload={"user_id": int(uid), "text": text, "username": pending.get("username")},
                created_at=time.time(),
            )
        )


async def complete_questionnaire(store: Store, uid: str) -> None:
    pending = store.pending_questionnaires.get(uid)
    if not pending:
        return
    pending["done"] = True
    body = "\n\n".join(pending.get("fragments") or [])
    uname = pending.get("username") or uid
    md = (
        f"# Анкета {pending.get('full_name')} (@{uname})\n\n"
        f"- user_id: {uid}\n"
        f"- joined: {datetime.fromtimestamp(pending['joined_at']).isoformat()}\n\n"
        f"{body}\n"
    )
    await store.append_md(f"questionnaires/{uid}-{uname}.md", md)
    await store.persist()


async def _handle_long_post(message: Message, store: Store, text: str) -> None:
    if not text:
        return
    uid = message.from_user.id
    now = time.time()
    cfg = store.config
    burst = store.burst[uid]
    burst.append((now, text))
    store.burst[uid] = [(t, s) for t, s in burst if now - t <= cfg.long_post_burst_seconds]
    series = store.burst[uid]
    long_enough = len(text) >= cfg.long_post_chars
    burst_enough = len(series) >= cfg.long_post_burst
    if not long_enough and not burst_enough:
        return
    chunks = [text] if long_enough and not burst_enough else [s for _, s in series]
    md = (
        f"# Пост {_uname(message)}\n\n"
        f"- user_id: {uid}\n"
        f"- date: {datetime.now().date().isoformat()}\n\n"
        + "\n\n".join(chunks)
        + "\n"
    )
    await store.append_md(
        f"posts/{datetime.now().date().isoformat()}-{message.message_id}.md", md
    )
    store.burst[uid] = []


async def _handle_todo(message: Message, store: Store, text: str) -> None:
    from app.parse import TODO_RE

    m = TODO_RE.match(text.strip())
    if not m:
        return
    item = m.group(2).strip()
    uid = message.from_user.id
    uname = _uname(message)
    md = f"- [{datetime.now().date().isoformat()}] {item}\n"
    await store.append_md(f"todos/{uid}-{uname}.md", md)
    await message.reply("Записал в список «сделаю».")


async def _handle_schedule(message: Message, store: Store, text: str) -> None:
    parsed = parse_schedule(text, datetime.now())
    if parsed:
        title, when = parsed
        store.events.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "when": when.timestamp(),
                "author": message.from_user.id,
                "reminders_sent": [],
            }
        )
        await store.persist()
        await message.reply(f"Активность «{title}» на {when.strftime('%d.%m.%Y %H:%M')}.")
        return
    if "запланировать" in text.lower() and store.local_connected:
        await store.enqueue_nlp(
            NlpJob(
                id=str(uuid.uuid4()),
                kind="schedule",
                payload={"text": text, "user_id": message.from_user.id, "chat_id": message.chat.id},
                created_at=time.time(),
            )
        )


async def _handle_terms(message: Message, store: Store, bot: Bot, text: str) -> None:
    if not text:
        return
    addressed = False
    if message.reply_to_message and message.reply_to_message.from_user:
        addressed = bool(store.bot_username) and (
            message.reply_to_message.from_user.username == store.bot_username
        )
    uname = store.bot_username
    if uname and f"@{uname}".lower() in text.lower():
        addressed = True
    q = extract_term_query(text)
    if q:
        addressed = True
    if not addressed:
        return
    query = q or text.replace(f"@{uname}", "").strip()
    hit = glossary_lookup(query, store.glossary)
    if hit:
        term, body = hit
        await message.reply(f"<b>{escape(term)}</b>\n\n{escape(body[:3500])}", parse_mode="HTML")
        return
    if store.local_connected:
        await store.enqueue_nlp(
            NlpJob(
                id=str(uuid.uuid4()),
                kind="term",
                payload={
                    "chat_id": message.chat.id,
                    "reply_to": message.message_id,
                    "query": query,
                    "glossary": store.glossary,
                },
                created_at=time.time(),
            )
        )
    else:
        await message.reply(store.config.missing_term_reply)


async def tick_jobs(bot: Bot, store: Store) -> None:
    now = time.time()
    cfg = store.config
    chat_id = cfg.chat_id
    if chat_id and cfg.questionnaire_kick_enabled:
        timeout = cfg.questionnaire_timeout_minutes * 60
        for uid, pending in list(store.pending_questionnaires.items()):
            if pending.get("done"):
                continue
            if now - pending.get("joined_at", now) < timeout:
                continue
            try:
                await bot.ban_chat_member(chat_id, int(uid))
                await bot.unban_chat_member(chat_id, int(uid))
            except Exception:
                pass
            pending["done"] = True
            pending["kicked"] = True
            await store.log_line(f"{now:.0f}\tkick_no_questionnaire\t{uid}")
        await store.persist()

    if chat_id and cfg.inactive_warning_enabled:
        interval = cfg.inactive_check_hours * 3600
        if now - store.last_inactive_ping >= interval and store.activity:
            least = min(store.activity.items(), key=lambda kv: (kv[1].get("count", 0), kv[1].get("last", 0)))
            uid, info = least
            mention = f'<a href="tg://user?id={uid}">{escape(str(info.get("name") or uid))}</a>'
            text = cfg.inactive_warning_text.format(mention=mention)
            try:
                await bot.send_message(chat_id, text, parse_mode="HTML")
            except Exception:
                pass
            store.last_inactive_ping = now
            await store.persist()

    if chat_id:
        for ev in store.events:
            when = float(ev.get("when", 0))
            sent = set(ev.get("reminders_sent") or [])
            for minutes in cfg.activity_reminders:
                key = str(minutes)
                fire_at = when - minutes * 60
                if key in sent:
                    continue
                if now >= fire_at and now < when + 60:
                    label = f"{minutes} мин" if minutes < 60 else f"{minutes // 60} ч"
                    try:
                        await bot.send_message(
                            chat_id,
                            f"Напоминание ({label}): {ev.get('title')} — "
                            f"{datetime.fromtimestamp(when).strftime('%d.%m.%Y %H:%M')}",
                        )
                    except Exception:
                        pass
                    sent.add(key)
            ev["reminders_sent"] = list(sent)
        await store.persist()


def build_dispatcher(store: Store) -> Dispatcher:
    dp = Dispatcher()
    dp["store"] = store
    dp.include_router(router)
    return dp
