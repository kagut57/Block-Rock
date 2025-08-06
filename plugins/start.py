import os
import asyncio
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatJoinRequest
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from bot import Bot
from config import ADMINS, FORCE_MSG, START_MSG, CUSTOM_CAPTION, DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT, DELAY
from helper_func import subscribed, encode, decode, get_messages
from database.database import add_user, del_user, full_userbase, present_user, fsub

from database.database import (
    add_referral_user, get_user_tokens, update_user_tokens, 
    get_referral_stats, add_referral_transaction
)

TOKENS_PER_REFERRAL = 10
TOKEN_SELL_RATE = 0.01

async def delete_message_after_delay(client: Client, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
    except Exception as e:
        print(f"Error deleting message {message_id} in chat {chat_id}: {e}")

@Bot.on_message(filters.command('start') & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    id = message.from_user.id
    if not await present_user(id):
        try:
            await add_user(id)
        except:
            pass
    
    text = message.text
    if len(text) > 7:
        await message.delete()
        try:
            base64_string = text.split(" ", 1)[1]
        except:
            return
        
        # Check if it's a referral (direct user ID)
        try:
            referrer_id = int(base64_string)
            if referrer_id != id and await present_user(referrer_id):
                success = await add_referral_user(referrer_id, id)
                if success:
                    await update_user_tokens(referrer_id, TOKENS_PER_REFERRAL)
                    
                    try:
                        await client.send_message(
                            referrer_id,
                            f"🎉 **Congratulations!**\n\n"
                            f"You earned **{TOKENS_PER_REFERRAL} tokens** for referring a new user!\n"
                            f"Your current token balance: **{await get_user_tokens(referrer_id)} tokens**\n\n"
                            f"Use /tokens to check your balance or /sell_tokens to sell them back."
                        )
                    except:
                        pass
                    
                    welcome_msg = (
                        f"🎉 **Welcome!**\n\n"
                        f"You were referred by someone and they just earned tokens!\n"
                        f"You can also start earning tokens by sharing your referral link.\n\n"
                        f"Use /referral to get your link!"
                    )
                    await message.reply_text(welcome_msg)
                    return
            else:
                pass
                
        except ValueError:
            string = await decode(base64_string)
            argument = string.split("-")
            if len(argument) == 3:
                try:
                    start = int(int(argument[1]) / abs(client.db_channel.id))
                    end = int(int(argument[2]) / abs(client.db_channel.id))
                except:
                    return
                if start <= end:
                    ids = range(start, end + 1)
                else:
                    ids = []
                    i = start
                    while True:
                        ids.append(i)
                        i -= 1
                        if i < end:
                            break
            elif len(argument) == 2:
                try:
                    ids = [int(int(argument[1]) / abs(client.db_channel.id))]
                except:
                    return
            
            temp_msg = await message.reply("Please wait...")
            try:
                messages = await get_messages(client, ids)
            except:
                await message.reply_text("Something went wrong..!")
                return
            await temp_msg.delete()

            for msg in messages:
                if bool(CUSTOM_CAPTION) & bool(msg.document):
                    caption = CUSTOM_CAPTION.format(
                        previouscaption="" if not msg.caption else msg.caption.html,
                        filename=msg.document.file_name
                    )
                else:
                    caption = "" if not msg.caption else msg.caption.html

                if DISABLE_CHANNEL_BUTTON:
                    reply_markup = msg.reply_markup
                else:
                    reply_markup = None

                try:
                    sent_message = await msg.copy(
                        chat_id=message.from_user.id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    asyncio.create_task(delete_message_after_delay(client, message.from_user.id, sent_message.id, int(DELAY)))
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    sent_message = await msg.copy(
                        chat_id=message.from_user.id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    asyncio.create_task(delete_message_after_delay(client, message.from_user.id, sent_message.id, int(DELAY)))
                except Exception as e:
                    print(f"Error sending message: {e}")
            
            n_msg = await message.reply("**Please forward files somewhere else or save in Saved Messages cause file going to delete in few minutes.")
            await asyncio.sleep(10)
            await n_msg.delete()
            return
    
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("😊 About Me", callback_data="about"),
                InlineKeyboardButton("💰 Referral", callback_data="referral")
            ],
            [
                InlineKeyboardButton("🪙 My Tokens", callback_data="tokens"),
                InlineKeyboardButton("🔒 Close", callback_data="close")
            ]
        ]
    )
    await message.reply_text(
        text=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        quote=True
    )
    return

@Bot.on_message(filters.command('referral') & filters.private & subscribed)
async def referral_command(client: Client, message: Message):
    user_id = message.from_user.id
    bot_username = client.username
    
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    stats = await get_referral_stats(user_id)
    tokens = await get_user_tokens(user_id)
    
    referral_text = (
        f"🔗 **Your Referral System**\n\n"
        f"📊 **Your Stats:**\n"
        f"• Total Referrals: **{stats['total_referrals']}**\n"
        f"• Current Tokens: **{tokens}** 🪙\n"
        f"• Tokens per Referral: **{TOKENS_PER_REFERRAL}** 🪙\n\n"
        f"🔗 **Your Referral Link:**\n"
        f"`{referral_link}`\n\n"
        f"💡 **How it works:**\n"
        f"• Share your link with friends\n"
        f"• When they join using your link, you earn **{TOKENS_PER_REFERRAL} tokens**\n"
        f"• You can sell tokens back to admin\n"
        f"• Current rate: **${TOKEN_SELL_RATE:.2f} per token**\n\n"
        f"📱 **Commands:**\n"
        f"• /tokens - Check token balance\n"
        f"• /sell_tokens <amount> - Sell tokens back\n"
        f"• /referral_stats - Detailed statistics"
    )
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Share Link", switch_inline_query=f"Join this amazing bot: {referral_link}")],
        [InlineKeyboardButton("🪙 My Tokens", callback_data="tokens"), 
         InlineKeyboardButton("💸 Sell Tokens", callback_data="sell_tokens")]
    ])
    
    await message.reply_text(referral_text, reply_markup=reply_markup, disable_web_page_preview=True)

@Bot.on_message(filters.command('tokens') & filters.private & subscribed)
async def tokens_command(client: Client, message: Message):
    user_id = message.from_user.id
    tokens = await get_user_tokens(user_id)
    stats = await get_referral_stats(user_id)
    
    token_text = (
        f"🪙 **Your Token Balance**\n\n"
        f"💰 **Current Balance:** {tokens} tokens\n"
        f"👥 **Total Referrals:** {stats['total_referrals']}\n"
        f"💵 **Token Value:** ${tokens * TOKEN_SELL_RATE:.2f}\n\n"
        f"📈 **Earning Rate:** {TOKENS_PER_REFERRAL} tokens per referral\n"
        f"💲 **Sell Rate:** ${TOKEN_SELL_RATE:.2f} per token\n\n"
        f"Use /sell_tokens <amount> to sell your tokens!"
    )
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Get Referral Link", callback_data="referral")],
        [InlineKeyboardButton("💸 Sell Tokens", callback_data="sell_tokens")]
    ])
    
    await message.reply_text(token_text, reply_markup=reply_markup)

@Bot.on_message(filters.command('sell_tokens') & filters.private & subscribed)
async def sell_tokens_command(client: Client, message: Message):
    user_id = message.from_user.id
    current_tokens = await get_user_tokens(user_id)
    
    try:
        amount = int(message.command[1]) if len(message.command) > 1 else 0
    except (ValueError, IndexError):
        await message.reply_text(
            "❌ **Invalid amount!**\n\n"
            f"Usage: `/sell_tokens <amount>`\n"
            f"Example: `/sell_tokens 50`\n\n"
            f"Your current balance: **{current_tokens} tokens**"
        )
        return
    
    if amount <= 0:
        await message.reply_text("❌ Amount must be greater than 0!")
        return
    
    if amount > current_tokens:
        await message.reply_text(
            f"❌ **Insufficient tokens!**\n\n"
            f"You have: **{current_tokens} tokens**\n"
            f"You want to sell: **{amount} tokens**"
        )
        return
    
    total_value = amount * TOKEN_SELL_RATE
    
    sell_text = (
        f"💸 **Token Sell Request**\n\n"
        f"🪙 **Amount:** {amount} tokens\n"
        f"💵 **Value:** ${total_value:.2f}\n"
        f"📊 **Rate:** ${TOKEN_SELL_RATE:.2f} per token\n\n"
        f"👤 **User:** {message.from_user.mention}\n"
        f"🆔 **User ID:** `{user_id}`\n\n"
        f"⚠️ This request has been sent to admins for approval."
    )
    
    admin_text = (
        f"💸 **NEW TOKEN SELL REQUEST**\n\n"
        f"👤 **User:** {message.from_user.mention}\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"👤 **Username:** @{message.from_user.username or 'None'}\n\n"
        f"🪙 **Tokens to Sell:** {amount}\n"
        f"💵 **Total Value:** ${total_value:.2f}\n"
        f"📊 **Current Balance:** {current_tokens} tokens\n\n"
        f"Use /approve_sell {user_id} {amount} to approve\n"
        f"Use /reject_sell {user_id} {amount} to reject"
    )
    
    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, admin_text)
        except:
            pass
    
    await add_referral_transaction(user_id, "sell_request", amount, total_value)
    
    await message.reply_text(sell_text)

@Bot.on_message(filters.command(['approve_sell', 'reject_sell']) & filters.private & filters.user(ADMINS))
async def handle_sell_request(client: Client, message: Message):
    try:
        cmd_parts = message.text.split()
        action = cmd_parts[0][1:]  # Remove '/'
        target_user_id = int(cmd_parts[1])
        amount = int(cmd_parts[2])
    except (ValueError, IndexError):
        await message.reply_text("❌ Invalid command format!")
        return
    
    current_tokens = await get_user_tokens(target_user_id)
    
    if action == "approve_sell":
        if amount > current_tokens:
            await message.reply_text(f"❌ User doesn't have enough tokens! Current: {current_tokens}")
            return
        
        await update_user_tokens(target_user_id, -amount)
        total_value = amount * TOKEN_SELL_RATE
        
        await add_referral_transaction(target_user_id, "sell_approved", amount, total_value)
        
        try:
            await client.send_message(
                target_user_id,
                f"✅ **Token Sale Approved!**\n\n"
                f"🪙 **Sold:** {amount} tokens\n"
                f"💵 **Value:** ${total_value:.2f}\n\n"
                f"💰 **Remaining Balance:** {await get_user_tokens(target_user_id)} tokens\n\n"
                f"Payment will be processed shortly. Contact admin for payment details."
            )
        except:
            pass
        
        await message.reply_text(f"✅ Approved! Deducted {amount} tokens from user {target_user_id}")
        
    elif action == "reject_sell":
        await add_referral_transaction(target_user_id, "sell_rejected", amount, 0)
        
        try:
            await client.send_message(
                target_user_id,
                f"❌ **Token Sale Rejected**\n\n"
                f"🪙 **Amount:** {amount} tokens\n\n"
                f"Your request has been rejected by admin. Contact support for more information."
            )
        except:
            pass
        
        await message.reply_text(f"❌ Rejected sell request for {amount} tokens from user {target_user_id}")

@Bot.on_message(filters.command('referral_stats') & filters.private & subscribed)
async def referral_stats_command(client: Client, message: Message):
    user_id = message.from_user.id
    stats = await get_referral_stats(user_id)
    
    stats_text = (
        f"📊 **Detailed Referral Statistics**\n\n"
        f"👥 **Total Referrals:** {stats['total_referrals']}\n"
        f"🪙 **Total Tokens Earned:** {stats['total_tokens_earned']}\n"
        f"💸 **Tokens Sold:** {stats['tokens_sold']}\n"
        f"💰 **Current Balance:** {await get_user_tokens(user_id)} tokens\n\n"
        f"📈 **Performance:**\n"
        f"• Earnings: ${stats['total_earnings']:.2f}\n"
        f"• Avg. per Referral: {stats['total_tokens_earned']/max(1, stats['total_referrals']):.1f} tokens\n\n"
        f"🔗 Use /referral to get your referral link!"
    )
    
    await message.reply_text(stats_text)

# Callback query handlers for inline buttons
@Bot.on_callback_query(filters.regex("referral"))
async def referral_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    bot_username = client.username
    
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    stats = await get_referral_stats(user_id)
    tokens = await get_user_tokens(user_id)
    
    referral_text = (
        f"🔗 **Your Referral System**\n\n"
        f"📊 **Your Stats:**\n"
        f"• Total Referrals: **{stats['total_referrals']}**\n"
        f"• Current Tokens: **{tokens}** 🪙\n\n"
        f"🔗 **Your Referral Link:**\n"
        f"`{referral_link}`\n\n"
        f"💡 Share this link to earn **{TOKENS_PER_REFERRAL} tokens** per referral!"
    )
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Share Link", switch_inline_query=f"Join this amazing bot: {referral_link}")],
        [InlineKeyboardButton("« Back", callback_data="back_to_start")]
    ])
    
    await callback_query.edit_message_text(referral_text, reply_markup=reply_markup, disable_web_page_preview=True)

@Bot.on_callback_query(filters.regex("tokens"))
async def tokens_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    tokens = await get_user_tokens(user_id)
    stats = await get_referral_stats(user_id)
    
    token_text = (
        f"🪙 **Your Token Balance**\n\n"
        f"💰 **Current Balance:** {tokens} tokens\n"
        f"👥 **Total Referrals:** {stats['total_referrals']}\n"
        f"💵 **Token Value:** ${tokens * TOKEN_SELL_RATE:.2f}\n\n"
        f"Use /sell_tokens <amount> to sell your tokens!"
    )
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Sell Tokens", callback_data="sell_tokens")],
        [InlineKeyboardButton("« Back", callback_data="back_to_start")]
    ])
    
    await callback_query.edit_message_text(token_text, reply_markup=reply_markup)

@Bot.on_callback_query(filters.regex("sell_tokens"))
async def sell_tokens_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    tokens = await get_user_tokens(user_id)
    
    sell_text = (
        f"💸 **Sell Your Tokens**\n\n"
        f"🪙 **Your Balance:** {tokens} tokens\n"
        f"💵 **Current Rate:** ${TOKEN_SELL_RATE:.2f} per token\n"
        f"💰 **Total Value:** ${tokens * TOKEN_SELL_RATE:.2f}\n\n"
        f"To sell tokens, use:\n"
        f"`/sell_tokens <amount>`\n\n"
        f"Example: `/sell_tokens 50`"
    )
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data="tokens")]
    ])
    
    await callback_query.edit_message_text(sell_text, reply_markup=reply_markup)

@Bot.on_callback_query(filters.regex("back_to_start"))
async def back_to_start_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("😊 About Me", callback_data="about"),
                InlineKeyboardButton("💰 Referral", callback_data="referral")
            ],
            [
                InlineKeyboardButton("🪙 My Tokens", callback_data="tokens"),
                InlineKeyboardButton("🔒 Close", callback_data="close")
            ]
        ]
    )
    
    await callback_query.edit_message_text(
        text=START_MSG.format(
            first=callback_query.from_user.first_name,
            last=callback_query.from_user.last_name,
            username=None if not callback_query.from_user.username else '@' + callback_query.from_user.username,
            mention=callback_query.from_user.mention,
            id=callback_query.from_user.id
        ),
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

#=====================================================================================##

WAIT_MSG = """"<b>Processing ...</b>"""
REPLY_ERROR = """<code>Use this command as a replay to any telegram message with out any spaces.</code>"""

#=====================================================================================##
        
@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    buttons = []
    
    bot_id = client.me.id
    fsub_entry = fsub.find_one({"_id": bot_id})

    if not fsub_entry or "channel_ids" not in fsub_entry:
        return

    force_sub_channels = fsub_entry["channel_ids"]
    
    for idx, force_sub_channel in enumerate(force_sub_channels, start=1):
        try:
            invite_link = await client.create_chat_invite_link(chat_id=force_sub_channel)
            buttons.append(
                InlineKeyboardButton(
                    f"Join Channel {idx}",
                    url=invite_link.invite_link
                )
            )
        except Exception as e:
            print(f"Error creating invite link for channel {force_sub_channel}: {e}")

    button_rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    try:
        button_rows.append(
            [
                InlineKeyboardButton(
                    text='Try Again',
                    url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ]
        )
    except IndexError:
        pass

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=InlineKeyboardMarkup(button_rows),
        quote=True,
        disable_web_page_preview=True
    )

    
#=====================================================================================##

WAIT_MSG = """"<b>Processing ...</b>"""

REPLY_ERROR = """<code>Use this command as a replay to any telegram message with out any spaces.</code>"""

#=====================================================================================##

        
@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    buttons = []
    
    bot_id = client.me.id
    fsub_entry = fsub.find_one({"_id": bot_id})

    if not fsub_entry or "channel_ids" not in fsub_entry:
        return

    force_sub_channels = fsub_entry["channel_ids"]
    
    # Iterate through each force subscription channel
    for idx, force_sub_channel in enumerate(force_sub_channels, start=1):
        try:
            invite_link = await client.create_chat_invite_link(chat_id=force_sub_channel)
            buttons.append(
                InlineKeyboardButton(
                    f"Join Channel {idx}",
                    url=invite_link.invite_link
                )
            )
        except Exception as e:
            print(f"Error creating invite link for channel {force_sub_channel}: {e}")

    # Group buttons into rows of two
    button_rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    try:
        button_rows.append(
            [
                InlineKeyboardButton(
                    text='Try Again',
                    url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ]
        )
    except IndexError:
        pass

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=InlineKeyboardMarkup(button_rows),
        quote=True,
        disable_web_page_preview=True
    )

@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await full_userbase()
    await msg.edit(f"{len(users)} users are using this bot")

ongoing_broadcasts = {}
MAX_CONCURRENT = 25
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

def format_time(seconds):
    mins, secs = divmod(seconds, 60)
    return f"{mins}m {secs}s" if mins else f"{secs}s"

async def send_single(client, chat_id, broadcast_msg, broadcast_id, stats):
    async with semaphore:
        if ongoing_broadcasts.get(broadcast_id, {}).get('cancelled', False):
            return
        try:
            sent_msg = await broadcast_msg.copy(chat_id)
            ongoing_broadcasts[broadcast_id]['sent_messages'].append({
                'chat_id': chat_id,
                'message_id': sent_msg.id
            })
            stats['successful'] += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            sent_msg = await broadcast_msg.copy(chat_id)
            ongoing_broadcasts[broadcast_id]['sent_messages'].append({
                'chat_id': chat_id,
                'message_id': sent_msg.id
            })
            stats['successful'] += 1
        except UserIsBlocked:
            await del_user(chat_id)
            stats['blocked'] += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            stats['deleted'] += 1
        except:
            stats['unsuccessful'] += 1

@Bot.on_message(filters.private & filters.command('broadcast') & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
    if not message.reply_to_message:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        await msg.delete()
        return

    broadcast_id = str(int(time.time()))
    query = await full_userbase()
    broadcast_msg = message.reply_to_message

    stats = {
        'successful': 0,
        'blocked': 0,
        'deleted': 0,
        'unsuccessful': 0
    }

    ongoing_broadcasts[broadcast_id] = {
        'cancelled': False,
        'sent_messages': [],
        'admin_id': message.from_user.id,
        'start_time': time.time()
    }

    pls_wait = await message.reply(
        f"<i>Broadcasting Message.. This will Take Some Time</i>\n"
        f"<b>Broadcast ID:</b> <code>{broadcast_id}</code>\n"
        f"<b>Cancel Command:</b> <code>/cancel {broadcast_id}</code>"
    )

    tasks = [
        send_single(client, chat_id, broadcast_msg, broadcast_id, stats)
        for chat_id in query
    ]
    await asyncio.gather(*tasks)

    total = len(query)
    end_time = int(time.time() - ongoing_broadcasts[broadcast_id]["start_time"])
    cancelled = ongoing_broadcasts[broadcast_id]["cancelled"]

    if cancelled:
        status = (
            f"<b><u>Broadcast Cancelled</u></b>\n"
            f"<b>Broadcast ID:</b> <code>{broadcast_id}</code>\n"
            f"<b>Total Users Processed:</b> <code>{total}</code>\n"
            f"<b>Messages Sent Before Cancel:</b> <code>{stats['successful']}</code>\n"
            f"<b>Blocked Users:</b> <code>{stats['blocked']}</code>\n"
            f"<b>Deleted Accounts:</b> <code>{stats['deleted']}</code>\n"
            f"<b>Unsuccessful:</b> <code>{stats['unsuccessful']}</code>"
        )
    else:
        status = (
            f"<b><u>Broadcast Completed</u></b>\n"
            f"<b>Broadcast ID:</b> <code>{broadcast_id}</code>\n"
            f"<b>Total Users:</b> <code>{total}</code>\n"
            f"<b>Successful:</b> <code>{stats['successful']}</code>\n"
            f"<b>Blocked Users:</b> <code>{stats['blocked']}</code>\n"
            f"<b>Deleted Accounts:</b> <code>{stats['deleted']}</code>\n"
            f"<b>Unsuccessful:</b> <code>{stats['unsuccessful']}</code>\n"
            f"<b>Time Taken:</b> <code>{format_time(end_time)}</code>"
        )

    await message.reply(status)

@Bot.on_message(filters.private & filters.command('cancel') & filters.user(ADMINS))
async def cancel_broadcast(client: Bot, message: Message):
    if len(message.command) != 2:
        await message.reply("⚠️ Please provide the broadcast ID as well. Usage: /cancel <id>")
        return

    broadcast_id = message.command[1]

    if broadcast_id not in ongoing_broadcasts:
        await message.reply("❌ No ongoing broadcast found with this ID or broadcast already completed.")
        return

    broadcast_info = ongoing_broadcasts[broadcast_id]

    if broadcast_info['admin_id'] != message.from_user.id:
        await message.reply("❌ You can only cancel broadcasts started by you.")
        return

    broadcast_info['cancelled'] = True

    cancel_msg = await message.reply(
        f"✅ <b>Broadcast Cancelled!</b>\n"
        f"<b>Broadcast ID:</b> <code>{broadcast_id}</code>\n"
        f"<i>Now deleting sent messages...</i>"
    )

    deleted_count = 0
    failed_deletes = 0
    total_messages = len(broadcast_info['sent_messages'])

    for i, msg_info in enumerate(broadcast_info['sent_messages']):
        try:
            await client.delete_messages(
                chat_id=msg_info['chat_id'],
                message_ids=msg_info['message_id']
            )
            deleted_count += 1
            if i % 20 == 0:
                await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                await client.delete_messages(
                    chat_id=msg_info['chat_id'],
                    message_ids=msg_info['message_id']
                )
                deleted_count += 1
            except:
                failed_deletes += 1
        except (MessageDeleteForbidden, UserIsBlocked, InputUserDeactivated):
            failed_deletes += 1
        except:
            failed_deletes += 1
        if i % 50 == 0 and i > 0:
            try:
                await cancel_msg.edit(
                    f"✅ <b>Broadcast Cancelled!</b>\n"
                    f"<b>Broadcast ID:</b> <code>{broadcast_id}</code>\n"
                    f"<i>Deleting messages... {i}/{total_messages}</i>"
                )
            except:
                pass

    final_status = (
        f"✅ <b>Broadcast Cancelled & Cleanup Completed</b>\n"
        f"<b>Broadcast ID:</b> <code>{broadcast_id}</code>\n"
        f"<b>Messages Deleted:</b> <code>{deleted_count}</code>\n"
        f"<b>Failed Deletions:</b> <code>{failed_deletes}</code>\n"
        f"<b>Total Messages Sent:</b> <code>{total_messages}</code>"
    )

    await cancel_msg.edit(final_status)
    if broadcast_id in ongoing_broadcasts:
        del ongoing_broadcasts[broadcast_id]

@Bot.on_message(filters.private & filters.command('broadcasts') & filters.user(ADMINS))
async def list_broadcasts(client: Bot, message: Message):
    if not ongoing_broadcasts:
        await message.reply("No ongoing broadcasts.")
        return
    broadcast_list = "<b>Ongoing Broadcasts:</b>\n\n"
    for broadcast_id, info in ongoing_broadcasts.items():
        elapsed_time = int(time.time() - info['start_time'])
        broadcast_list += (
            f"🔄 <code>{broadcast_id}</code>\n"
            f"⏰ Running for: {format_time(elapsed_time)}\n"
            f"📤 Messages sent: {len(info['sent_messages'])}\n"
            f"🚫 Cancel: <code>/cancel {broadcast_id}</code>\n\n"
        )
    await message.reply(broadcast_list)

#add fsub in db 
@Bot.on_message(filters.command('addfsub') & filters.private & filters.user(ADMINS))
async def add_fsub(client, message):
    if len(message.command) == 1:
        await message.reply("Please provide channel IDs to add as fsub in the bot. If adding more than one, separate IDs with spaces.")
        return

    channel_ids = message.text.split()[1:]
    bot_id = client.me.id

    for channel_id in channel_ids:
        try:
            test_msg = await client.send_message(int(channel_id), "test")
            await test_msg.delete()
        except:
            await message.reply(f"Please make admin bot in channel_id: {channel_id} or double check the id.")
            return

    fsub.update_one(
        {"_id": bot_id},
        {"$addToSet": {"channel_ids": {"$each": channel_ids}}},
        upsert=True
    )
    await message.reply(f"Added channel IDs: {', '.join(channel_ids)}")

### Deleting Channel IDs
@Bot.on_message(filters.command('delfsub') & filters.private & filters.user(ADMINS))
async def del_fsub(client, message):
    if len(message.command) == 1:
        await message.reply("Please provide channel IDs to delete from fsub in the bot. If deleting more than one, separate IDs with spaces.")
        return

    channel_ids = message.text.split()[1:]
    bot_id = client.me.id

    fsub.update_one(
        {"_id": bot_id},
        {"$pull": {"channel_ids": {"$in": channel_ids}}}
    )
    await message.reply(f"Deleted channel IDs: {', '.join(channel_ids)}")

### Showing All Channel IDs
@Bot.on_message(filters.command('showfsub') & filters.private & filters.user(ADMINS))
async def show_fsub(client, message):
    bot_id = client.me.id
    fsub_entry = fsub.find_one({"_id": bot_id})

    if fsub_entry and "channel_ids" in fsub_entry:
        channel_ids = fsub_entry["channel_ids"]
        channel_info = []
        for channel_id in channel_ids:
            try:
                chat = await client.get_chat(int(channel_id))
            except:
                continue
            channel_info.append(f"→ **[{chat.title}]({chat.invite_link})**")
        if channel_info:
            await message.reply(f"**Force Subscribed channels:**\n" + "\n".join(channel_info), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        else:
            await message.reply("No force sub channels found.")
    else:
        await message.reply("No subscribed channel IDs found.")
