#(©)Codexbotz
from pyrogram import __version__
from bot import Bot
from config import OWNER_ID, START_MSG
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.database import get_user_tokens, get_referral_stats

TOKENS_PER_REFERRAL = 10
TOKEN_SELL_RATE = 0.01

@Bot.on_callback_query()
async def cb_handler(client: Bot, query: CallbackQuery):
    data = query.data
    
    if data == "about":
        await query.message.edit_text(
            text = f"<b>○ Creator : <a href='tg://user?id={OWNER_ID}'>This Person</a>\n○ Language : <code>Python3</code>\n○ Library : <a href='https://docs.pyrogram.org/'>Pyrogram asyncio {__version__}</a>",
            disable_web_page_preview = True,
            reply_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("🔒 Close", callback_data = "close")
                    ]
                ]
            )
        )
    
    elif data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass
    
    elif data == "referral":
        await query.answer()
        user_id = query.from_user.id
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
             InlineKeyboardButton("💸 Sell Tokens", callback_data="sell_tokens")],
            [InlineKeyboardButton("« Back", callback_data="back_to_start")]
        ])
        
        await query.edit_message_text(referral_text, reply_markup=reply_markup, disable_web_page_preview=True)
    
    elif data == "tokens":
        await query.answer()
        user_id = query.from_user.id
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
            [InlineKeyboardButton("💸 Sell Tokens", callback_data="sell_tokens")],
            [InlineKeyboardButton("« Back", callback_data="back_to_start")]
        ])
        
        await query.edit_message_text(token_text, reply_markup=reply_markup)
    
    elif data == "sell_tokens":
        await query.answer()
        user_id = query.from_user.id
        tokens = await get_user_tokens(user_id)
        
        sell_text = (
            f"💸 **Sell Your Tokens**\n\n"
            f"🪙 **Your Balance:** {tokens} tokens\n"
            f"💵 **Current Rate:** ${TOKEN_SELL_RATE:.2f} per token\n"
            f"💰 **Total Value:** ${tokens * TOKEN_SELL_RATE:.2f}\n\n"
            f"To sell tokens, use:\n"
            f"`/sell_tokens <amount>`\n\n"
            f"Example: `/sell_tokens 50`\n\n"
            f"📝 **Process:**\n"
            f"1. Send command with amount\n"
            f"2. Request sent to admin\n"
            f"3. Get payment after approval"
        )
        
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back", callback_data="tokens")]
        ])
        
        await query.edit_message_text(sell_text, reply_markup=reply_markup)
    
    elif data == "back_to_start":
        await query.answer()
        
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
        
        await query.edit_message_text(
            text=START_MSG.format(
                first=query.from_user.first_name,
                last=query.from_user.last_name,
                username=None if not query.from_user.username else '@' + query.from_user.username,
                mention=query.from_user.mention,
                id=query.from_user.id
            ),
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
