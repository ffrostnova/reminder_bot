import re
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

TOKEN = "YOUR TELEGRAM TOKEN"

scheduler = AsyncIOScheduler()
user_jobs = {}

#SQLite
def init_db():
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS week_reminders (
            chat_id INTEGER,
            hour INTEGER,
            minute INTEGER,
            day_of_week INTEGER,
            PRIMARY KEY(chat_id, hour, minute, day_of_week)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS month_reminders (
            chat_id INTEGER,
            hour INTEGER,
            minute INTEGER,
            day_of_month INTEGER,
            PRIMARY KEY(chat_id, hour, minute, day_of_month)
        )
    """)
    conn.commit()
    conn.close()

def save_week_reminder(chat_id, hour, minute, day_of_week):
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("REPLACE INTO week_reminders (chat_id, hour, minute, day_of_week) VALUES (?, ?, ?, ?)",
              (chat_id, hour, minute, day_of_week))
    conn.commit()
    conn.close()

def save_month_reminder(chat_id, hour, minute, day_of_month):
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("REPLACE INTO month_reminders (chat_id, hour, minute, day_of_month) VALUES (?, ?, ?, ?)",
              (chat_id, hour, minute, day_of_month))
    conn.commit()
    conn.close()

def delete_week_reminders(chat_id):
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("DELETE FROM week_reminders WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def delete_month_reminders(chat_id):
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("DELETE FROM month_reminders WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def load_week_reminders():
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, hour, minute, day_of_week FROM week_reminders")
    rows = c.fetchall()
    conn.close()
    return rows

def load_month_reminders():
    conn = sqlite3.connect("reminders.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, hour, minute, day_of_month FROM month_reminders")
    rows = c.fetchall()
    conn.close()
    return rows

# Напоминания
async def send_report_reminder(app: Application, chat_id: int):
    await app.bot.send_message(chat_id=chat_id, text="❗ Пора сдать отчёт!")

def schedule_week_job(app: Application, chat_id, hour, minute, day_of_week):
    job_id = f"week_{chat_id}_{hour}_{minute}_{day_of_week}"
    if job_id in user_jobs:
        user_jobs[job_id].remove()
    trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
    job = scheduler.add_job(send_report_reminder, trigger=trigger, args=[app, chat_id], id=job_id, replace_existing=True)
    user_jobs[job_id] = job
    save_week_reminder(chat_id, hour, minute, day_of_week)

def schedule_month_job(app: Application, chat_id, hour, minute, day_of_month):
    job_id = f"month_{chat_id}_{hour}_{minute}_{day_of_month}"
    if job_id in user_jobs:
        user_jobs[job_id].remove()
    trigger = CronTrigger(day=day_of_month, hour=hour, minute=minute)
    job = scheduler.add_job(send_report_reminder, trigger=trigger, args=[app, chat_id], id=job_id, replace_existing=True)
    user_jobs[job_id] = job
    save_month_reminder(chat_id, hour, minute, day_of_month)

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот-напоминалка.\n\n"
        "Настройка недельных напоминаний:\n"
        "/set_week 09:00,12:00 Пн,Ср,Пт\n\n"
        "Настройка месячных напоминаний:\n"
        "/set_month 09:00,12:00 1,15,28\n\n"
        "Команда /cancel — удалить все ваши напоминания."
    )

async def set_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: /set_week ВРЕМЯ_1,ВРЕМЯ_2 ПН,СР,...")
        return

    times_str = context.args[0].split(",")
    days_str = context.args[1].split(",")

    day_map = {"Пн":0, "Вт":1, "Ср":2, "Чт":3, "Пт":4, "Сб":5, "Вс":6}

    times = []
    for t in times_str:
        if not re.match(r"^\d{1,2}:\d{2}$", t):
            await update.message.reply_text(f"❌ Неверное время: {t}")
            return
        h, m = map(int, t.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            await update.message.reply_text(f"❌ Время вне диапазона: {t}")
            return
        times.append((h, m))

    days = []
    for d in days_str:
        d = d.strip()
        if d not in day_map:
            await update.message.reply_text(f"❌ Неверный день недели: {d}")
            return
        days.append(day_map[d])

    delete_week_reminders(chat_id)

    for h, m in times:
        for day in days:
            schedule_week_job(context.application, chat_id, h, m, day)

    await update.message.reply_text(f"✅ Недельные напоминания установлены на дни {', '.join(days_str)} в {', '.join(times_str)}")

async def set_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: /set_month ВРЕМЯ_1,ВРЕМЯ_2 ДЕНЬ_1,ДЕНЬ_2,...")
        return

    times_str = context.args[0].split(",")
    days_str = context.args[1].split(",")

    times = []
    for t in times_str:
        if not re.match(r"^\d{1,2}:\d{2}$", t):
            await update.message.reply_text(f"❌ Неверное время: {t}")
            return
        h, m = map(int, t.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            await update.message.reply_text(f"❌ Время вне диапазона: {t}")
            return
        times.append((h, m))

    days = []
    for d in days_str:
        try:
            day = int(d)
            if not (1 <= day <= 31):
                await update.message.reply_text(f"❌ День месяца вне диапазона: {day}")
                return
            days.append(day)
        except ValueError:
            await update.message.reply_text(f"❌ Неверный день месяца: {d}")
            return

    delete_month_reminders(chat_id)

    for h, m in times:
        for day in days:
            schedule_month_job(context.application, chat_id, h, m, day)

    await update.message.reply_text(f"✅ Месячные напоминания установлены на дни {', '.join(days_str)} в {', '.join(times_str)}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    delete_week_reminders(chat_id)
    delete_month_reminders(chat_id)
    for job_id in list(user_jobs.keys()):
        if job_id.startswith(f"week_{chat_id}_") or job_id.startswith(f"month_{chat_id}_"):
            user_jobs[job_id].remove()
            del user_jobs[job_id]
    await update.message.reply_text("❌ Все ваши напоминания удалены.")

# Обработчик ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"⚠️ Возникла ошибка: {context.error}")

# post_init
async def post_init(app: Application):
    scheduler.start()
    for chat_id, hour, minute, day_of_week in load_week_reminders():
        schedule_week_job(app, chat_id, hour, minute, day_of_week)
    for chat_id, hour, minute, day_of_month in load_month_reminders():
        schedule_month_job(app, chat_id, hour, minute, day_of_month)
    print(f"🔄 Восстановлены все напоминания из базы.")

# Main
def main():
    init_db()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_week", set_week))
    app.add_handler(CommandHandler("set_month", set_month))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_error_handler(error_handler)
    print("✅ Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()