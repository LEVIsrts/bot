#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production-Grade Telegram Translation & Tagging Bot
Engineered for Render and Constrained Hosting Environments
Tech Stack: pyTelegramBotAPI (telebot), deep_translator, Flask
"""

import os
import sys
import time
import logging
import threading
from typing import Optional, Dict, Any

# Ensure UTF-8 standard input/output encoding across environments
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import telebot
from telebot.types import Message
from deep_translator import MyMemoryTranslator
from flask import Flask, jsonify

# ══════════════════════════════════════════════════════════════
# 1. Logging Configuration
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TranslatorBot")

# Suppress noisy logs from werkzeug
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ══════════════════════════════════════════════════════════════
# 2. Configuration & Environment Variables
# ══════════════════════════════════════════════════════════════
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8936315525:AAGxsT-QEHTb6LI0W1lQC2h4W5fuJ_xs1zQ").strip()
PORT: int = int(os.getenv("PORT", "8080"))

# Target Topic / Thread Confinement (Topic #3)
TARGET_THREAD_ID: int = int(os.getenv("TARGET_THREAD_ID", "3"))

# Authorized Trigger User (Username: iyedbd or Admin Numerical ID)
AUTHORIZED_USERNAME: str = os.getenv("AUTHORIZED_USERNAME", "iyedbd").lower().strip("@")
_raw_auth_id = os.getenv("AUTHORIZED_USER_ID", "8760969567").strip()
AUTHORIZED_USER_ID: Optional[int] = int(_raw_auth_id) if _raw_auth_id.isdigit() else None

# Target Users to dynamically tag when translation is triggered
TARGET_NAME_KEYWORDS = ("sofine", "traore")

# ══════════════════════════════════════════════════════════════
# 3. In-Memory Registry for Dynamic User Resolution
# ══════════════════════════════════════════════════════════════
# Registry maps: user_id -> dict of profile metadata
member_registry: Dict[int, Dict[str, Any]] = {}
registry_lock = threading.Lock()


def register_user(user: Any) -> None:
    """Inspects and persists user metadata to allow tagging non-username members."""
    if not user or user.is_bot:
        return

    user_id = user.id
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip() or first_name or f"User {user_id}"
    username = (user.username or "").lower().strip()

    with registry_lock:
        if user_id not in member_registry:
            logger.info(f"👤 [Registry] Cached member: {full_name} (@{username or 'no_user'}, ID: {user_id})")
        member_registry[user_id] = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "username": username,
        }


def find_target_recipient() -> Optional[Dict[str, Any]]:
    """Resolves target recipient (Sofine / TRAORE) from dynamic in-memory registry."""
    with registry_lock:
        for uid, data in member_registry.items():
            searchable_str = f"{data['first_name']} {data['last_name']} {data['username']}".lower()
            for kw in TARGET_NAME_KEYWORDS:
                if kw in searchable_str:
                    return {
                        "id": uid,
                        "name": data["full_name"],
                    }
    return None


# ══════════════════════════════════════════════════════════════
# 4. Daemon Flask Health-Check Web Server (for Render Port Scan)
# ══════════════════════════════════════════════════════════════
flask_app = Flask("HealthServer")


@flask_app.route("/", methods=["GET"])
@flask_app.route("/health", methods=["GET"])
def health_endpoint():
    """Returns 200 OK to satisfy Render.com port-binding and health checks."""
    return (
        jsonify(
            status="healthy",
            service="Telegram Translator & Tag Bot",
            target_topic=TARGET_THREAD_ID,
            cached_members=len(member_registry),
        ),
        200,
    )


def start_flask_server() -> None:
    """Runs the Flask health check in a background daemon thread."""
    logger.info(f"🌐 [Web Server] Starting daemon HTTP server on 0.0.0.0:{PORT}...")
    try:
        flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ [Web Server] Flask daemon failed: {e}")


# ══════════════════════════════════════════════════════════════
# 5. Translation Engine Wrapper
# ══════════════════════════════════════════════════════════════
def perform_translation(arabic_text: str) -> str:
    """
    Translates Arabic text to British English using MyMemoryTranslator.
    Guarantees no crashes, returns fallback if network/quota issues occur.
    """
    if not arabic_text or not arabic_text.strip():
        return ""

    text_to_translate = arabic_text.strip()
    try:
        translator = MyMemoryTranslator(source="ar-SA", target="en-GB")
        translated = translator.translate(text_to_translate)
        if translated:
            return translated.strip()
    except Exception as err:
        logger.warning(f"⚠️ [Translator Engine] MyMemory translation error: {err}")

    # Fallback to direct text if translation encounters transient issues
    return text_to_translate


# ══════════════════════════════════════════════════════════════
# 6. Telegram Bot Initialization & Dispatchers
# ══════════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")


def is_authorized_user(from_user: Any) -> bool:
    """Verifies that the trigger sender is iyedbd (by username or ID)."""
    if not from_user:
        return False

    sender_username = (from_user.username or "").lower().strip()
    sender_id = from_user.id

    if sender_username == AUTHORIZED_USERNAME:
        return True
    if AUTHORIZED_USER_ID and sender_id == AUTHORIZED_USER_ID:
        return True

    return False


@bot.message_handler(content_types=["text"])
def handle_topic_messages(message: Message) -> None:
    """
    Core Message Processor:
    - Enforces strict confinement to Topic / Thread ID: 3.
    - Caches user metadata dynamically for tagging.
    - Verifies trigger permissions (authorized user 'iyedbd').
    - Translates Arabic to English.
    - Appends actionable inline tag mention.
    """
    try:
        # ── A. Register Sender & Any Mentioned Entities in Cache ───────
        if message.from_user:
            register_user(message.from_user)

        # Cache any explicit text_mention entities
        if message.entities:
            for ent in message.entities:
                if ent.type == "text_mention" and getattr(ent, "user", None):
                    register_user(ent.user)

        # ── B. Strict Topic / Thread Confinement (Thread ID: 3) ──────
        current_thread_id = getattr(message, "message_thread_id", None)
        if current_thread_id != TARGET_THREAD_ID:
            # Cleanly and immediately ignore messages from other topics or General
            return

        # ── C. Strict Access Control Check ────────────────────────────
        if not is_authorized_user(message.from_user):
            logger.debug(
                f"🔒 [Access Control] Ignored message from unauthorized user: "
                f"@{message.from_user.username} (ID: {message.from_user.id})"
            )
            return

        input_text = (message.text or "").strip()
        if not input_text:
            return

        # Ignore commands like /start, /help to avoid duplicate handling
        if input_text.startswith("/"):
            return

        logger.info(f"📥 [Topic #{TARGET_THREAD_ID}] Authorized message from @{message.from_user.username}: '{input_text}'")

        # ── D. Perform Translation (Arabic -> English) ────────────────
        translated_text = perform_translation(input_text)

        # ── E. Dynamic Target Resolution (Sofine / TRAORE) ────────────
        target = find_target_recipient()

        if target:
            # Actionable inline Markdown mention triggering direct notification
            target_mention = f"[{target['name']}](tg://user?id={target['id']})"
            response_payload = f"{translated_text}\n\n👥 {target_mention}"
            logger.info(f"🎯 [Target Resolved] Tagging {target['name']} (ID: {target['id']})")
        else:
            # Fallback when Sofine/TRAORE has not yet sent a message to the bot
            response_payload = (
                f"{translated_text}\n\n"
                f"🔔 _Notification for Sofine / TRAORE (Will be directly tagged upon their next message)_"
            )
            logger.info("ℹ️ [Target Pending] Target Sofine/TRAORE not yet cached in member registry.")

        # ── F. Send Response Reply Inside Topic #3 ────────────────────
        bot.reply_to(
            message,
            response_payload,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        logger.info(f"✅ [Topic #{TARGET_THREAD_ID}] Dispatched translated response successfully.")

    except Exception as exc:
        logger.error(f"❌ [Handler Exception] Error processing message {getattr(message, 'message_id', 'N/A')}: {exc}")


@bot.message_handler(content_types=["new_chat_members"])
def handle_new_members(message: Message) -> None:
    """Automatically registers newly joined group members into memory."""
    if message.new_chat_members:
        for new_user in message.new_chat_members:
            register_user(new_user)


# ══════════════════════════════════════════════════════════════
# 7. Resilient Infinite-Polling Supervisor Loop
# ══════════════════════════════════════════════════════════════
def run_resilient_bot() -> None:
    """
    Executes an indestructible polling loop with dynamic backoff sleep
    to eliminate crashes from transient network drops or Telegram 409 Conflict errors.
    """
    logger.info("🚀 [Startup] Initializing Telegram Translation Bot Supervisor...")
    logger.info(f"🎯 [Configuration] Locked to Topic/Thread ID: {TARGET_THREAD_ID}")
    logger.info(f"🛡️ [Access Control] Authorized User: @{AUTHORIZED_USERNAME} (ID: {AUTHORIZED_USER_ID or 'Any'})")

    # Start Flask Health-Check Server on background daemon thread
    web_thread = threading.Thread(target=start_flask_server, daemon=True)
    web_thread.start()

    logger.info("▶️ [Bot Polling] Initiating telebot infinity_polling...")

    while True:
        try:
            bot.infinity_polling(
                timeout=20,
                long_polling_timeout=10,
                skip_pending=True,
                allowed_updates=["message", "edited_message", "chat_member"],
            )
        except Exception as err:
            logger.error(f"💥 [Polling Exception] Network drop or Telegram API error: {err}")
            logger.info("⏳ [Backoff] Reconnecting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    run_resilient_bot()
