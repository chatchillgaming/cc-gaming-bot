import os
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

# Separate scores for each game.
scores = {
    "uno": defaultdict(int),
    "cricket": defaultdict(int),
    "word": defaultdict(int),
    "ludo": defaultdict(int),
}

# Word-clue rounds by chat.
word_rounds = {}

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
    await update.message.reply_text("🎮 Choose your game:", reply_markup=main_menu())

async def leaderboard_text(game):
    board = sorted(scores[game].items(), key=lambda x: x[1], reverse=True)[:10]
    title = {"uno":"🃏 UNO", "cricket":"🏏 CRICKET", "word":"🔤 WORD CLUE", "ludo":"🎲 LUDO"}[game]
    if not board:
        return f"🏆 {title} LEADERBOARD\n\nNo scores yet."
    lines = [f"🏆 {title} LEADERBOARD", ""]
    for i, (uid, pts) in enumerate(board, 1):
        lines.append(f"{i}. `{uid}` — {pts} pts")
    return "\n".join(lines)

async def leaderboards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🃏 UNO", callback_data="lb:uno"),
         InlineKeyboardButton("🏏 Cricket", callback_data="lb:cricket")],
        [InlineKeyboardButton("🔤 Word", callback_data="lb:word"),
         InlineKeyboardButton("🎲 Ludo", callback_data="lb:ludo")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="menu")]
    ]
    await update.message.reply_text("🏆 Select a leaderboard:", reply_markup=InlineKeyboardMarkup(buttons))

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lines = [
        "👤 *MY PROFILE*",
        f"ID: `{uid}`",
        "",
        f"🃏 UNO: {scores['uno'][uid]} pts",
        f"🏏 Cricket: {scores['cricket'][uid]} pts",
        f"🔤 Word: {scores['word'][uid]} pts",
        f"🎲 Ludo: {scores['ludo'][uid]} pts",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔤 *WORD CLUE*\n\n"
        "Use `/wordhost SECRET_WORD` to start a round.\n"
        "The host's secret word stays hidden from the group.\n"
        "Maximum time: 5 minutes.\n"
        "Correct answer: +2 points.",
        parse_mode="Markdown",
    )

async def wordhost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.chat.type in ("group", "supergroup"):
        await update.message.reply_text("Use /wordhost inside the group.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /wordhost SECRET_WORD")
        return

    secret = " ".join(context.args).strip()
    chat_id = update.effective_chat.id
    word_rounds[chat_id] = {
        "host": update.effective_user.id,
        "word": secret.casefold(),
        "expires": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    await update.message.reply_text(
        "🔤 *WORD CLUE ROUND STARTED!*\n\n"
        "Host: give your clue now.\n"
        "⏱️ Time limit: 5 minutes\n"
        "🏆 Correct answer: +2 points",
        parse_mode="Markdown",
    )

async def word_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    round_data = word_rounds.get(chat_id)
    if not round_data:
        return
    if update.effective_user.id == round_data["host"]:
        return
    if datetime.now(timezone.utc) > round_data["expires"]:
        word_rounds.pop(chat_id, None)
        await update.message.reply_text("⏰ Word round ended!")
        return
    if update.message.text.strip().casefold() == round_data["word"]:
        scores["word"][update.effective_user.id] += 2
        word_rounds.pop(chat_id, None)
        await update.message.reply_text(
            f"🎉 Correct!\n\n"
            f"🏆 {update.effective_user.full_name} gets +2 points!"
        )

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "menu":
        await q.edit_message_text("🎮 Choose a game:", reply_markup=main_menu())
    elif data == "leaderboards":
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
        game = data.split(":", 1)[1]
        await q.edit_message_text(
            await leaderboard_text(game),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Leaderboards", callback_data="leaderboards")]
            ])
        )
    elif data == "profile":
        uid = q.from_user.id
        await q.edit_message_text(
            f"👤 *MY PROFILE*\n\n"
            f"🃏 UNO: {scores['uno'][uid]} pts\n"
            f"🏏 Cricket: {scores['cricket'][uid]} pts\n"
            f"🔤 Word: {scores['word'][uid]} pts\n"
            f"🎲 Ludo: {scores['ludo'][uid]} pts",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Menu", callback_data="menu")]
            ])
        )
    elif data.startswith("game:"):
        game = data.split(":", 1)[1]
        names = {
            "uno": "🃏 UNO",
            "cricket": "🏏 CRICKET",
            "word": "🔤 WORD CLUE",
            "ludo": "🎲 LUDO",
        }
        await q.edit_message_text(
            f"{names[game]}\n\n"
            "Game engine setup is the next build stage.\n"
            "Use the menu to view separate leaderboards.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏆 Leaderboard", callback_data=f"lb:{game}")],
                [InlineKeyboardButton("⬅️ Menu", callback_data="menu")]
            ])
        )

def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("games", games))
    app.add_handler(CommandHandler("leaderboard", leaderboards))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("word", word_command))
    app.add_handler(CommandHandler("wordhost", wordhost))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, word_answers))
    return app

if __name__ == "__main__":
    build_app().run_polling()
