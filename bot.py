import os
import logging

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


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    if query.data == "uno":
        await query.answer(
            "🃏 UNO module coming next!",
            show_alert=True
        )

    elif query.data == "word":
        await query.answer(
            "🔤 Word Game module coming next!",
            show_alert=True
        )

    elif query.data == "cricket":
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

    elif query.data == "ludo":
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

    elif query.data == "leaderboards":
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

    elif query.data == "home":
        await query.edit_message_text(
            "🎮 <b>CC GAMING MENU</b>",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )

    else:
        await query.answer(
            "🔥 Module will be added next!",
            show_alert=True
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 CC Gaming Bot Started!")

    app.run_polling()


if __name__ == "__main__":
    main()      
