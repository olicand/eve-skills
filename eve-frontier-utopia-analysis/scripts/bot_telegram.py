#!/usr/bin/env python3
"""Telegram Bot integration for EVE Frontier AI Agent.

Provides a chat-like interface where users can:
1. Log in via EVE Frontier SSO (/login command)
2. Ask natural language questions about the game
3. The AI agent interprets queries and calls appropriate skills
4. Results are formatted and sent back in chat

Prerequisites:
    pip install python-telegram-bot openai

Environment variables:
    TELEGRAM_BOT_TOKEN       - Telegram bot token from @BotFather
    OPENAI_API_KEY           - OpenAI API key (or compatible endpoint)
    EVE_FRONTIER_CLIENT_ID   - SSO OAuth2 client ID
    EVE_FRONTIER_REDIRECT_URI - SSO callback URL

Usage:
    export TELEGRAM_BOT_TOKEN="..."
    export OPENAI_API_KEY="..."
    python3 bot_telegram.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# ---- lazy imports for optional deps ----
try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError:
    print("Install python-telegram-bot:  pip install python-telegram-bot")
    sys.exit(1)

try:
    import openai
except ImportError:
    print("Install openai:  pip install openai")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))
from session_manager import SessionManager
from skill_executor import SkillExecutor
from skill_tool_definitions import get_tool_definitions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)

SYSTEM_PROMPT = """\
You are an EVE Frontier game assistant AI. You help players interact with the \
EVE Frontier universe through available tools.

You can:
- Look up solar systems, constellations, ships, item types, and tribes
- Query Smart Assemblies (Gates, Turrets, Storage Units) on the Sui blockchain
- Check player characters, jump history, killmails, and combat events
- Help plan jump routes and build Sui transactions for gate jumps
- Send sandbox commands (/moveme, /giveitem) to the game
- Check launcher status and control

When the user is not logged in, suggest they use the /login command first.
Always respond concisely. Format game data clearly.
Respond in the same language as the user.
"""

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

session_mgr = SessionManager()
executor = SkillExecutor(session_mgr)
ai_client: openai.OpenAI | None = None


def get_ai_client() -> openai.OpenAI:
    global ai_client
    if ai_client is None:
        kwargs: dict[str, Any] = {"api_key": OPENAI_API_KEY}
        if OPENAI_BASE_URL:
            kwargs["base_url"] = OPENAI_BASE_URL
        ai_client = openai.OpenAI(**kwargs)
    return ai_client


# ---------------------------------------------------------------------------
# AI Agent logic
# ---------------------------------------------------------------------------

MAX_TOOL_ROUNDS = 5


def run_agent(user_id: str, user_message: str) -> str:
    """Run the AI agent loop: user message → tool calls → final response."""
    client = get_ai_client()
    tools = get_tool_definitions()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        choice = response.choices[0]

        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            return choice.message.content or "(no response)"

        messages.append(choice.message)

        for tc in choice.message.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

            logger.info("Tool call: %s(%s)", fn_name, json.dumps(fn_args, ensure_ascii=False)[:200])

            result = executor.execute(user_id, fn_name, fn_args)

            result_str = json.dumps(result, indent=2, ensure_ascii=False)
            if len(result_str) > 4000:
                result_str = result_str[:3900] + "\n... (truncated)"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    return "I've made too many tool calls. Please try a simpler query."


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to EVE Frontier Assistant!\n\n"
        "I can help you explore the universe, look up ships, items, "
        "check Smart Assemblies, plan jumps, and more.\n\n"
        "Commands:\n"
        "  /login - Log in with EVE Frontier SSO\n"
        "  /login_token <token> - Log in with a bearer token\n"
        "  /login_wallet <0x...> - Link EVE Vault wallet\n"
        "  /status - Check auth status\n"
        "  /logout - Log out\n\n"
        "Or just ask me anything about EVE Frontier!"
    )


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"tg_{update.effective_user.id}"
    session = session_mgr.get_session(user_id)
    result = session_mgr.start_login(session)

    if result["ok"]:
        await update.message.reply_text(
            f"Click the link below to log in:\n\n{result['login_url']}\n\n"
            "After logging in, you'll be redirected. "
            "Copy the auth code and send it with:\n"
            "/callback <code>"
        )
    else:
        await update.message.reply_text(
            f"Login not available: {result.get('error')}\n"
            f"Hint: {result.get('hint', '')}\n\n"
            "Alternative: use /login_token <your_bearer_token> to log in directly."
        )


async def cmd_login_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"tg_{update.effective_user.id}"
    if not context.args:
        await update.message.reply_text("Usage: /login_token <bearer_token>")
        return

    token = context.args[0]
    session = session_mgr.get_session(user_id)
    result = session_mgr.login_with_token(session, token)

    if result["ok"]:
        name = result.get("claims_summary", {}).get("name", "unknown")
        await update.message.reply_text(f"Logged in as: {name}")
        await update.message.delete()
    else:
        await update.message.reply_text(f"Login failed: {result.get('error')}")


async def cmd_login_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"tg_{update.effective_user.id}"
    if not context.args:
        await update.message.reply_text("Usage: /login_wallet <0x...>")
        return

    wallet = context.args[0]
    session = session_mgr.get_session(user_id)
    result = session_mgr.login_with_wallet(session, wallet)
    await update.message.reply_text(result.get("message", str(result)))


async def cmd_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"tg_{update.effective_user.id}"
    if not context.args:
        await update.message.reply_text("Usage: /callback <auth_code>")
        return

    code = context.args[0]
    session = session_mgr.get_session(user_id)
    result = session_mgr.complete_login(session, code=code)

    if result["ok"]:
        await update.message.reply_text(f"Login successful! Welcome, {result.get('user', 'pilot')}!")
    else:
        await update.message.reply_text(f"Login failed: {result.get('error')}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"tg_{update.effective_user.id}"
    session = session_mgr.get_session(user_id)
    summary = session.summary()
    lines = [
        f"Authenticated: {'Yes' if summary['authenticated'] else 'No'}",
        f"Bearer: {summary.get('bearer_masked') or 'None'}",
        f"Wallet: {summary.get('wallet_masked') or 'None'}",
        f"Environment: {summary['env']}",
    ]
    if summary.get("expired"):
        lines.append("Token: EXPIRED (will auto-refresh if possible)")
    await update.message.reply_text("\n".join(lines))


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"tg_{update.effective_user.id}"
    session_mgr.delete_session(user_id)
    await update.message.reply_text("Logged out. Your session has been cleared.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle natural language messages via AI agent."""
    user_id = f"tg_{update.effective_user.id}"
    user_text = update.message.text

    if not OPENAI_API_KEY:
        await update.message.reply_text(
            "AI agent not configured (OPENAI_API_KEY not set).\n"
            "You can still use direct commands like /status, /login, etc."
        )
        return

    thinking_msg = await update.message.reply_text("Thinking...")

    try:
        response = run_agent(user_id, user_text)

        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i + 4096])
        else:
            await thinking_msg.edit_text(response)
    except Exception as e:
        logger.exception("Agent error")
        await thinking_msg.edit_text(f"Error: {str(e)[:500]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN environment variable.")
        print("\nExample:")
        print("  export TELEGRAM_BOT_TOKEN='your_token_from_botfather'")
        print("  export OPENAI_API_KEY='your_openai_key'")
        print("  python3 bot_telegram.py")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CommandHandler("login_token", cmd_login_token))
    app.add_handler(CommandHandler("login_wallet", cmd_login_wallet))
    app.add_handler(CommandHandler("callback", cmd_callback))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting... (model=%s)", OPENAI_MODEL)
    app.run_polling()


if __name__ == "__main__":
    main()
