import os
import random
import asyncio
import logging
from html import escape

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
UNO_MAX_PLAYERS = 10


# ============================================================
# STORAGE
# ============================================================

uno_games = {}


# ============================================================
# MAIN MENU
# ============================================================

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


# ============================================================
# UNO LOBBY MENU
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
# CREATE UNO DECK
# ============================================================

def create_uno_deck():

    deck = []

    colors = [
        "Red",
        "Yellow",
        "Green",
        "Blue",
    ]

    for color in colors:

        # One zero
        deck.append({
            "color": color,
            "value": "0",
        })

        # Two of every 1-9
        for number in range(1, 10):

            for _ in range(2):

                deck.append({
                    "color": color,
                    "value": str(number),
                })

        # Two Skip
        for _ in range(2):

            deck.append({
                "color": color,
                "value": "Skip",
            })

        # Two Reverse
        for _ in range(2):

            deck.append({
                "color": color,
                "value": "Reverse",
            })

        # Two Draw Two
        for _ in range(2):

            deck.append({
                "color": color,
                "value": "Draw Two",
            })

    # 4 Wild
    for _ in range(4):

        deck.append({
            "color": "Wild",
            "value": "Wild",
        })

    # 4 Wild Draw Four
    for _ in range(4):

        deck.append({
            "color": "Wild",
            "value": "Wild Draw Four",
        })

    random.shuffle(deck)

    return deck


# ============================================================
# CARD EMOJI
# ============================================================

def color_emoji(color):

    return {
        "Red": "🔴",
        "Yellow": "🟡",
        "Green": "🟢",
        "Blue": "🔵",
        "Wild": "🌈",
    }.get(color, "🃏")


def card_name(card):

    return (
        f"{color_emoji(card['color'])} "
        f"{card['color']} {card['value']}"
    )


# ============================================================
# GAME CREATION
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
            "current_color": None,
            "draw_penalty": 0,
            "uno_pending": None,
            "lobby_task": None,
            "pending_wild": None,
        }

    return uno_games[chat_id]


# ============================================================
# START
# ============================================================

async def start(update, context):

    text = (
        "🎮 <b>Welcome to CC Gaming!</b> 🔥\n\n"
        "🃏 UNO • 🔤 Word • 🏏 Cricket • 🎲 Ludo\n\n"
        "Choose your game & let's play! 🚀"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ============================================================
# MENU
# ============================================================

async def menu(update, context):

    await update.message.reply_text(
        "🎮 <b>CC GAMING MENU</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ============================================================
# UNO COMMAND
# ============================================================

async def uno_command(update, context):

    chat_id = update.effective_chat.id
    game = get_game(chat_id)

    if game["active"]:

        await update.message.reply_text(
            "🃏 <b>UNO match already running!</b>",
            parse_mode="HTML",
        )
        return

    players = game["players"]

    if players:

        player_text = "\n".join(
            f"{i}. {escape(name)}"
            for i, name in enumerate(
                players.values(),
                1
            )
        )

    else:

        player_text = "No players joined yet."

    text = (
        "🃏 <b>UNO LOBBY</b>\n\n"
        f"👥 Players: <b>{len(players)}</b>\n"
        f"⏱️ Joining Time: <b>{UNO_JOIN_TIME} seconds</b>\n\n"
        f"{player_text}\n\n"
        "👇 Join the game!"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )

    if game["lobby_task"] is None:

        game["lobby_task"] = asyncio.create_task(
            lobby_timer(context, chat_id)
        )


# ============================================================
# JOIN
# ============================================================

async def join_uno(update, context):

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

    if len(game["players"]) >= UNO_MAX_PLAYERS:

        await update.message.reply_text(
            "❌ UNO lobby is full!"
        )
        return

    game["players"][user.id] = user.full_name
    game["player_order"].append(user.id)

    await update.message.reply_text(
        f"🃏 <b>{escape(user.full_name)}</b> joined UNO! 🔥\n\n"
        f"👥 Players: <b>{len(game['players'])}</b>",
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


# ============================================================
# LEAVE
# ============================================================

async def leave_uno(update, context):

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
        f"🚪 <b>{escape(user.full_name)}</b> left UNO.",
        parse_mode="HTML",
    )


# ============================================================
# FORCE START
# ============================================================

async def force_uno(update, context):

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

async def lobby_timer(context, chat_id):

    await asyncio.sleep(UNO_JOIN_TIME)

    game = uno_games.get(chat_id)

    if not game:
        return

    game["lobby_task"] = None

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
# DEAL CARDS
# ============================================================

def deal_cards(game):

    game["deck"] = create_uno_deck()
    game["hands"] = {}

    for player_id in game["player_order"]:

        game["hands"][player_id] = []

        for _ in range(7):

            game["hands"][player_id].append(
                game["deck"].pop()
            )


# ============================================================
# START GAME
# ============================================================

async def start_uno_game(context, chat_id):

    game = get_game(chat_id)

    if game["active"]:
        return

    if len(game["players"]) < UNO_MIN_PLAYERS:
        return

    game["active"] = True
    game["turn_index"] = 0
    game["direction"] = 1
    game["draw_penalty"] = 0
    game["uno_pending"] = None
    game["pending_wild"] = None

    deal_cards(game)

    # First card
    while True:

        first = game["deck"].pop()

        if first["value"] not in [
            "Wild",
            "Wild Draw Four",
            "Draw Two",
            "Skip",
            "Reverse",
        ]:

            game["discard"] = [first]
            game["current_color"] = first["color"]
            break

        game["deck"].insert(
            0,
            first
        )

        random.shuffle(game["deck"])

    players_text = []

    for index, player_id in enumerate(
        game["player_order"],
        1
    ):

        players_text.append(
            f"{index}. "
            f"{escape(game['players'][player_id])}"
            f" — 🎴 7 cards"
        )

    await context.bot.send_message(
        chat_id,
        "🔥 <b>UNO MATCH STARTED!</b> 🔥\n\n"
        + "\n".join(players_text)
        + "\n\n"
        "🎴 Each player received 7 cards.\n"
        "🔐 Cards are private.\n\n"
        "🚀 LET THE GAME BEGIN!",
        parse_mode="HTML",
    )

    # Send private hands
    for player_id in game["player_order"]:

        try:

            await send_hand(
                context,
                chat_id,
                player_id,
            )

        except Exception:

            await context.bot.send_message(
                chat_id,
                f"⚠️ <b>{escape(game['players'][player_id])}</b>\n"
                "Open CC Game Arena bot in private chat "
                "and press /start.",
                parse_mode="HTML",
            )

    await announce_turn(
        context,
        chat_id
    )


# ============================================================
# PLAYABLE CHECK
# ============================================================

def is_playable(card, game):

    top = game["discard"][-1]
    current_color = game["current_color"]

    # Wild
    if card["color"] == "Wild":
        return True

    # Same colour
    if card["color"] == current_color:
        return True

    # Same value
    if card["value"] == top["value"]:
        return True

    return False


# ============================================================
# RECYCLE DISCARD
# ============================================================

def recycle_deck(game):

    if len(game["deck"]) > 0:
        return

    if len(game["discard"]) <= 1:
        return

    top = game["discard"][-1]

    old_cards = game["discard"][:-1]

    game["discard"] = [top]

    random.shuffle(old_cards)

    game["deck"] = old_cards


# ============================================================
# CURRENT PLAYER
# ============================================================

def current_player(game):

    if not game["player_order"]:
        return None

    return game["player_order"][
        game["turn_index"]
    ]


# ============================================================
# MOVE TURN
# ============================================================

def move_turn(game, steps=1):

    if not game["player_order"]:
        return

    total = len(game["player_order"])

    game["turn_index"] = (
        game["turn_index"]
        + (game["direction"] * steps)
    ) % total


# ============================================================
# ANNOUNCE TURN
# ============================================================

async def announce_turn(context, chat_id):

    game = get_game(chat_id)

    if not game["active"]:
        return

    player_id = current_player(game)

    if player_id is None:
        return

    name = game["players"][player_id]
    top = game["discard"][-1]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🃏 MY CARDS",
                callback_data=f"myhand:{chat_id}"
            )
        ]
    ])

    await context.bot.send_message(
        chat_id,
        "🎯 <b>UNO TURN</b>\n\n"
        f"🏏 Current Player: <b>{escape(name)}</b>\n\n"
        f"🃏 Top Card: <b>{card_name(top)}</b>\n"
        f"🎨 Current Colour: "
        f"<b>{color_emoji(game['current_color'])} "
        f"{game['current_color']}</b>\n\n"
        "🔐 Check your private cards.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ============================================================
# SEND PRIVATE HAND
# ============================================================

async def send_hand(context, chat_id, player_id):

    game = get_game(chat_id)

    if player_id not in game["hands"]:
        return

    hand = game["hands"][player_id]

    current_id = current_player(game)

    buttons = []

    for index, card in enumerate(hand):

        playable = (
            player_id == current_id
            and is_playable(card, game)
        )

        label = (
            f"▶️ {color_emoji(card['color'])} "
            f"{card['value']}"
            if playable
            else
            f"{color_emoji(card['color'])} "
            f"{card['value']}"
        )

        buttons.append(
            InlineKeyboardButton(
                label,
                callback_data=(
                    f"play:{chat_id}:{index}"
                )
            )
        )

    rows = []

    for i in range(0, len(buttons), 2):

        rows.append(
            buttons[i:i + 2]
        )

    rows.append([
        InlineKeyboardButton(
            "🎴 DRAW CARD",
            callback_data=f"draw:{chat_id}"
        )
    ])

    if len(hand) == 1:

        rows.append([
            InlineKeyboardButton(
                "📢 UNO!",
                callback_data=f"uno_call:{chat_id}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "🔄 REFRESH",
            callback_data=f"myhand:{chat_id}"
        )
    ])

    text = (
        "🃏 <b>YOUR UNO HAND</b>\n\n"
        f"🎴 Cards: <b>{len(hand)}</b>\n\n"
        "Tap a card to play it.\n"
        "🎴 Draw if you don't have a playable card."
    )

    await context.bot.send_message(
        player_id,
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# ============================================================
# SHOW HAND
# ============================================================

async def show_hand(query, context, chat_id):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:

        await query.answer(
            "❌ No active UNO game.",
            show_alert=True
        )
        return

    if player_id not in game["hands"]:

        await query.answer(
            "❌ You are not in this game.",
            show_alert=True
        )
        return

    hand = game["hands"][player_id]

    current_id = current_player(game)

    buttons = []

    for index, card in enumerate(hand):

        playable = (
            player_id == current_id
            and is_playable(card, game)
        )

        label = (
            f"▶️ {color_emoji(card['color'])} {card['value']}"
            if playable
            else
            f"{color_emoji(card['color'])} {card['value']}"
        )

        buttons.append(
            InlineKeyboardButton(
                label,
                callback_data=f"play:{chat_id}:{index}"
            )
        )

    rows = []

    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])

    rows.append([
        InlineKeyboardButton(
            "🎴 DRAW CARD",
            callback_data=f"draw:{chat_id}"
        )
    ])

    if len(hand) == 1:

        rows.append([
            InlineKeyboardButton(
                "📢 UNO!",
                callback_data=f"uno_call:{chat_id}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "🔄 REFRESH",
            callback_data=f"myhand:{chat_id}"
        )
    ])

    await query.edit_message_text(
        "🃏 <b>YOUR UNO HAND</b>\n\n"
        f"🎴 Cards: <b>{len(hand)}</b>\n\n"
        "▶️ = playable card",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# ============================================================
# DRAW CARD
# ============================================================

async def draw_card(query, context, chat_id):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:
        return

    if player_id != current_player(game):

        await query.answer(
            "⏳ Not your turn!",
            show_alert=True
        )
        return

    recycle_deck(game)

    if not game["deck"]:

        await query.answer(
            "❌ No cards available!",
            show_alert=True
        )
        return

    card = game["deck"].pop()

    game["hands"][player_id].append(card)

    await query.answer(
        f"🎴 Drew {card['value']}"
    )

    await context.bot.send_message(
        chat_id,
        f"🎴 <b>{escape(game['players'][player_id])}</b> "
        "drew a card.",
        parse_mode="HTML",
    )

    # For this phase, drawing ends turn
    move_turn(game)

    await send_hand(
        context,
        chat_id,
        player_id
    )

    await announce_turn(
        context,
        chat_id
    )


# ============================================================
# PLAY CARD
# ============================================================

async def play_card(query, context, chat_id, index):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:

        await query.answer(
            "❌ No active UNO game.",
            show_alert=True
        )
        return

    if player_id != current_player(game):

        await query.answer(
            "⏳ It's not your turn!",
            show_alert=True
        )
        return

    hand = game["hands"][player_id]

    if index < 0 or index >= len(hand):

        await query.answer(
            "❌ Invalid card.",
            show_alert=True
        )
        return

    card = hand[index]

    if not is_playable(card, game):

        await query.answer(
            "❌ You cannot play this card!",
            show_alert=True
        )
        return

    # Remove card
    hand.pop(index)

    game["discard"].append(card)

    game["uno_pending"] = None

    # Wild needs colour selection
    if card["color"] == "Wild":

        game["pending_wild"] = player_id

        await query.answer(
            "🌈 Choose a colour!"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔴 RED",
                    callback_data=f"color:{chat_id}:Red"
                ),
                InlineKeyboardButton(
                    "🟡 YELLOW",
                    callback_data=f"color:{chat_id}:Yellow"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🟢 GREEN",
                    callback_data=f"color:{chat_id}:Green"
                ),
                InlineKeyboardButton(
                    "🔵 BLUE",
                    callback_data=f"color:{chat_id}:Blue"
                ),
            ],
        ])

        await query.message.reply_text(
            "🌈 <b>Choose the new colour</b>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        return

    # Normal card
    game["current_color"] = card["color"]

    await query.answer(
        f"▶️ Played {card['value']}"
    )

    await resolve_card(
        context,
        chat_id,
        player_id,
        card
    )


# ============================================================
# RESOLVE CARD
# ============================================================

async def resolve_card(
    context,
    chat_id,
    player_id,
    card
):

    game = get_game(chat_id)

    player_name = game["players"][player_id]

    await context.bot.send_message(
        chat_id,
        f"🃏 <b>{escape(player_name)}</b> played "
        f"<b>{card_name(card)}</b>",
        parse_mode="HTML",
    )

    # WIN
    if len(game["hands"][player_id]) == 0:

        await finish_game(
            context,
            chat_id,
            player_id
        )
        return

    # UNO
    if len(game["hands"][player_id]) == 1:

        game["uno_pending"] = player_id

        await context.bot.send_message(
            chat_id,
            f"🚨 <b>{escape(player_name)}</b> has ONE CARD!\n\n"
            "📢 Press <b>UNO!</b> now!",
            parse_mode="HTML",
        )

    # Special card
    value = card["value"]

    if value == "Skip":

        move_turn(game, 2)

    elif value == "Reverse":

        if len(game["player_order"]) == 2:

            move_turn(game, 2)

        else:

            game["direction"] *= -1
            move_turn(game, 1)

    elif value == "Draw Two":

        next_player = get_next_player(
            game
        )

        recycle_deck(game)

        for _ in range(2):

            if game["deck"]:

                game["hands"][next_player].append(
                    game["deck"].pop()
                )

        await context.bot.send_message(
            chat_id,
            f"➕2 <b>{escape(game['players'][next_player])}</b> "
            "draws 2 cards!",
            parse_mode="HTML",
        )

        move_turn(game, 2)

    else:

        move_turn(game, 1)

    await send_hand(
        context,
        chat_id,
        player_id
    )

    await announce_turn(
        context,
        chat_id
    )


# ============================================================
# NEXT PLAYER
# ============================================================

def get_next_player(game):

    if not game["player_order"]:
        return None

    total = len(game["player_order"])

    next_index = (
        game["turn_index"]
        + game["direction"]
    ) % total

    return game["player_order"][next_index]


# ============================================================
# WILD COLOUR
# ============================================================

async def choose_color(query, context, chat_id, color):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:
        return

    if game["pending_wild"] != player_id:

        await query.answer(
            "❌ Colour selection is not yours!",
            show_alert=True
        )
        return

    game["current_color"] = color
    game["pending_wild"] = None

    last_card = game["discard"][-1]

    await query.answer(
        f"{color} selected!"
    )

    await query.edit_message_text(
        f"🌈 <b>Colour changed to "
        f"{color_emoji(color)} {color}</b>",
        parse_mode="HTML",
    )

    # Wild Draw Four
    if last_card["value"] == "Wild Draw Four":

        next_player = get_next_player(
            game
        )

        recycle_deck(game)

        for _ in range(4):

            if game["deck"]:

                game["hands"][next_player].append(
                    game["deck"].pop()
                )

        await context.bot.send_message(
            chat_id,
            f"🌈 <b>Wild +4!</b>\n"
            f"➕ <b>{escape(game['players'][next_player])}</b> "
            "draws 4 cards!",
            parse_mode="HTML",
        )

        move_turn(game, 2)

    else:

        move_turn(game, 1)

    await send_hand(
        context,
        chat_id,
        player_id
    )

    await announce_turn(
        context,
        chat_id
    )


# ============================================================
# UNO CALL
# ============================================================

async def call_uno(query, context, chat_id):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:
        return

    hand = game["hands"].get(player_id, [])

    if len(hand) != 1:

        await query.answer(
            "❌ UNO can only be called with 1 card!",
            show_alert=True
        )
        return

    if game["uno_pending"] != player_id:

        await query.answer(
            "⚠️ UNO already called or unavailable.",
            show_alert=True
        )
        return

    game["uno_pending"] = None

    await query.answer(
        "📢 UNO!"
    )

    await context.bot.send_message(
        chat_id,
        f"📢 <b>{escape(game['players'][player_id])} "
        "called UNO!</b> 🔥",
        parse_mode="HTML",
    )

    await send_hand(
        context,
        chat_id,
        player_id
    )


# ============================================================
# FINISH GAME
# ============================================================

async def finish_game(
    context,
    chat_id,
    winner_id
):

    game = get_game(chat_id)

    winner = game["players"][winner_id]

    game["active"] = False

    await context.bot.send_message(
        chat_id,
        "🏆🏆🏆 <b>UNO WINNER!</b> 🏆🏆🏆\n\n"
        f"👑 <b>{escape(winner)}</b>\n\n"
        "🎉 Congratulations!\n"
        "🔥 What a game!",
        parse_mode="HTML",
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def button_handler(update, context):

    query = update.callback_query

    data = query.data

    # --------------------------
    # UNO MENU
    # --------------------------

    if data == "uno":

        await query.answer()

        await query.edit_message_text(
            "🃏 <b>UNO</b>\n\n"
            "Start a new UNO lobby:",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

        return

    # --------------------------
    # JOIN
    # --------------------------

    if data == "uno_join":

        await query.answer()

        chat_id = query.message.chat.id
        user = query.from_user

        game = get_game(chat_id)

        if game["active"]:

            await query.answer(
                "❌ Match already started!",
                show_alert=True
            )
            return

        if user.id in game["players"]:

            await query.answer(
                "⚠️ Already joined!",
                show_alert=True
            )
            return

        if len(game["players"]) >= UNO_MAX_PLAYERS:

            await query.answer(
                "❌ Lobby full!",
                show_alert=True
            )
            return

        game["players"][user.id] = user.full_name
        game["player_order"].append(user.id)

        player_text = "\n".join(
            f"{i}. {escape(name)}"
            for i, name in enumerate(
                game["players"].values(),
                1
            )
        )

        await query.edit_message_text(
            "🃏 <b>UNO LOBBY</b>\n\n"
            f"👥 Players: <b>{len(game['players'])}</b>\n"
            f"⏱️ Joining Time: <b>{UNO_JOIN_TIME} seconds</b>\n\n"
            f"{player_text}\n\n"
            "👇 Join the game!",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

        return

    # --------------------------
    # LEAVE
    # --------------------------

    if data == "uno_leave":

        await query.answer()

        chat_id = query.message.chat.id
        user = query.from_user

        game = get_game(chat_id)

        if user.id not in game["players"]:

            await query.answer(
                "❌ You are not in lobby.",
                show_alert=True
            )
            return

        del game["players"][user.id]

        if user.id in game["player_order"]:
            game["player_order"].remove(user.id)

        await query.edit_message_text(
            "🃏 <b>UNO LOBBY</b>\n\n"
            f"👥 Players: {len(game['players'])}\n\n"
            "👇 Join the game!",
            parse_mode="HTML",
            reply_markup=uno_menu(),
        )

        return

    # --------------------------
    # FORCE START
    # --------------------------

    if data == "uno_force":

        await query.answer()

        chat_id = query.message.chat.id

        game = get_game(chat_id)

        if len(game["players"]) < UNO_MIN_PLAYERS:

            await query.answer(
                "❌ Minimum 2 players required!",
                show_alert=True
            )
            return

        await start_uno_game(
            context,
            chat_id
        )

        return

    # --------------------------
    # MY HAND
    # --------------------------

    if data.startswith("myhand:"):

        await query.answer()

        chat_id = int(
            data.split(":")[1]
        )

        await show_hand(
            query,
            context,
            chat_id
        )

        return

    # --------------------------
    # DRAW
    # --------------------------

    if data.startswith("draw:"):

        chat_id = int(
            data.split(":")[1]
        )

        await draw_card(
            query,
            context,
            chat_id
        )

        return

    # --------------------------
    # PLAY
    # --------------------------

    if data.startswith("play:"):

        parts = data.split(":")

        chat_id = int(parts[1])
        index = int(parts[2])

        await play_card(
            query,
            context,
            chat_id,
            index
        )

        return

    # --------------------------
    # COLOR
    # --------------------------

    if data.startswith("color:"):

        parts = data.split(":")

        chat_id = int(parts[1])
        color = parts[2]

        await choose_color(
            query,
            context,
            chat_id,
            color
        )

        return

    # --------------------------
    # UNO CALL
    # --------------------------

    if data.startswith("uno_call:"):

        chat_id = int(
            data.split(":")[1]
        )

        await call_uno(
            query,
            context,
            chat_id
        )

        return

    # --------------------------
    # CRICKET
    # --------------------------

    if data == "cricket":

        await query.answer()

        await query.edit_message_text(
            "🏏 <b>CRICKET</b>\n\n"
            "Cricket module coming next! 🔥",
            parse_mode="HTML",
        )

        return

    # --------------------------
    # LUDO
    # --------------------------

    if data == "ludo":

        await query.answer()

        await query.edit_message_text(
            "🎲 <b>LUDO</b>\n\n"
            "Ludo module coming next! 🔥",
            parse_mode="HTML",
        )

        return

    # --------------------------
    # WORD
    # --------------------------

    if data == "word":

        await query.answer()

        await query.edit_message_text(
            "🔤 <b>WORD GAME</b>\n\n"
            "Word module coming next! 🔥",
            parse_mode="HTML",
        )

        return

    # --------------------------
    # LEADERBOARD
    # --------------------------

    if data == "leaderboards":

        await query.answer()

        await query.edit_message_text(
            "🏆 <b>LEADERBOARDS</b>\n\n"
            "🃏 UNO\n"
            "🔤 WORD\n"
            "🏏 CRICKET\n"
            "🎲 LUDO",
            parse_mode="HTML",
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

    print("🤖 CC Game Arena Bot Started!")

    app.run_polling()


if __name__ == "__main__":
    main()              
