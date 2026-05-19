"""
Telegram Broadcast Bot
======================
Features:
  - /broadcast <message>               → Send to ALL groups/channels instantly
  - /schedule HH:MM days <message>     → Schedule on specific days
  - /listschedules                     → Show all scheduled messages
  - /cancelschedule <id>               → Cancel a scheduled message
  - /listchats                         → Show all registered chats
  - /help                              → Show help

Days format: mon,tue,wed,thu,fri,sat,sun  (comma separated, no spaces)
Examples:
  /schedule 09:00 mon,fri Good morning!         → Every Monday & Friday at 9am
  /schedule 08:00 mon,tue,wed,thu,fri Hello!    → Every weekday at 8am
  /schedule 10:00 sat,sun Weekend message!      → Every weekend at 10am
  /schedule 07:00 everyday Rise and shine!      → Every day at 7am

Setup:
  1. pip install python-telegram-bot apscheduler
  2. Replace BOT_TOKEN and ADMIN_USER_ID below
  3. Add your bot as ADMIN to every group/channel
  4. Run: python telegram_broadcast_bot.py
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────
# ✏️  CONFIGURE THESE TWO VALUES
# ─────────────────────────────────────────────
BOT_TOKEN = "8888979016:AAHtA_dZl0UbHVoQP-lhUghwrK61Ln8ZAlw"       # From @BotFather
ADMIN_USER_ID = 1776630741               # Your Telegram user ID (from @userinfobot)
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Store chat IDs the bot has been added to
known_chats: set[int] = set()

# Store scheduled jobs: { job_id: {"time": "HH:MM", "days": str, "message": str} }
scheduled_jobs: dict[str, dict] = {}

scheduler = AsyncIOScheduler()

# Day name mapping
DAY_MAP = {
    "mon": "mon", "monday": "mon",
    "tue": "tue", "tuesday": "tue",
    "wed": "wed", "wednesday": "wed",
    "thu": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri",
    "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}
DAY_LABELS = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
    "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}


# ── Helpers ──────────────────────────────────

def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_USER_ID


def parse_days(days_str: str) -> tuple[list[str], str]:
    if days_str.lower() in ("everyday", "daily", "all"):
        return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ""

    parts = [d.strip().lower() for d in days_str.split(",")]
    resolved = []
    for part in parts:
        if part in DAY_MAP:
            resolved.append(DAY_MAP[part])
        else:
            return [], f"❌ Unknown day: '{part}'. Use: mon, tue, wed, thu, fri, sat, sun"

    seen = set()
    unique = []
    for d in resolved:
        if d not in seen:
            seen.add(d)
            unique.append(d)

    return unique, ""


def days_to_label(days: list[str]) -> str:
    if set(days) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
        return "Every day"
    if set(days) == {"mon", "tue", "wed", "thu", "fri"}:
        return "Weekdays (Mon–Fri)"
    if set(days) == {"sat", "sun"}:
        return "Weekends (Sat & Sun)"
    return ", ".join(DAY_LABELS[d] for d in days)


async def send_to_all(application: Application, message: str) -> tuple[int, int]:
    success, fail = 0, 0
    for chat_id in list(known_chats):
        try:
            await application.bot.send_message(chat_id=chat_id, text=message)
            success += 1
        except Exception as e:
            logger.warning(f"Failed to send to {chat_id}: {e}")
            fail += 1
    return success, fail


# ── Auto-track chats ──────────────────────────

async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.id != ADMIN_USER_ID:
        known_chats.add(update.effective_chat.id)


# ── Commands ──────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "👋 *Broadcast Bot is running!*\n\n"
        "*Commands:*\n"
        "/broadcast <message>\n"
        "→ Send to all chats right now\n\n"
        "/schedule HH:MM <days> <message>\n"
        "→ Schedule on specific days\n\n"
        "/listschedules — View all schedules\n"
        "/cancelschedule <id> — Cancel a schedule\n"
        "/listchats — Show all registered chats\n"
        "/help — Show this help\n\n"
        "*Days examples:*\n"
        "`mon,fri` — Monday & Friday only\n"
        "`mon,tue,wed,thu,fri` — Weekdays\n"
        "`sat,sun` — Weekends only\n"
        "`everyday` — Every day",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ You are not authorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <your message here>")
        return

    message = " ".join(context.args)

    if not known_chats:
        await update.message.reply_text(
            "⚠️ No chats registered yet.\n"
            "Make sure you've added the bot as admin to your groups/channels."
        )
        return

    await update.message.reply_text(f"📤 Sending to {len(known_chats)} chat(s)...")
    success, fail = await send_to_all(context.application, message)
    await update.message.reply_text(f"✅ Done!\n• Sent: {success}\n• Failed: {fail}")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ You are not authorized.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /schedule HH:MM <days> <message>\n\n"
            "Examples:\n"
            "/schedule 09:00 mon,fri Good morning!\n"
            "/schedule 08:00 mon,tue,wed,thu,fri Daily update!\n"
            "/schedule 10:00 sat,sun Weekend post!\n"
            "/schedule 07:00 everyday Rise and shine!"
        )
        return

    time_str = context.args[0]
    days_str = context.args[1]
    message = " ".join(context.args[2:])

    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid time. Use HH:MM (e.g. 09:00)")
        return

    days, error = parse_days(days_str)
    if error:
        await update.message.reply_text(
            f"{error}\n\nValid: mon tue wed thu fri sat sun\nOr use: everyday"
        )
        return

    job_id = f"sched_{hour:02d}{minute:02d}_{len(scheduled_jobs)}"
    days_cron = ",".join(days)

    async def scheduled_broadcast():
        s, f = await send_to_all(context.application, message)
        logger.info(f"Job '{job_id}': sent={s}, failed={f}")

    scheduler.add_job(
        scheduled_broadcast,
        trigger="cron",
        day_of_week=days_cron,
        hour=hour,
        minute=minute,
        id=job_id,
    )

    scheduled_jobs[job_id] = {
        "time": time_str,
        "days": days,
        "days_label": days_to_label(days),
        "message": message,
    }

    await update.message.reply_text(
        f"⏰ *Scheduled!*\n"
        f"• Time: `{time_str}`\n"
        f"• Days: {days_to_label(days)}\n"
        f"• Message: {message}\n"
        f"• ID: `{job_id}`",
        parse_mode="Markdown",
    )


async def cmd_list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if not scheduled_jobs:
        await update.message.reply_text("📋 No scheduled messages.")
        return

    lines = [f"📋 *Scheduled Messages ({len(scheduled_jobs)}):*\n"]
    for job_id, info in scheduled_jobs.items():
        lines.append(
            f"🕐 `{info['time']}` — {info['days_label']}\n"
            f"💬 {info['message']}\n"
            f"🆔 `{job_id}`\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /cancelschedule <job_id>")
        return

    job_id = context.args[0]

    if job_id not in scheduled_jobs:
        await update.message.reply_text(f"❌ No schedule found with ID: `{job_id}`", parse_mode="Markdown")
        return

    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    info = scheduled_jobs.pop(job_id)
    await update.message.reply_text(
        f"✅ Cancelled!\n• Was: `{info['time']}` on {info['days_label']}\n• Message: {info['message']}",
        parse_mode="Markdown",
    )


async def cmd_list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if not known_chats:
        await update.message.reply_text("📋 No chats registered yet.")
        return

    lines = [f"📋 *Registered Chats ({len(known_chats)}):*\n"]
    for chat_id in known_chats:
        try:
            chat = await context.bot.get_chat(chat_id)
            lines.append(f"• {chat.title or chat.username or 'Unknown'} (`{chat_id}`)")
        except Exception:
            lines.append(f"• Unknown (`{chat_id}`)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Main ──────────────────────────────────────

async def post_init(application: Application):
    scheduler.start()

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Please set your BOT_TOKEN in the script first!")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("listschedules", cmd_list_schedules))
    app.add_handler(CommandHandler("cancelschedule", cmd_cancel_schedule))
    app.add_handler(CommandHandler("listchats", cmd_list_chats))
    app.add_handler(MessageHandler(filters.ALL, track_chat))

    print("🤖 Broadcast bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
