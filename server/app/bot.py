from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.filters import ChatMemberUpdatedFilter, Command
from aiogram.filters.chat_member_updated import JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.types import ChatMemberUpdated, ChatPermissions, Message

from app.models import ChatConfig, NlpJob
from app.parse import (
    contains_forbidden,
    extract_term_query,
    glossary_lookup,
    parse_schedule,
)
from app.store import Store

router = Router()

_ACTIVE = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.RESTRICTED,
}


def _uname(message: Message) -> str:
    user = message.from_user
    if not user:
        return "unknown"
    return user.username or str(user.id)


def _qkey(chat_id: int, user_id: int | str) -> str:
    return f"{chat_id}:{user_id}"


async def _kick_if_blacklisted(bot: Bot, cfg: ChatConfig, user_id: int) -> bool:
    if user_id not in cfg.blacklist:
        return False
    try:
        await bot.ban_chat_member(cfg.chat_id, user_id)
        await bot.unban_chat_member(cfg.chat_id, user_id)
    except Exception:
        pass
    return True


@router.my_chat_member()
async def on_bot_membership(event: ChatMemberUpdated, bot: Bot, store: Store) -> None:
    chat = event.chat
    status = event.new_chat_member.status
    if chat.type == ChatType.CHANNEL:
        if status in _ACTIVE:
            # Channel the bot can read: remember id only; mapping to chats is per-chat in GUI.
            await store.log_line(f"{time.time():.0f}\tchannel_added\t{chat.id}\t{chat.title or ''}")
        return
    if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    if status in _ACTIVE:
        cfg = await store.ensure_chat(
            chat.id,
            title=chat.title or str(chat.id),
            username=chat.username or "",
            chat_type=chat.type.value,
        )
        await store.log_line(
            f"{time.time():.0f}\tbot_joined\t{chat.id}\t{cfg.title}",
            chat_id=chat.id,
        )
        try:
            await bot.send_message(
                chat.id,
                f"Чат привязан. ID: <code>{chat.id}</code>\n"
                "Правила этого чата настраиваются отдельно в локальном GUI.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return
    existing = store.chat(chat.id)
    if existing:
        existing.enabled = False
        await store.persist()
        await store.broadcast_config()
        await store.log_line(f"{time.time():.0f}\tbot_left\t{chat.id}", chat_id=chat.id)


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_join(event: ChatMemberUpdated, bot: Bot, store: Store) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return
    chat_id = event.chat.id
    cfg = await store.ensure_chat(
        chat_id,
        title=event.chat.title or str(chat_id),
        username=event.chat.username or "",
        chat_type=event.chat.type.value if hasattr(event.chat.type, "value") else str(event.chat.type),
    )
    if not cfg.enabled:
        return
    if await _kick_if_blacklisted(bot, cfg, user.id):
        await store.log_line(f"{time.time():.0f}\tkick_blacklist\t{user.id}", chat_id=chat_id)
        return
    sent = await bot.send_message(chat_id, cfg.welcome_text)
    store.pending_questionnaires[_qkey(chat_id, user.id)] = {
        "user_id": user.id,
        "chat_id": chat_id,
        "username": user.username or "",
        "full_name": user.full_name,
        "joined_at": time.time(),
        "welcome_message_id": sent.message_id,
        "fragments": [],
        "done": False,
    }
    act = store.activity.setdefault(str(chat_id), {})
    act.setdefault(
        str(user.id),
        {"count": 0, "last": time.time(), "name": user.full_name, "username": user.username},
    )
    await store.log_line(f"{time.time():.0f}\tjoin\t{user.id}\t{user.full_name}", chat_id=chat_id)
    await store.persist()


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_leave(event: ChatMemberUpdated, store: Store) -> None:
    user = event.old_chat_member.user
    if user.is_bot:
        return
    store.pending_questionnaires.pop(_qkey(event.chat.id, user.id), None)
    await store.persist()


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot, store: Store) -> None:
    src = message.chat.id
    for cfg in store.chats.values():
        if not cfg.enabled or src not in cfg.channel_ids:
            continue
        try:
            await bot.copy_message(cfg.chat_id, src, message.message_id)
            await store.log_line(
                f"{time.time():.0f}\trepost\t{src}\t{message.message_id}",
                chat_id=cfg.chat_id,
            )
        except Exception as exc:
            await store.log_line(f"{time.time():.0f}\trepost_fail\t{exc}", chat_id=cfg.chat_id)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Я админ чатов. Каждый чат настраивается отдельно в локальном GUI. "
        "После добавления в группу ID подставится сам."
    )


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def on_group_message(message: Message, bot: Bot, store: Store) -> None:
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id
    chat_id = message.chat.id
    cfg = await store.ensure_chat(
        chat_id,
        title=message.chat.title or str(chat_id),
        username=message.chat.username or "",
        chat_type=message.chat.type.value,
    )
    if not cfg.enabled:
        return
    if await _kick_if_blacklisted(bot, cfg, uid):
        await store.log_line(f"{time.time():.0f}\tkick_blacklist\t{uid}", chat_id=chat_id)
        return

    text = message.text or message.caption or ""
    name = message.from_user.full_name
    rec = store.activity.setdefault(str(chat_id), {}).setdefault(
        str(uid),
        {"count": 0, "last": 0, "name": name, "username": message.from_user.username},
    )
    rec["count"] = int(rec.get("count", 0)) + 1
    rec["last"] = time.time()
    rec["name"] = name

    await store.log_line(
        f"{datetime.now(timezone.utc).isoformat()}\t{uid}\t{_uname(message)}\t{text[:2000]}",
        chat_id=chat_id,
    )

    if text and contains_forbidden(text, cfg.forbidden_words):
        try:
            await message.delete()
        except Exception:
            pass
        until = int(time.time()) + cfg.mute_seconds
        try:
            await bot.restrict_chat_member(
                chat_id,
                uid,
                ChatPermissions(can_send_messages=False),
                until_date=until,
            )
        except Exception:
            pass
        notice = cfg.mute_notice.format(minutes=cfg.mute_seconds // 60)
        await bot.send_message(chat_id, notice)
        await store.log_line(f"{time.time():.0f}\tmute\t{uid}", chat_id=chat_id)
        return

    if cfg.nlp_profanity and text and store.local_connected:
        await store.enqueue_nlp(
            NlpJob(
                id=str(uuid.uuid4()),
                kind="profanity",
                payload={
                    "user_id": uid,
                    "chat_id": chat_id,
                    "message_id": message.message_id,
                    "text": text,
                },
                created_at=time.time(),
            )
        )

    await _handle_questionnaire(message, store, cfg, text)
    await _handle_long_post(message, store, cfg, text)
    await _handle_todo(message, store, cfg, text)
    await _handle_schedule(message, store, cfg, text)
    await _handle_terms(message, store, bot, cfg, text)


async def _handle_questionnaire(message: Message, store: Store, cfg: ChatConfig, text: str) -> None:
    key = _qkey(cfg.chat_id, message.from_user.id)
    pending = store.pending_questionnaires.get(key)
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
            await complete_questionnaire(store, key)
        else:
            await store.persist()
        return
    if store.local_connected:
        await store.enqueue_nlp(
            NlpJob(
                id=str(uuid.uuid4()),
                kind="questionnaire",
                payload={
                    "user_id": message.from_user.id,
                    "chat_id": cfg.chat_id,
                    "text": text,
                    "username": pending.get("username"),
                },
                created_at=time.time(),
            )
        )


async def complete_questionnaire(store: Store, key: str) -> None:
    pending = store.pending_questionnaires.get(key)
    if not pending:
        return
    pending["done"] = True
    body = "\n\n".join(pending.get("fragments") or [])
    uname = pending.get("username") or str(pending.get("user_id"))
    chat_id = pending.get("chat_id")
    md = (
        f"# Анкета {pending.get('full_name')} (@{uname})\n\n"
        f"- chat_id: {chat_id}\n"
        f"- user_id: {pending.get('user_id')}\n"
        f"- joined: {datetime.fromtimestamp(pending['joined_at']).isoformat()}\n\n"
        f"{body}\n"
    )
    await store.append_md(f"questionnaires/{chat_id}/{pending.get('user_id')}-{uname}.md", md)
    await store.persist()


async def _handle_long_post(message: Message, store: Store, cfg: ChatConfig, text: str) -> None:
    if not text:
        return
    uid = message.from_user.id
    now = time.time()
    bkey = _qkey(cfg.chat_id, uid)
    burst = store.burst[bkey]
    burst.append((now, text))
    store.burst[bkey] = [(t, s) for t, s in burst if now - t <= cfg.long_post_burst_seconds]
    series = store.burst[bkey]
    long_enough = len(text) >= cfg.long_post_chars
    burst_enough = len(series) >= cfg.long_post_burst
    if not long_enough and not burst_enough:
        return
    chunks = [text] if long_enough and not burst_enough else [s for _, s in series]
    md = (
        f"# Пост {_uname(message)}\n\n"
        f"- chat_id: {cfg.chat_id}\n"
        f"- user_id: {uid}\n"
        f"- date: {datetime.now().date().isoformat()}\n\n"
        + "\n\n".join(chunks)
        + "\n"
    )
    await store.append_md(
        f"posts/{cfg.chat_id}/{datetime.now().date().isoformat()}-{message.message_id}.md", md
    )
    store.burst[bkey] = []


async def _handle_todo(message: Message, store: Store, cfg: ChatConfig, text: str) -> None:
    from app.parse import TODO_RE

    m = TODO_RE.match(text.strip())
    if not m:
        return
    item = m.group(2).strip()
    uid = message.from_user.id
    uname = _uname(message)
    md = f"- [{datetime.now().date().isoformat()}] {item}\n"
    await store.append_md(f"todos/{cfg.chat_id}/{uid}-{uname}.md", md)
    await message.reply("Записал в список «сделаю».")


async def _handle_schedule(message: Message, store: Store, cfg: ChatConfig, text: str) -> None:
    parsed = parse_schedule(text, datetime.now())
    if parsed:
        title, when = parsed
        store.events.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "when": when.timestamp(),
                "author": message.from_user.id,
                "chat_id": cfg.chat_id,
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
                payload={
                    "text": text,
                    "user_id": message.from_user.id,
                    "chat_id": cfg.chat_id,
                },
                created_at=time.time(),
            )
        )


async def _handle_terms(message: Message, store: Store, bot: Bot, cfg: ChatConfig, text: str) -> None:
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
                    "chat_id": cfg.chat_id,
                    "reply_to": message.message_id,
                    "query": query,
                    "glossary": store.glossary,
                    "missing": cfg.missing_term_reply,
                },
                created_at=time.time(),
            )
        )
    else:
        await message.reply(cfg.missing_term_reply)


async def tick_jobs(bot: Bot, store: Store) -> None:
    now = time.time()
    for cfg in list(store.chats.values()):
        if not cfg.enabled:
            continue
        chat_id = cfg.chat_id
        if cfg.questionnaire_kick_enabled:
            timeout = cfg.questionnaire_timeout_minutes * 60
            for key, pending in list(store.pending_questionnaires.items()):
                if pending.get("chat_id") != chat_id or pending.get("done"):
                    continue
                if now - pending.get("joined_at", now) < timeout:
                    continue
                try:
                    await bot.ban_chat_member(chat_id, int(pending["user_id"]))
                    await bot.unban_chat_member(chat_id, int(pending["user_id"]))
                except Exception:
                    pass
                pending["done"] = True
                pending["kicked"] = True
                await store.log_line(
                    f"{now:.0f}\tkick_no_questionnaire\t{pending.get('user_id')}",
                    chat_id=chat_id,
                )

        if cfg.inactive_warning_enabled:
            interval = cfg.inactive_check_hours * 3600
            last = store.last_inactive_ping.get(str(chat_id), 0.0)
            members = store.activity.get(str(chat_id)) or {}
            if now - last >= interval and members:
                least = min(members.items(), key=lambda kv: (kv[1].get("count", 0), kv[1].get("last", 0)))
                uid, info = least
                mention = f'<a href="tg://user?id={uid}">{escape(str(info.get("name") or uid))}</a>'
                text = cfg.inactive_warning_text.format(mention=mention)
                try:
                    await bot.send_message(chat_id, text, parse_mode="HTML")
                except Exception:
                    pass
                store.last_inactive_ping[str(chat_id)] = now

        for ev in store.events:
            if int(ev.get("chat_id") or 0) != chat_id:
                continue
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
