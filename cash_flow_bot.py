"""
Cash Flow - Crypto Mining Simulation Bot
----------------------------------------
A simple Telegram bot built with python-telegram-bot (v20+).
All coins are VIRTUAL (simulation only) - no real money or crypto involved.

Install:   pip install "python-telegram-bot>=20.0"
Run:       python cash_flow_bot.py
"""

import json
import logging
import os
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
BOT_TOKEN = "8896579151:AAEirv3VOCw_XFLM9iIF2q6uFxjoSIZGfMk"

COIN = "CFC"                 # Name of the virtual coin
MINING_RATE_PER_HOUR = 0.5   # Coins earned per hour of mining
MAX_SESSION_HOURS = 4        # A session stops earning after this many hours
REFERRAL_BONUS = 5.0         # Coins given to both inviter and new user
DATA_FILE = "cashflow_data.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# SIMPLE JSON STORAGE (swap for a real database in production)
# --------------------------------------------------------------------------
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


DB = load_data()


def get_user(user_id: int) -> dict:
    """Return the user's record, creating it if needed."""
    uid = str(user_id)
    if uid not in DB:
        DB[uid] = {
            "balance": 0.0,
            "mining_start": None,   # Unix timestamp or None
            "referrals": 0,
            "notifications": True,
        }
        save_data(DB)
    return DB[uid]


# --------------------------------------------------------------------------
# MINING LOGIC
# --------------------------------------------------------------------------
def pending_coins(user: dict) -> float:
    """Coins earned in the current mining session so far."""
    if not user["mining_start"]:
        return 0.0
    hours = (time.time() - user["mining_start"]) / 3600
    hours = min(hours, MAX_SESSION_HOURS)
    return round(hours * MINING_RATE_PER_HOUR, 4)


def session_finished(user: dict) -> bool:
    if not user["mining_start"]:
        return False
    return (time.time() - user["mining_start"]) >= MAX_SESSION_HOURS * 3600


def time_left_text(user: dict) -> str:
    remaining = MAX_SESSION_HOURS * 3600 - (time.time() - user["mining_start"])
    remaining = max(0, int(remaining))
    h, m = remaining // 3600, (remaining % 3600) // 60
    return f"{h}h {m}m"


# --------------------------------------------------------------------------
# KEYBOARDS
# --------------------------------------------------------------------------
def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🚀 Start Mining", callback_data="mine")],
        [
            InlineKeyboardButton("💰 Balance", callback_data="balance"),
            InlineKeyboardButton("👥 Invite Friends", callback_data="invite"),
        ],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]])


# --------------------------------------------------------------------------
# MESSAGE TEXT BUILDERS
# --------------------------------------------------------------------------
WELCOME_TEXT = (
    "👋 Welcome to <b>Cash Flow</b>!\n\n"
    "⛏ <b>What is crypto mining?</b>\n"
    "Mining is how computers validate transactions on a blockchain and earn "
    "coins as a reward. In Cash Flow you simulate this: start a mining "
    f"session and earn <b>{COIN}</b> coins while your virtual rig works.\n\n"
    f"• Rate: <b>{MINING_RATE_PER_HOUR} {COIN}/hour</b>\n"
    f"• Each session lasts up to <b>{MAX_SESSION_HOURS} hours</b>\n"
    "• Invite friends to earn bonus coins\n\n"
    "Choose an option below 👇"
)


def balance_text(user: dict) -> str:
    text = (
        "💰 <b>Your Wallet</b>\n\n"
        f"Balance: <b>{user['balance']:.4f} {COIN}</b>\n"
        f"Friends invited: <b>{user['referrals']}</b>\n"
    )
    if user["mining_start"]:
        text += f"\n⛏ Mining in progress: <b>{pending_coins(user):.4f} {COIN}</b> pending"
    return text


# --------------------------------------------------------------------------
# COMMAND HANDLERS
# --------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start - welcome message, handles referral links like /start ref_123."""
    tg_user = update.effective_user
    is_new = str(tg_user.id) not in DB
    user = get_user(tg_user.id)

    # Referral handling (only for brand-new users, never self-referral)
    if is_new and context.args and context.args[0].startswith("ref_"):
        referrer_id = context.args[0][4:]
        if referrer_id.isdigit() and referrer_id != str(tg_user.id) and referrer_id in DB:
            DB[referrer_id]["balance"] += REFERRAL_BONUS
            DB[referrer_id]["referrals"] += 1
            user["balance"] += REFERRAL_BONUS
            save_data(DB)
            try:
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=f"🎉 A friend joined using your link! You earned {REFERRAL_BONUS} {COIN}.",
                )
            except Exception:  # Referrer may have blocked the bot
                pass

    await update.message.reply_text(
        WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=main_menu()
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/balance - show wallet."""
    user = get_user(update.effective_user.id)
    await update.message.reply_text(
        balance_text(user), parse_mode=ParseMode.HTML, reply_markup=main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help - list commands."""
    text = (
        "ℹ️ <b>Cash Flow Help</b>\n\n"
        "/start - Open the main menu\n"
        "/balance - Check your balance\n"
        "/help - Show this message\n\n"
        "Tap <b>🚀 Start Mining</b> to begin a session, then come back later "
        "to claim your coins.\n\n"
        "<i>Note: Cash Flow is a simulation. Coins are virtual.</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------
# BUTTON (CALLBACK) HANDLER
# --------------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Stop the loading spinner on the button

    user = get_user(query.from_user.id)
    action = query.data

    if action == "menu":
        await query.edit_message_text(
            WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )

    elif action == "mine":
        if not user["mining_start"]:
            # Start a new session
            user["mining_start"] = time.time()
            save_data(DB)
            text = (
                "🚀 <b>Mining started!</b>\n\n"
                f"Your rig is earning <b>{MINING_RATE_PER_HOUR} {COIN}/hour</b> "
                f"for the next {MAX_SESSION_HOURS} hours.\n"
                "Come back anytime to check progress or claim."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Check Progress", callback_data="mine")],
                [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
            ])
        else:
            # Session already running - show progress / allow claim
            earned = pending_coins(user)
            if session_finished(user):
                status = "✅ Session complete! Claim your coins."
            else:
                status = f"⏳ Time left: <b>{time_left_text(user)}</b>"
            text = (
                "⛏ <b>Mining Progress</b>\n\n"
                f"Earned so far: <b>{earned:.4f} {COIN}</b>\n{status}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💸 Claim Coins", callback_data="claim")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="mine")],
                [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
            ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif action == "claim":
        if user["mining_start"]:
            earned = pending_coins(user)
            user["balance"] += earned
            user["mining_start"] = None  # End session
            save_data(DB)
            text = (
                f"💸 Claimed <b>{earned:.4f} {COIN}</b>!\n"
                f"New balance: <b>{user['balance']:.4f} {COIN}</b>\n\n"
                "Start a new session to keep earning."
            )
        else:
            text = "You have no active mining session. Tap 🚀 Start Mining first."
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )

    elif action == "balance":
        await query.edit_message_text(
            balance_text(user), parse_mode=ParseMode.HTML, reply_markup=back_button()
        )

    elif action == "invite":
        link = f"https://t.me/{context.bot.username}?start=ref_{query.from_user.id}"
        text = (
            "👥 <b>Invite Friends</b>\n\n"
            f"Share your link. When a friend joins, you both get <b>{REFERRAL_BONUS} {COIN}</b>!\n\n"
            f"🔗 {link}\n\n"
            f"Friends invited: <b>{user['referrals']}</b>"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=back_button()
        )

    elif action == "settings":
        status = "ON ✅" if user["notifications"] else "OFF ❌"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔔 Notifications: {status}", callback_data="toggle_notif")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
        ])
        await query.edit_message_text(
            "⚙️ <b>Settings</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard
        )

    elif action == "toggle_notif":
        user["notifications"] = not user["notifications"]
        save_data(DB)
        status = "ON ✅" if user["notifications"] else "OFF ❌"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔔 Notifications: {status}", callback_data="toggle_notif")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
        ])
        await query.edit_message_text(
            "⚙️ <b>Settings</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard
        )


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Cash Flow bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
