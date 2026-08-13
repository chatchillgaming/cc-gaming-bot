import os
import logging
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# =========================
# UNO DATA
# =========================

uno_lobbies = {}

UNO_JOIN_TIME = 120
UNO_MIN_PLAYERS = 2


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🃏 UNO", callback_data="uno"),
            InlineKeyboardButton("🔤 WORD GAME", callback_data="word"),
        ],
        [
            InlineKeyboardButton("🏏 CRICKET", callback_data="cricket"),
            InlineKeyboardButton("🎲 LUDO", callback_data="ludo"),
        ],
        [
            InlineKeyboardButton(
                "🏆 LEADERBOARDS",
                callback_data="leaderboards"
            )
        ],
    ])


def uno_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 JOIN UNO",
                callback_data="uno_join"
            )
        ],
        [
            InlineKeyboardButton(
                "🚪 LEAVE UNO",
                callback_data="uno_leave"
            )
        ],
        [
            InlineKeyboardButton(
                "⚡ FORCE START",
                callback_data="uno_force"
            )
        ],
    ])


def get_uno_lobby(chat_id):
    if chat_id not in uno_lobbies:
        uno_lobbies[chat_id] = {
            "players": {},
            "active": False,
            "timer_task": None,
        }

    return uno_lobbies[chat_id]


def lobby_text(lobby):
    players = lobby["players"]

    if not players:
        player_text = "No players joined yet."
    else:
        player_text = "\n".join(
            f"{index}. {name}"
            for index, name in enumerate(players.values(), 1)
        )

    return (
        "🃏 <b>UNO LOBBY</b>\n\n"
        f"👥 Players: <b>{len(players)}</b>\n"
        f"⏱️ Joining Time: <b>{UNO_JOIN_TIME} seconds</b>\n\n"
        f"{player_text}\n\n"
        "👇 Join the game!"
    )


# =========================
# START / MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🎮 <b>Welcome to CC Gaming!</b> 🔥\n\n"
        "🃏 UNO • 🔤 Word • 🏏 Cricket • 🎲 Ludo\n\n"
        "<b>Choose your game & let's play! 🚀</b>"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 <b>CC GAMING MENU</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================
# UNO COMMANDS
# =========================

async def uno_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    lobby = get_uno_lobby(chat_id)

    if lobby["active"]:
        await update.message.reply_text(
            "🃏 UNO match is already running!"
        )
        return

    await update.message.reply_text(
        lobby_text(lobby),
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )

    if lobby["timer_task"] is None:
        lobby["timer_task"] = asyncio.create_task(
            uno_lobby_timer(
                context,
                chat_id
            )
        )


async def join_uno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    lobby = get_uno_lobby(chat_id)

    if lobby["active"]:
        await update.message.reply_text(
            "❌ UNO match already started!"
        )
        return

    if user.id in lobby["players"]:
        await update.message.reply_text(
            "⚠️ You are already in the UNO lobby!"
        )
        return

    lobby["players"][user.id] = (
        user.full_name
    )

    await update.message.reply_text(
        f"🃏 <b>{user.full_name}</b> joined UNO! 🔥\n\n"
        + lobby_text(lobby),
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


async def leave_uno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    lobby = get_uno_lobby(chat_id)

    if user.id not in lobby["players"]:
        await update.message.reply_text(
            "❌ You are not in the UNO lobby."
        )
        return

    del lobby["players"][user.id]

    await update.message.reply_text(
        f"🚪 <b>{user.full_name}</b> left UNO.\n\n"
        + lobby_text(lobby),
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


async def force_uno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lobby = get_uno_lobby(chat_id)

    if lobby["active"]:
        await update.message.reply_text(
            "❌ UNO match already started!"
        )
        return

    if len(lobby["players"]) < UNO_MIN_PLAYERS:
        await update.message.reply_text(
            "❌ <b>Minimum 2 players required!</b>\n\n"
            f"Current players: {len(lobby['players'])}",
            parse_mode="HTML",
        )
        return

    await start_uno_match(
        context,
        chat_id
    )


# =========================
# UNO BUTTONS
# =========================

async def uno_join_button(
    query,
    context
):
    chat_id = query.message.chat.id
    user = query.from_user

    lobby = get_uno_lobby(chat_id)

    if lobby["active"]:
        await query.answer(
            "UNO match already started!",
            show_alert=True
        )
        return

    if user.id in lobby["players"]:
        await query.answer(
            "You already joined!",
            show_alert=True
        )
        return

    lobby["players"][user.id] = user.full_name

    await query.answer(
        "🃏 Joined UNO!",
        show_alert=False
    )

    await query.edit_message_text(
        lobby_text(lobby),
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


async def uno_leave_button(
    query,
    context
):
    chat_id = query.message.chat.id
    user = query.from_user

    lobby = get_uno_lobby(chat_id)

    if user.id not in lobby["players"]:
        await query.answer(
            "You are not in the lobby!",
            show_alert=True
        )
        return

    del lobby["players"][user.id]

    await query.answer(
        "🚪 You left UNO."
    )

    await query.edit_message_text(
        lobby_text(lobby),
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


async def uno_force_button(
    query,
    context
):
    chat_id = query.message.chat.id
    lobby = get_uno_lobby(chat_id)

    if len(lobby["players"]) < UNO_MIN_PLAYERS:
        await query.answer(
            "❌ Minimum 2 players required!",
            show_alert=True
        )
        return

    await query.answer(
        "⚡ Starting UNO!"
    )

    await start_uno_match(
        context,
        chat_id
    )


# =========================
# UNO TIMER
# =========================

async def uno_lobby_timer(
    context,
    chat_id
):
    await asyncio.sleep(UNO_JOIN_TIME)

    lobby = uno_lobbies.get(chat_id)

    if not lobby:
        return

    lobby["timer_task"] = None

    if lobby["active"]:
        return

    if len(lobby["players"]) >= UNO_MIN_PLAYERS:
        await start_uno_match(
            context,
            chat_id
        )

    else:
        await context.bot.send_message(
            chat_id,
            "⏰ <b>UNO LOBBY CLOSED</b>\n\n"
            "❌ Not enough players joined.\n"
            "Minimum 2 players required.",
            parse_mode="HTML",
        )


# =========================
# UNO MATCH START
# =========================

async def start_uno_match(
    context,
    chat_id
):
    lobby = get_uno_lobby(chat_id)

    if lobby["active"]:
        return

    if len(lobby["players"]) < UNO_MIN_PLAYERS:
        return

    lobby["active"] = True

    players = list(lobby["players"].values())

    player_text = "\n".join(
        f"{i}. {name}"
        for i, name in enumerate(players, 1)
    )

    await context.bot.send_message(
        chat_id,
        "🔥 <b>UNO MATCH STARTED!</b> 🔥\n\n"
        f"👥 Players: <b>{len(players)}</b>\n\n"
        f"{player_text}\n\n"
        "🃏 Card engine will start in the next phase!",
        parse_mode="HTML",
    )


# =========================
# BUTTON HANDLER
# =========================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    data = query.data

    await query.answer()

    if data == "uno":
        await query.edit_message_text(
            "🃏 <b>UNO</b>\n\n"
            "Start a new UNO lobby:",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

    elif data == "uno_join":
        await uno_join_button(
            query,
            context
        )

    elif data == "uno_leave":
        await uno_leave_button(
            query,
            context
        )

    elif data == "uno_force":
        await uno_force_button(
            query,
            context
        )

    elif data == "cricket":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "👤 SOLO",
                    callback_data="cricket_solo"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚔️ 1 VS 1",
                    callback_data="cricket_1v1"
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 TEAM",
                    callback_data="cricket_team"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ MAIN MENU",
                    callback_data="home"
                )
            ],
        ])

        await query.edit_message_text(
            "🏏 <b>CRICKET</b>\n\n"
            "Choose your mode:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    elif data == "ludo":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🟢 NORMAL",
                    callback_data="ludo_normal"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔴 CHAOS",
                    callback_data="ludo_chaos"
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ MAIN MENU",
                    callback_data="home"
                )
            ],
        ])

        await query.edit_message_text(
            "🎲 <b>LUDO</b>\n\n"
            "👥 2–4 Players\n\n"
            "Choose your mode:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    elif data == "leaderboards":
        await query.edit_message_text(
            "🏆 <b>LEADERBOARDS</b>\n\n"
            "🃏 UNO\n"
            "🔤 Word Game\n"
            "🏏 Cricket\n"
            "🎲 Ludo",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ MAIN MENU",
                        callback_data="home"
                    )
                ]
            ]),
        )

    elif data == "home":
        await query.edit_message_text(
            "🎮 <b>CC GAMING MENU</b>",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )


# =========================
# MAIN
# =========================

def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "menu",
            menu
        )
    )

    app.add_handler(
        CommandHandler(
            "uno",
            uno_command
        )
    )

    app.add_handler(
        CommandHandler(
            "joinuno",
            join_uno
        )
    )

    app.add_handler(
        CommandHandler(
            "leaveuno",
            leave_uno
        )
    )

    app.add_handler(
        CommandHandler(
            "forceuno",
            force_uno
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    print("🤖 CC Gaming Bot Started!")

    app.run_polling()


if __name__ == "__main__":
    main()
