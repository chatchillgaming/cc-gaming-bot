import os
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

DB = "cc_gaming.db"

def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS scores (
        user_id INTEGER NOT NULL,
        game TEXT NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, game)
    )""")
    con.commit()
    return con

def add_points(user_id, game, points):
    con = db()
    con.execute(
        """INSERT INTO scores(user_id, game, points) VALUES(?,?,?)
           ON CONFLICT(user_id, game) DO UPDATE SET points=points+excluded.points""",
        (user_id, game, points)
    )
    con.commit()
    con.close()

def get_points(user_id, game):
    con = db()
    row = con.execute(
        "SELECT points FROM scores WHERE user_id=? AND game=?",
        (user_id, game)
    ).fetchone()
    con.close()
    return row[0] if row else 0

def leaderboard(game):
    con = db()
    rows = con.execute(
        "SELECT user_id, points FROM scores WHERE game=? ORDER BY points DESC LIMIT 10",
        (game,)
    ).fetchall()
    con.close()
    return rows

# Active Word Clue rounds.
# A round is created in a group; the host sets the secret word privately.
word_rounds = {}  # chat_id -> dict

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 UNO", callback_data="game:uno"),
         InlineKeyboardButton("🏏 CRICKET", callback_data="game:cricket")],
        [InlineKeyboardButton("🔤 WORD CLUE", callback_data="game:word"),
         InlineKeyboardButton("🎲 LUDO", callback_data="game:ludo")],
        [InlineKeyboardButton("🏆 LEADERBOARDS", callback_data="leaderboards"),
         InlineKeyboardButton("👤 MY PROFILE", callback_data="profile")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *CHAT & CHILL GAMING BOT*\n\n"
        "🃏 UNO • 🏏 Cricket • 🔤 Word Clue • 🎲 Ludo\n\n"
        "Choose a game:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )

async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Choose a game:", reply_markup=main_menu())

async def leaderboard_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 Select a leaderboard:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🃏 UNO", callback_data="lb:uno"),
             InlineKeyboardButton("🏏 Cricket", callback_data="lb:cricket")],
            [InlineKeyboardButton("🔤 Word", callback_data="lb:word"),
             InlineKeyboardButton("🎲 Ludo", callback_data="lb:ludo")],
        ])
    )

async def profile_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        "👤 *MY PROFILE*\n\n"
        f"🃏 UNO: {get_points(uid,'uno')} pts\n"
        f"🏏 Cricket: {get_points(uid,'cricket')} pts\n"
        f"🔤 Word: {get_points(uid,'word')} pts\n"
        f"🎲 Ludo: {get_points(uid,'ludo')} pts",
        parse_mode="Markdown"
    )

async def word_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔤 *WORD CLUE — HOW TO PLAY*\n\n"
        "1️⃣ Start `/wordhost` inside the group.\n"
        "2️⃣ The bot will ask the host to open a private chat with the bot.\n"
        "3️⃣ Host sends `/wordset SECRET_WORD` privately.\n"
        "4️⃣ Host gives a clue in the group WITHOUT saying the word.\n"
        "5️⃣ Players answer by sending the word in the group.\n\n"
        "⏱️ Maximum: 5 minutes\n"
        "✅ Correct answer: +2 points\n"
        "🏆 First correct answer wins the round.",
        parse_mode="Markdown"
    )

async def wordhost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /wordhost inside your gaming group.")
        return

    chat_id = update.effective_chat.id
    if chat_id in word_rounds:
        await update.message.reply_text("⚠️ A Word Clue round is already active in this group.")
        return

    uid = update.effective_user.id
    word_rounds[chat_id] = {
        "host": uid,
        "word": None,
        "expires": None,
        "started": False,
    }

    me = await context.bot.get_me()
    await update.message.reply_text(
        f"🔤 *WORD CLUE ROUND CREATED!*\n\n"
        f"👑 Host: {update.effective_user.full_name}\n\n"
        f"Host, open @{me.username} in private chat and send:\n"
        f"`/wordset YOUR_SECRET_WORD`\n\n"
        f"After setting the word, give your clue in this group.\n"
        f"⏱️ The 5-minute timer starts when the secret word is set.",
        parse_mode="Markdown"
    )

async def wordset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("🔐 Send /wordset privately to the bot.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /wordset SECRET_WORD")
        return

    uid = update.effective_user.id
    pending = [cid for cid, r in word_rounds.items() if r["host"] == uid and r["word"] is None]
    if not pending:
        await update.message.reply_text("❌ You don't have a pending Word Clue round.")
        return

    chat_id = pending[-1]
    secret = " ".join(context.args).strip()
    word_rounds[chat_id]["word"] = secret.casefold()
    word_rounds[chat_id]["expires"] = datetime.now(timezone.utc) + timedelta(minutes=5)
    word_rounds[chat_id]["started"] = True

    await update.message.reply_text(
        "🔐 Secret word saved.\n"
        "Now go to the group and give your clue. ⏱️ You have 5 minutes."
    )
    await context.bot.send_message(
        chat_id,
        "🔤 *WORD CLUE ROUND STARTED!*\n\n"
        "👑 Host: give your clue now.\n"
        "⏱️ Time limit: 5 minutes\n"
        "🏆 Correct answer: +2 points\n\n"
        "Players: send your answer in the group!",
        parse_mode="Markdown"
    )
    context.application.create_task(expire_word_round(context, chat_id))

async def expire_word_round(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    await asyncio.sleep(300)
    round_data = word_rounds.get(chat_id)
    if round_data and round_data.get("started"):
        word_rounds.pop(chat_id, None)
        await context.bot.send_message(chat_id, "⏰ *Time's up!* No correct answer this round.", parse_mode="Markdown")

async def word_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.effective_chat.type not in ("group", "supergroup"):
        return

    chat_id = update.effective_chat.id
    r = word_rounds.get(chat_id)
    if not r or not r.get("started"):
        return
    if update.effective_user.id == r["host"]:
        return

    if datetime.now(timezone.utc) > r["expires"]:
        word_rounds.pop(chat_id, None)
        await update.message.reply_text("⏰ Word round ended!")
        return

    if update.message.text.strip().casefold() == r["word"]:
        word_rounds.pop(chat_id, None)
        add_points(update.effective_user.id, "word", 2)
        await update.message.reply_text(
            f"🎉 *CORRECT!*\n\n"
            f"🏆 {update.effective_user.full_name} wins the round!\n"
            f"⭐ +2 Word points",
            parse_mode="Markdown"
        )

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "leaderboards":
        await q.edit_message_text(
            "🏆 Select a leaderboard:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🃏 UNO", callback_data="lb:uno"),
                 InlineKeyboardButton("🏏 Cricket", callback_data="lb:cricket")],
                [InlineKeyboardButton("🔤 Word", callback_data="lb:word"),
                 InlineKeyboardButton("🎲 Ludo", callback_data="lb:ludo")],
                [InlineKeyboardButton("⬅️ Menu", callback_data="menu")]
            ])
        )
    elif data.startswith("lb:"):
        game = data.split(":",1)[1]
        names = {"uno":"🃏 UNO","cricket":"🏏 CRICKET","word":"🔤 WORD CLUE","ludo":"🎲 LUDO"}
        rows = leaderboard(game)
        text = f"🏆 *{names[game]} LEADERBOARD*\n\n"
        if not rows:
            text += "No scores yet."
        else:
            for i,(uid,pts) in enumerate(rows,1):
                text += f"{i}. `{uid}` — {pts} pts\n"
        await q.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="leaderboards")]])
        )
    elif data == "profile":
        uid = q.from_user.id
        await q.edit_message_text(
            "👤 *MY PROFILE*\n\n"
            f"🃏 UNO: {get_points(uid,'uno')} pts\n"
            f"🏏 Cricket: {get_points(uid,'cricket')} pts\n"
            f"🔤 Word: {get_points(uid,'word')} pts\n"
            f"🎲 Ludo: {get_points(uid,'ludo')} pts",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu")]])
        )
    elif data == "menu":
        await q.edit_message_text("🎮 Choose a game:", reply_markup=main_menu())
    elif data == "game:word":
        await q.edit_message_text(
            "🔤 *WORD CLUE*\n\n"
            "Start a round in your group with `/wordhost`.\n"
            "The host chooses the secret word privately.\n"
            "⏱️ 5 minutes • ✅ Correct = +2 points",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Word Leaderboard", callback_data="lb:word")]])
        )
    else:
        await q.edit_message_text(
            "🎮 This game engine will be added next.\n"
            "🔤 Word Clue is ready in this version.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu")]])
        )

def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("games", games))
    app.add_handler(CommandHandler("leaderboard", leaderboard_menu_message))
    app.add_handler(CommandHandler("profile", profile_message))
    app.add_handler(CommandHandler("word", word_help))
    app.add_handler(CommandHandler("wordhost", wordhost))
    app.add_handler(CommandHandler("wordset", wordset))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, word_answers))
    return app

if __name__ == "__main__":
    build_app().run_polling()
