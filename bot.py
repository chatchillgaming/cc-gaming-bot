import os
import random
import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
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


# ============================================================
# SETTINGS
# ============================================================

UNO_JOIN_TIME = 120
UNO_MIN_PLAYERS = 2


# ============================================================
# GAME STORAGE
# ============================================================

uno_games = {}


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🃏 UNO",
                callback_data="uno"
            ),
            InlineKeyboardButton(
                "🔤 WORD GAME",
                callback_data="word"
            ),
        ],
        [
            InlineKeyboardButton(
                "🏏 CRICKET",
                callback_data="cricket"
            ),
            InlineKeyboardButton(
                "🎲 LUDO",
                callback_data="ludo"
            ),
        ],
        [
            InlineKeyboardButton(
                "🏆 LEADERBOARDS",
                callback_data="leaderboards"
            )
        ],
    ])


# ============================================================
# UNO MENU
# ============================================================

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


# ============================================================
# UNO DECK
# ============================================================

def create_uno_deck():

    deck = []

    colors = [
        "🔴 Red",
        "🟡 Yellow",
        "🟢 Green",
        "🔵 Blue",
    ]

    # Number cards
    for color in colors:

        # One zero
        deck.append({
            "color": color,
            "value": "0",
        })

        # One 1-9
        for number in range(1, 10):

            deck.append({
                "color": color,
                "value": str(number),
            })

            deck.append({
                "color": color,
                "value": str(number),
            })

        # Action cards - two each
        for action in ["Skip", "Reverse", "Draw Two"]:

            deck.append({
                "color": color,
                "value": action,
            })

            deck.append({
                "color": color,
                "value": action,
            })

    # Wild cards
    for _ in range(4):

        deck.append({
            "color": "🌈 Wild",
            "value": "Wild",
        })

    # Wild Draw Four
    for _ in range(4):

        deck.append({
            "color": "🌈 Wild",
            "value": "Wild Draw Four",
        })

    random.shuffle(deck)

    return deck


# ============================================================
# CARD DISPLAY
# ============================================================

def card_text(card):

    return (
        f"{card['color']} "
        f"**{card['value']}**"
    )


def hand_text(hand):

    if not hand:
        return "🖐️ Your hand is empty."

    lines = []

    for index, card in enumerate(hand, 1):

        lines.append(
            f"{index}. {card['color']} — "
            f"<b>{card['value']}</b>"
        )

    return "\n".join(lines)


# ============================================================
# GET / CREATE GAME
# ============================================================

def get_game(chat_id):

    if chat_id not in uno_games:

        uno_games[chat_id] = {
            "players": {},
            "player_order": [],
            "active": False,
            "deck": [],
            "discard": [],
            "hands": {},
            "turn_index": 0,
            "direction": 1,
            "timer_task": None,
        }

    return uno_games[chat_id]


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🎮 <b>Welcome to CC Gaming!</b> 🔥\n\n"
        "🃏 UNO • 🔤 Word • 🏏 Cricket • 🎲 Ludo\n\n"
        "<b>Choose your game & let's play! 🚀</b>"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ============================================================
# MENU
# ============================================================

async def menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🎮 <b>CC GAMING MENU</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ============================================================
# UNO COMMAND
# ============================================================

async def uno_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    game = get_game(chat_id)

    if game["active"]:

        await update.message.reply_text(
            "🃏 An UNO match is already running!"
        )

        return

    players = game["players"]

    player_list = "No players joined yet."

    if players:

        player_list = "\n".join(
            f"{i}. {name}"
            for i, name in enumerate(
                players.values(),
                1
            )
        )

    text = (
        "🃏 <b>UNO LOBBY</b>\n\n"
        f"👥 Players: <b>{len(players)}</b>\n"
        f"⏱️ Joining Time: <b>{UNO_JOIN_TIME} seconds</b>\n\n"
        f"{player_list}\n\n"
        "👇 Join the game!"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )

    if game["timer_task"] is None:

        game["timer_task"] = asyncio.create_task(
            uno_lobby_timer(
                context,
                chat_id
            )
        )


# ============================================================
# JOIN UNO
# ============================================================

async def join_uno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game(chat_id)

    if game["active"]:

        await update.message.reply_text(
            "❌ UNO match already started!"
        )

        return

    if user.id in game["players"]:

        await update.message.reply_text(
            "⚠️ You already joined UNO!"
        )

        return

    game["players"][user.id] = user.full_name

    game["player_order"].append(user.id)

    await update.message.reply_text(
        f"🃏 <b>{user.full_name}</b> joined UNO! 🔥\n\n"
        f"👥 Players: <b>{len(game['players'])}</b>",
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


# ============================================================
# LEAVE UNO
# ============================================================

async def leave_uno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game(chat_id)

    if user.id not in game["players"]:

        await update.message.reply_text(
            "❌ You are not in the UNO lobby."
        )

        return

    del game["players"][user.id]

    if user.id in game["player_order"]:

        game["player_order"].remove(user.id)

    await update.message.reply_text(
        f"🚪 <b>{user.full_name}</b> left UNO.",
        parse_mode="HTML",
    )


# ============================================================
# FORCE START
# ============================================================

async def force_uno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    game = get_game(chat_id)

    if game["active"]:

        await update.message.reply_text(
            "❌ UNO match already running!"
        )

        return

    if len(game["players"]) < UNO_MIN_PLAYERS:

        await update.message.reply_text(
            "❌ <b>Minimum 2 players required!</b>",
            parse_mode="HTML",
        )

        return

    await start_uno_game(
        context,
        chat_id
    )


# ============================================================
# LOBBY TIMER
# ============================================================

async def uno_lobby_timer(
    context,
    chat_id
):

    await asyncio.sleep(
        UNO_JOIN_TIME
    )

    game = uno_games.get(chat_id)

    if not game:
        return

    game["timer_task"] = None

    if game["active"]:
        return

    if len(game["players"]) >= UNO_MIN_PLAYERS:

        await start_uno_game(
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


# ============================================================
# START REAL UNO GAME
# ============================================================

async def start_uno_game(
    context,
    chat_id
):

    game = get_game(chat_id)

    if game["active"]:
        return

    if len(game["players"]) < UNO_MIN_PLAYERS:
        return

    game["active"] = True

    # Create deck
    game["deck"] = create_uno_deck()

    game["discard"] = []

    game["hands"] = {}

    game["turn_index"] = 0

    game["direction"] = 1

    # Deal 7 cards to every player
    for player_id in game["player_order"]:

        game["hands"][player_id] = []

        for _ in range(7):

            card = game["deck"].pop()

            game["hands"][player_id].append(
                card
            )

    # First discard card
    while True:

        first_card = game["deck"].pop()

        # Keep first card simple for Phase 2
        if first_card["value"].isdigit():

            game["discard"].append(
                first_card
            )

            break

        else:

            game["deck"].insert(
                0,
                first_card
            )

            random.shuffle(
                game["deck"]
            )

    # Announce game
    player_lines = []

    for index, player_id in enumerate(
        game["player_order"],
        1
    ):

        name = game["players"][player_id]

        player_lines.append(
            f"{index}. {name} — 🎴 7 cards"
        )

    text = (
        "🔥 <b>UNO MATCH STARTED!</b> 🔥\n\n"
        + "\n".join(player_lines)
        + "\n\n"
        "🃏 Each player received 7 cards.\n"
        "🔐 Your cards are private.\n\n"
        "🎯 First turn:"
    )

    await context.bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
    )

    # Send private cards
    for player_id in game["player_order"]:

        try:

            await send_private_hand(
                context,
                chat_id,
                player_id
            )

        except Exception:

            await context.bot.send_message(
                chat_id,
                f"⚠️ <b>{game['players'][player_id]}</b> "
                "please open the bot in private chat "
                "and press /start so I can send your cards.",
                parse_mode="HTML",
            )

    await announce_turn(
        context,
        chat_id
    )


# ============================================================
# SEND PRIVATE HAND
# ============================================================

async def send_private_hand(
    context,
    chat_id,
    player_id
):

    game = get_game(chat_id)

    hand = game["hands"][player_id]

    text = (
        "🃏 <b>YOUR UNO HAND</b>\n\n"
        f"{hand_text(hand)}\n\n"
        "🔐 Only you can see these cards."
    )

    await context.bot.send_message(
        player_id,
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔄 REFRESH HAND",
                    callback_data=f"uno_hand:{chat_id}"
                )
            ]
        ]),
    )


# ============================================================
# ANNOUNCE TURN
# ============================================================

async def announce_turn(
    context,
    chat_id
):

    game = get_game(chat_id)

    if not game["active"]:
        return

    player_id = game["player_order"][
        game["turn_index"]
    ]

    player_name = game["players"][
        player_id
    ]

    top_card = game["discard"][-1]

    await context.bot.send_message(
        chat_id,
        "🎯 <b>UNO TURN</b>\n\n"
        f"🏏 Current Player: <b>{player_name}</b>\n"
        f"🃏 Top Card: "
        f"{top_card['color']} "
        f"<b>{top_card['value']}</b>\n\n"
        "🔐 Check your private cards.",
        parse_mode="HTML",
    )


# ============================================================
# PRIVATE HAND BUTTON
# ============================================================

async def refresh_hand(
    query,
    context,
    chat_id
):

    player_id = query.from_user.id

    game = uno_games.get(
        chat_id
    )

    if not game or not game["active"]:

        await query.answer(
            "No active UNO game.",
            show_alert=True
        )

        return

    if player_id not in game["hands"]:

        await query.answer(
            "You are not part of this game.",
            show_alert=True
        )

        return

    hand = game["hands"][player_id]

    await query.answer(
        "🔄 Hand refreshed!"
    )

    await query.edit_message_text(
        "🃏 <b>YOUR UNO HAND</b>\n\n"
        f"{hand_text(hand)}\n\n"
        "🔐 Private hand",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔄 REFRESH HAND",
                    callback_data=f"uno_hand:{chat_id}"
                )
            ]
        ]),
    )


# ============================================================
# BUTTON HANDLER
# ============================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    data = query.data

    await query.answer()

    # -------------------------
    # MAIN UNO
    # -------------------------

    if data == "uno":

        await query.edit_message_text(
            "🃏 <b>UNO</b>\n\n"
            "Start a new UNO lobby:",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

        return

    # -------------------------
    # JOIN
    # -------------------------

    if data == "uno_join":

        chat_id = query.message.chat.id
        user = query.from_user

        game = get_game(chat_id)

        if game["active"]:

            await query.answer(
                "Match already started!",
                show_alert=True
            )

            return

        if user.id in game["players"]:

            await query.answer(
                "You already joined!",
                show_alert=True
            )

            return

        game["players"][
            user.id
        ] = user.full_name

        game["player_order"].append(
            user.id
        )

        await query.answer(
            "🃏 Joined UNO!"
        )

        await query.edit_message_text(
            "🃏 <b>UNO LOBBY</b>\n\n"
            f"👥 Players: <b>{len(game['players'])}</b>\n\n"
            + "\n".join(
                f"{i}. {name}"
                for i, name in enumerate(
                    game["players"].values(),
                    1
                )
            )
            + "\n\n👇 Join the game!",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

        return

    # -------------------------
    # LEAVE
    # -------------------------

    if data == "uno_leave":

        chat_id = query.message.chat.id
        user = query.from_user

        game = get_game(chat_id)

        if user.id not in game["players"]:

            await query.answer(
                "You are not in the lobby!",
                show_alert=True
            )

            return

        del game["players"][user.id]

        game["player_order"].remove(
            user.id
        )

        await query.answer(
            "🚪 You left UNO."
        )

        await query.edit_message_text(
            "🃏 <b>UNO LOBBY</b>\n\n"
            f"👥 Players: <b>{len(game['players'])}</b>\n\n"
            "👇 Join the game!",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

        return

    # -------------------------
    # FORCE START
    # -------------------------

    if data == "uno_force":

        chat_id = query.message.chat.id

        game = get_game(chat_id)

        if len(game["players"]) < UNO_MIN_PLAYERS:

            await query.answer(
                "❌ Minimum 2 players required!",
                show_alert=True
            )

            return

        await query.answer(
            "⚡ Starting UNO!"
        )

        await start_uno_game(
            context,
            chat_id
        )

        return

    # -------------------------
    # PRIVATE HAND
    # -------------------------

    if data.startswith("uno_hand:"):

        chat_id = int(
            data.split(":")[1]
        )

        await refresh_hand(
            query,
            context,
            chat_id
        )

        return

    # -------------------------
    # CRICKET
    # -------------------------

    if data == "cricket":

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

        return

    # -------------------------
    # LUDO
    # -------------------------

    if data == "ludo":

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

        return

    # -------------------------
    # LEADERBOARD
    # -------------------------

    if data == "leaderboards":

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

        return

    # -------------------------
    # HOME
    # -------------------------

    if data == "home":

        await query.edit_message_text(
            "🎮 <b>CC GAMING MENU</b>",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )

        return


# ============================================================
# MAIN
# ============================================================

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

    print(
        "🤖 CC Gaming Bot Started!"
    )

    app.run_polling()


if __name__ == "__main__":
    main() hi
