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
    else:
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("😊 About Me", callback_data="about"),
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
