import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, CallbackContext
import threading
import json
import os


# মূল বটের টোকেন (আপনার টোকেন দিয়ে প্রতিস্থাপন করুন)
MAIN_BOT_TOKEN = "7474540544:AAHkAcwcRJBP8lpss2UlAM-msBXjyh5l0rs"

# Paths to the JSON files
USER_BOTS_FILE = "user_bots.json"
RUNNING_BOTS_FILE = "running_bots.json"

# Function to save dictionary to a JSON file
def save_to_json_file(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file)

# Function to load dictionary from a JSON file
def load_from_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    else:
        return {}

# Load dictionaries from files during startup
user_bots = load_from_json_file(USER_BOTS_FILE)
running_bots = {token: None for token in load_from_json_file(RUNNING_BOTS_FILE)}  # Initialize with None

def save_user_bots():
    # Convert tuples to lists for JSON serialization
    user_bots_serializable = {k: [(bot[0], bot[1]) for bot in v] for k, v in user_bots.items()}
    save_to_json_file(user_bots_serializable, USER_BOTS_FILE)

def save_running_bots():
    # Only save bot tokens (no loops or application objects)
    running_bots_serializable = list(running_bots.keys())
    save_to_json_file(running_bots_serializable, RUNNING_BOTS_FILE)

# Helper function to get bot username
def get_bot_username(token):
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url).json()
        if response['ok']:
            return response['result']['username']
        else:
            return None
    except Exception:
        return None

# Forward user messages to admin
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.bot_data.get('admin_chat_id'):
            forwarded_message = await update.message.forward(chat_id=context.bot_data['admin_chat_id'])
            context.bot_data[forwarded_message.message_id] = update.message.chat_id
        else:
            pass
    except Exception:
        pass

# Reply to user messages from admin
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        original_message_id = update.message.reply_to_message.message_id
        user_id = context.bot_data.get(original_message_id)

        if user_id:
            try:
                if update.message.text:
                    await context.bot.send_message(chat_id=user_id, text=update.message.text)
                elif update.message.photo:
                    await context.bot.send_photo(chat_id=user_id, photo=update.message.photo[-1].file_id, caption=update.message.caption)
                elif update.message.video:
                    await context.bot.send_video(chat_id=user_id, video=update.message.video.file_id, caption=update.message.caption)
                else:
                    await context.bot.copy_message(chat_id=user_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            except Exception:
                pass

async def new_bot_start(update: Update, context: CallbackContext):
    await update.message.reply_text("নতুন বট: হায়")
    
# মূল বটের জন্য স্টার্ট হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # মূল বটের স্টার্ট মেসেজ
    keyboard = [
        [InlineKeyboardButton("🤖 Add Bot", callback_data='add_bot')],
        [InlineKeyboardButton("🪂 My Bots", callback_data='my_bots')],
        [InlineKeyboardButton("🔌 Disconnect Bot", callback_data='disconnect_bot')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Livegram Bot is a builder of feedback bots for Telegram. Read more about it.",
        reply_markup=reply_markup
    )

# Callback handler for the "Add Bot", "My Bots", and "Disconnect Bot" buttons
async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'add_bot':
        await query.message.reply_text(
            "To connect a bot, you should follow these two steps:\n\n"
            "1. Open @BotFather and create a new bot.\n"
            "2. You'll get a token (e.g. 12345:6789ABCDEF) — just forward or copy-paste it to this chat.\n\n"
            "Warning! Don't connect bots already used by other services like Chatfuel, Manybot, etc."
        )
        context.user_data['awaiting_token'] = True
    elif query.data == 'my_bots':
        user_id = query.from_user.id
        if user_id in user_bots and user_bots[user_id]:
            bot_info_list = "\n".join(
                [f"[✦] @{bot[0]}\n-» {bot[1]}" for bot in user_bots[user_id]]
            )
            response_message = (
                f"All bot: {len(user_bots[user_id])}\n\n"
                f"Here are available bots\n"
                f"━━━━━━✧Hønëy✧━━━━━━\n"
                f"{bot_info_list}\n"
                f"━━━━━━✧Hønëy✧━━━━━━\n\n"
                f"{query.from_user.full_name}, thank you for using the bot."
            )
        else:
            response_message = f"{query.from_user.full_name}, you have no active bots."

        await query.message.reply_text(response_message)
    elif query.data == 'disconnect_bot':
        await query.message.reply_text(
            "Please provide the token of the bot you want to disconnect. Send the token in the next message."
        )
        context.user_data['awaiting_disconnect_token'] = True

# Message handler to receive token and start a new bot
async def receive_token(update: Update, context: CallbackContext):
    if context.user_data.get('awaiting_token'):
        new_bot_token = update.message.text
        admin_chat_id = update.message.chat_id
        threading.Thread(target=start_new_bot, args=(new_bot_token, admin_chat_id, update.message.from_user.id)).start()
        
        bot_username = get_bot_username(new_bot_token)
        if bot_username:
            await update.message.reply_text(
                f"Success! @{bot_username} has been connected. The bot will forward any (including your own) messages sent to it.\n\n"
                "How do I reply to incoming messages?\n"
                "Use Telegram's reply feature. Swipe left (or double-click) on the message you want to reply."
            )
        else:
            await update.message.reply_text("Invalid token or unable to connect the bot. Please try again.")
        
        context.user_data['awaiting_token'] = False
    elif context.user_data.get('awaiting_disconnect_token'):
        # Send processing message
        processing_message = await update.message.reply_text("Please wait, your request is being processed.")
        
        token_to_disconnect = update.message.text
        if token_to_disconnect in running_bots:
            loop, application = running_bots[token_to_disconnect]
            
            # Stop the bot gracefully
            await application.stop()

            # Stop the event loop
            loop.stop()

            # Remove the bot from the dictionary
            del running_bots[token_to_disconnect]
            save_running_bots()  # Save the updated running bots data
            
            # Remove the bot from user's bot list
            for user_id, bots in user_bots.items():
                user_bots[user_id] = [bot for bot in bots if bot[1] != token_to_disconnect]
            save_user_bots()  # Save the updated user bots data
            
            # Delete the processing message and send confirmation
            await processing_message.delete()
            await update.message.reply_text(f"Bot with token {token_to_disconnect} has been disconnected.")
        else:
            # Delete the processing message and notify user
            await processing_message.delete()
            await update.message.reply_text(f"No active bot found with token {token_to_disconnect}.")
        
        context.user_data['awaiting_disconnect_token'] = False

def start_new_bot(token, admin_chat_id, user_id):
    # নতুন ইভেন্ট লুপ তৈরি এবং সেট করুন
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # নতুন বটের অ্যাপ্লিকেশন তৈরি
    new_bot_application = Application.builder().token(token).build()

    # নতুন বটের হ্যান্ডলার সেটআপ
    new_bot_application.add_handler(CommandHandler("start", new_bot_start))
    new_bot_application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.Chat(admin_chat_id), forward_to_admin))
    new_bot_application.add_handler(MessageHandler(filters.ALL & filters.Chat(admin_chat_id), reply_to_user))
   
    # Store admin chat ID in bot data
    new_bot_application.bot_data['admin_chat_id'] = admin_chat_id

    # Store the bot's loop and application for later termination
    running_bots[token] = (loop, new_bot_application)
    save_running_bots()  # Save the running bots data

    # Get bot username and store with user id
    bot_username = get_bot_username(token)
    if bot_username:
        if user_id not in user_bots:
            user_bots[user_id] = []
        user_bots[user_id].append((bot_username, token))
        save_user_bots()  # Save the user bots data

    # Start the new bot
    new_bot_application.run_polling(stop_signals=None, timeout=30)

# মূল বটের অ্যাপ্লিকেশন তৈরি এবং হ্যান্ডলার সেটআপ
def main():
    application = Application.builder().token(MAIN_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token))

    # মূল বটটি স্টার্ট করুন
    application.run_polling()

if __name__ == "__main__":
    main()
