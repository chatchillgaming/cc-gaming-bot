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

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ============================================================
# BOT TOKEN
# ============================================================

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
# GET GAME
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
            "uno_pending": None,
            "pending_wild": None,
            "lobby_task": None,
        }

    return uno_games[chat_id]


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


# ============================================================
# CARD NAME
# ============================================================

def card_name(card):

    return (
        f"{color_emoji(card['color'])} "
        f"{card['color']} {card['value']}"
    )


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

        # Zero
        deck.append({
            "color": color,
            "value": "0",
        })

        # 1 - 9
        for number in range(1, 10):

            for _ in range(2):

                deck.append({
                    "color": color,
                    "value": str(number),
                })

        # Skip
        for _ in range(2):

            deck.append({
                "color": color,
                "value": "Skip",
            })

        # Reverse
        for _ in range(2):

            deck.append({
                "color": color,
                "value": "Reverse",
            })

        # Draw Two
        for _ in range(2):

            deck.append({
                "color": color,
                "value": "Draw Two",
            })

    # Wild
    for _ in range(4):

        deck.append({
            "color": "Wild",
            "value": "Wild",
        })

    # Wild Draw Four
    for _ in range(4):

        deck.append({
            "color": "Wild",
            "value": "Wild Draw Four",
        })

    random.shuffle(deck)

    return deck


# ============================================================
# START COMMAND
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Private welcome is allowed for bot start,
    # but UNO itself is group-only.

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
# MENU COMMAND
# ============================================================

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

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

    # UNO GROUP ONLY
    if update.effective_chat.type not in [
        "group",
        "supergroup"
    ]:

        await update.message.reply_text(
            "❌ UNO can be played only in the group chat."
        )

        return

    chat_id = update.effective_chat.id

    game = get_game(chat_id)

    # Already running
    if game["active"]:

        await update.message.reply_text(
            "🔥 <b>UNO match already running!</b>\n\n"
            "❌ You cannot start another UNO match "
            "until this match ends.",
            parse_mode="HTML",
        )

        return

    player_list = get_player_list(game)

    await update.message.reply_text(
        "🎮 <b>UNO LOBBY</b>\n\n"
        f"👥 Players: <b>{len(game['players'])}</b>\n"
        f"⏱️ Joining Time: <b>{UNO_JOIN_TIME} seconds</b>\n\n"
        f"{player_list}\n\n"
        "👇 <b>Join below</b>",
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )

    # Start lobby timer only once
    if game["lobby_task"] is None:

        game["lobby_task"] = asyncio.create_task(
            lobby_timer(
                context,
                chat_id
            )
        )


# ============================================================
# PLAYER LIST
# ============================================================

def get_player_list(game):

    if not game["player_order"]:

        return "No players joined yet."

    lines = []

    for i, user_id in enumerate(
        game["player_order"],
        1
    ):

        name = game["players"].get(
            user_id,
            "Unknown"
        )

        lines.append(
            f"{i}. {escape(name)}"
        )

    return "\n".join(lines)


# ============================================================
# JOIN UNO COMMAND
# ============================================================

async def join_uno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # GROUP ONLY
    if update.effective_chat.type not in [
        "group",
        "supergroup"
    ]:

        await update.message.reply_text(
            "❌ UNO is available only in the group chat."
        )

        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game(chat_id)

    # Match active
    if game["active"]:

        await update.message.reply_text(
            "🔥 UNO match already started!"
        )

        return

    # Already joined
    if user.id in game["players"]:

        await update.message.reply_text(
            "⚠️ You already joined UNO!"
        )

        return

    # Lobby full
    if len(game["players"]) >= UNO_MAX_PLAYERS:

        await update.message.reply_text(
            "❌ UNO lobby is full!"
        )

        return

    # Add player
    game["players"][user.id] = user.full_name

    if user.id not in game["player_order"]:

        game["player_order"].append(
            user.id
        )

    await update.message.reply_text(
        "🟢 <b>PLAYER JOINED UNO!</b>\n\n"
        f"👤 {escape(user.full_name)}\n"
        f"👥 Players: <b>{len(game['players'])}</b>\n\n"
        f"{get_player_list(game)}\n\n"
        "👇 Join the game!",
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


# ============================================================
# LEAVE UNO COMMAND
# ============================================================

async def leave_uno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_chat.type not in [
        "group",
        "supergroup"
    ]:

        await update.message.reply_text(
            "❌ UNO is group-only."
        )

        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = get_game(chat_id)

    if game["active"]:

        await update.message.reply_text(
            "❌ Match already started. "
            "You cannot leave now."
        )

        return

    if user.id not in game["players"]:

        await update.message.reply_text(
            "❌ You are not in the UNO lobby."
        )

        return

    del game["players"][user.id]

    if user.id in game["player_order"]:

        game["player_order"].remove(
            user.id
        )

    await update.message.reply_text(
        f"🚪 <b>{escape(user.full_name)}</b> "
        "left UNO.\n\n"
        f"👥 Players: <b>{len(game['players'])}</b>",
        parse_mode="HTML",
        reply_markup=uno_menu(),
    )


# ============================================================
# FORCE START
# ============================================================

async def force_uno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_chat.type not in [
        "group",
        "supergroup"
    ]:

        await update.message.reply_text(
            "❌ UNO is group-only."
        )

        return

    chat_id = update.effective_chat.id

    game = get_game(chat_id)

    if game["active"]:

        await update.message.reply_text(
            "🔥 UNO match already running!"
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

async def lobby_timer(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id
):

    try:

        await asyncio.sleep(
            UNO_JOIN_TIME
        )

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

            # Reset lobby
            game["players"] = {}
            game["player_order"] = []

    except asyncio.CancelledError:

        return


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
# START UNO GAME
# ============================================================

async def start_uno_game(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id
):

    game = get_game(chat_id)

    if game["active"]:
        return

    if len(game["players"]) < UNO_MIN_PLAYERS:
        return

    # Cancel lobby timer
    if game["lobby_task"]:

        game["lobby_task"].cancel()
        game["lobby_task"] = None

    game["active"] = True
    game["turn_index"] = 0
    game["direction"] = 1
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

        game["deck"].append(first)
        random.shuffle(game["deck"])

    # Player list
    players_text = []

    for index, player_id in enumerate(
        game["player_order"],
        1
    ):

        name = game["players"][player_id]

        players_text.append(
            f"{index}. {escape(name)} — 🎴 7 cards"
        )

    await context.bot.send_message(
        chat_id,
        "🔥 <b>UNO MATCH STARTED!</b> 🔥\n\n"
        + "\n".join(players_text)
        + "\n\n"
        "🎴 Each player received 7 cards.\n"
        "🔐 Cards are private.\n\n"
        "🚀 <b>LET THE GAME BEGIN!</b>",
        parse_mode="HTML",
    )

    # Send private cards
    for player_id in game["player_order"]:

        try:

            await send_hand(
                context,
                chat_id,
                player_id
            )

        except Exception as e:

            logging.warning(
                "Could not send private hand to %s: %s",
                player_id,
                e
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
# RECYCLE DECK
# ============================================================

def recycle_deck(game):

    if game["deck"]:
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
# MOVE TURN
# ============================================================

def move_turn(game, steps=1):

    if not game["player_order"]:
        return

    total = len(game["player_order"])

    game["turn_index"] = (
        game["turn_index"]
        + game["direction"] * steps
    ) % total


# ============================================================
# TURN MESSAGE
# ============================================================

async def announce_turn(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id
):

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
        f"👤 <b>Current Player:</b> "
        f"<a href=\"tg://user?id={player_id}\">"
        f"{escape(name)}</a>\n\n"
        f"🃏 <b>Top Card:</b> "
        f"{card_name(top)}\n\n"
        f"🎨 <b>Current Colour:</b> "
        f"{color_emoji(game['current_color'])} "
        f"{game['current_color']}\n\n"
        "👇 <b>It's your turn!</b>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ============================================================
# PRIVATE HAND
# ============================================================

async def send_hand(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id,
    player_id
):

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

        if playable:

            label = (
                f"▶️ {color_emoji(card['color'])} "
                f"{card['value']}"
            )

        else:

            label = (
                f"{color_emoji(card['color'])} "
                f"{card['value']}"
            )

        buttons.append(
            InlineKeyboardButton(
                label,
                callback_data=f"play:{chat_id}:{index}"
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
            "🔄 REFRESH HAND",
            callback_data=f"myhand:{chat_id}"
        )
    ])

    text = (
        "🃏 <b>YOUR UNO HAND</b>\n\n"
        f"🎴 Cards: <b>{len(hand)}</b>\n\n"
        "▶️ Playable card\n"
        "🎴 Draw a card if needed."
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

async def show_hand(
    query,
    context,
    chat_id
):

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
                callback_data=f"play:{chat_id}:{index}"
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
            "🔄 REFRESH HAND",
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
# DRAW
# ============================================================

async def draw_card(
    query,
    context,
    chat_id
):

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

    player_name = game["players"][player_id]

    await context.bot.send_message(
        chat_id,
        f"🎴 <b>{escape(player_name)}</b> drew a card.",
        parse_mode="HTML",
    )

    # Draw ends turn
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

async def play_card(
    query,
    context,
    chat_id,
    index
):

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

    hand = game["hands"].get(
        player_id,
        []
    )

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

    hand.pop(index)

    game["discard"].append(card)

    game["uno_pending"] = None

    await query.answer(
        f"▶️ Played {card['value']}"
    )

    # Wild
    if card["color"] == "Wild":

        game["pending_wild"] = player_id

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

        await context.bot.send_message(
            chat_id,
            f"🌈 <b>{escape(game['players'][player_id])}</b> "
            "played a Wild card.\n\n"
            "🎨 Choose a colour.",
            parse_mode="HTML",
        )

        try:

            await context.bot.send_message(
                player_id,
                "🌈 <b>Choose the new colour</b>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except Exception:

            await query.message.reply_text(
                "⚠️ Please choose the colour below:",
                reply_markup=keyboard
            )

        return

    game["current_color"] = card["color"]

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

    # ONE CARD
    if len(game["hands"][player_id]) == 1:

        game["uno_pending"] = player_id

        await context.bot.send_message(
            chat_id,
            f"🚨 <b>{escape(player_name)}</b> has ONE CARD!\n\n"
            "📢 Press <b>UNO!</b> in your private hand.",
            parse_mode="HTML",
        )

    value = card["value"]

    # SKIP
    if value == "Skip":

        move_turn(game, 2)

    # REVERSE
    elif value == "Reverse":

        if len(game["player_order"]) == 2:

            move_turn(game, 2)

        else:

            game["direction"] *= -1

            move_turn(game, 1)

    # DRAW TWO
    elif value == "Draw Two":

        next_player = get_next_player(game)

        recycle_deck(game)

        for _ in range(2):

            if game["deck"]:

                game["hands"][next_player].append(
                    game["deck"].pop()
                )

        await context.bot.send_message(
            chat_id,
            f"➕2 <b>"
            f"{escape(game['players'][next_player])}"
            f"</b> draws 2 cards!",
            parse_mode="HTML",
        )

        move_turn(game, 2)

    # NORMAL
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
# CHOOSE WILD COLOUR
# ============================================================

async def choose_color(
    query,
    context,
    chat_id,
    color
):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:

        await query.answer(
            "❌ No active game.",
            show_alert=True
        )

        return

    if game["pending_wild"] != player_id:

        await query.answer(
            "❌ This colour selection is not yours!",
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

    # WILD DRAW FOUR
    if last_card["value"] == "Wild Draw Four":

        next_player = get_next_player(game)

        recycle_deck(game)

        for _ in range(4):

            if game["deck"]:

                game["hands"][next_player].append(
                    game["deck"].pop()
                )

        await context.bot.send_message(
            chat_id,
            "🌈 <b>WILD DRAW FOUR!</b>\n\n"
            f"➕ <b>"
            f"{escape(game['players'][next_player])}"
            f"</b> draws 4 cards!",
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

async def call_uno(
    query,
    context,
    chat_id
):

    player_id = query.from_user.id

    game = uno_games.get(chat_id)

    if not game or not game["active"]:

        await query.answer(
            "❌ No active game.",
            show_alert=True
        )

        return

    hand = game["hands"].get(
        player_id,
        []
    )

    if len(hand) != 1:

        await query.answer(
            "❌ UNO can only be called with 1 card!",
            show_alert=True
        )

        return

    if game["uno_pending"] != player_id:

        await query.answer(
            "⚠️ UNO is not available now.",
            show_alert=True
        )

        return

    game["uno_pending"] = None

    await query.answer(
        "📢 UNO!"
    )

    await context.bot.send_message(
        chat_id,
        f"📢 <b>"
        f"{escape(game['players'][player_id])}"
        f"</b> called UNO! 🔥",
        parse_mode="HTML",
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

    # Reset game
    game["players"] = {}
    game["player_order"] = []
    game["hands"] = {}
    game["deck"] = []
    game["discard"] = []
    game["turn_index"] = 0
    game["direction"] = 1
    game["current_color"] = None
    game["uno_pending"] = None
    game["pending_wild"] = None
    game["lobby_task"] = None


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    data = query.data

    # ========================================================
    # UNO MENU
    # ========================================================

    if data == "uno":

        await query.answer()

        chat_id = query.message.chat.id

        # GROUP ONLY
        if query.message.chat.type not in [
            "group",
            "supergroup"
        ]:

            await query.edit_message_text(
                "❌ UNO can be played only in the group chat."
            )

            return

        game = get_game(chat_id)

        if game["active"]:

            await query.edit_message_text()
                "🔥 <b>UNO MATCH ACTIVE</b>\n\n"
                "❌ Another UNO match cannot be started "
                "until the current match ends.",
               
