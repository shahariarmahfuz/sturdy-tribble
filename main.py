import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackContext, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
import threading
import json
import os

# মূল বটের টোকেন (আপনার টোকেন দিয়ে প্রতিস্থাপন করুন)
MAIN_BOT_TOKEN = "7323266008:AAFgxW_vfd_qB3ZHcMLq82r-1QllF5inDaM"

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

# মূল বটের জন্য স্টার্ট হ্যান্ডলার (modified to include the "Add Bot" button)
async def start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("🤖 Add Bot", callback_data='add_bot')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Livegram Bot is a builder of feedback bots for Telegram. Read more about it.", reply_markup=reply_markup)

# নতুন বটের জন্য স্টার্ট হ্যান্ডলার
async def new_bot_start(update: Update, context: CallbackContext):
    await update.message.reply_text("নতুন বট: হায়")

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

    # নতুন বটটি স্টার্ট করুন
    new_bot_application.run_polling(stop_signals=None, timeout=30)

# /delete_bot কমান্ড হ্যান্ডলার
async def delete_bot(update: Update, context: CallbackContext):
    if len(context.args) == 1:
        token_to_delete = context.args[0]
        if token_to_delete in running_bots:
            loop, application = running_bots[token_to_delete]
            
            # Stop the bot gracefully
            application.stop()

            # Stop the event loop
            loop.stop()

            # Remove the bot from the dictionary
            del running_bots[token_to_delete]
            save_running_bots()  # Save the updated running bots data
            
            # Remove the bot from user's bot list
            for user_id, bots in user_bots.items():
                user_bots[user_id] = [bot for bot in bots if bot[1] != token_to_delete]
            save_user_bots()  # Save the updated user bots data
            
            await update.message.reply_text(f"বট {token_to_delete} বন্ধ করা হয়েছে।")
        else:
            await update.message.reply_text(f"এই টোকেন {token_to_delete} এর জন্য কোন বট চালু নেই।")
    else:
        await update.message.reply_text("অনুগ্রহ করে একটি সঠিক টোকেন প্রদান করুন। উদাহরণ: /delete_bot <TOKEN>")

# /my_bot কমান্ড হ্যান্ডলার
async def my_bot(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
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
            f"{update.message.from_user.full_name}, thank you for using the bot."
        )
    else:
        response_message = f"{update.message.from_user.full_name}, you have no active bots."

    await update.message.reply_text(response_message)

# Callback handler for the "Add Bot" button
async def add_bot_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("To connect a bot, you should follow these  steps:\n\nGive a little token for the one you want to turn on!!")

# Handle user's token input and start the new bot
async def handle_token_input(update: Update, context: CallbackContext):
    new_bot_token = update.message.text
    admin_chat_id = update.message.chat_id
    threading.Thread(target=start_new_bot, args=(new_bot_token, admin_chat_id, update.message.from_user.id)).start()
    await update.message.reply_text("নতুন বট চালু হয়েছে!")

if __name__ == "__main__":
    try:
        # মূল বটের অ্যাপ্লিকেশন তৈরি
        application = Application.builder().token(MAIN_BOT_TOKEN).build()

        # মূল বটের হ্যান্ডলার সেটআপ
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("delete_bot", delete_bot))
        application.add_handler(CommandHandler("my_bot", my_bot))

        # Add the callback handler for the "Add Bot" button
        application.add_handler(CallbackQueryHandler(add_bot_callback, pattern='add_bot'))

        # Add the handler for user's token input
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token_input))

        # মূল বটটি চালু করুন
        application.run_polling()

    except Exception:
        pass

