import logging
import asyncio
import sqlite3
import aiosqlite
import hashlib
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    ChatMember
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from telegram.error import TelegramError

# --- কনফিগারেশন ---
BOT_TOKEN = "8892008701:AAGnaD6YAoiMaNlwvnowULCJYFU6Bwcd0CM"
ADMIN_ID = 8212595643

REQUIRED_GROUP = "@susissususkss"  
REQUIRED_CHANNEL = "@susissususks" 

TEST_MODE = True  

# কনভারসেশন স্টেটসমূহ
ADD_KEY, ADD_INFO, ADD_IMG = range(3)
EDIT_KEY, EDIT_FIELD, EDIT_VALUE = range(3, 6)
SUPPORT_MSG = 6

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_NAME = "combo_bot.db"

# --- ডেটাবেজ সেটআপ ---
async def init_db(application: Application):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                points REAL DEFAULT 0.0,
                referred_by INTEGER,
                joined_status INTEGER DEFAULT 0
            )''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                referee_id INTEGER,
                status TEXT,
                PRIMARY KEY (referrer_id, referee_id)
            )''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                course_key TEXT PRIMARY KEY,
                course_name TEXT,
                image_id TEXT,
                info_text TEXT,
                channel_id TEXT
            )''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_access (
                user_id INTEGER,
                course_key TEXT,
                invite_link TEXT,
                used INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, course_key)
            )''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
        await db.execute('''
            INSERT OR IGNORE INTO config (key, value) VALUES ('course_cost', '20.0')
        ''')
        await db.commit()
    print("✅ Combo Bot Database Initialized Successfully!")

# --- রিয়েল-টাইম মেম্বারশিপ চেক ---
async def is_user_joined(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member_group = await context.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
        member_channel = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        valid_statuses = [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        return member_group.status in valid_statuses and member_channel.status in valid_statuses
    except TelegramError:
        return False

async def get_course_cost() -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM config WHERE key = 'course_cost'") as cursor:
            row = await cursor.fetchone()
            if row:
                return float(row[0])
    return 20.0

# --- কিবোর্ডসমূহ ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👤 প্রোফাইল"), KeyboardButton("📚 আমার কোর্স")],
        [KeyboardButton("🛒 কোর্স কিনুন"), KeyboardButton("🔗 রেফারেল লিংক")],
        [KeyboardButton("🏆 লিডারবোর্ড"), KeyboardButton("📂 সকল কোর্সসমূহ")],
        [KeyboardButton("💬 সাপোর্ট")]
    ], resize_keyboard=True, input_field_placeholder="মেনু নির্বাচন করুন 👇")

def get_batch_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📚 HSC 27"), KeyboardButton("📚 HSC 28")],
        [KeyboardButton("🔙 Back"), KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

def get_platform_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔹 ACS"), KeyboardButton("🔹 BP")],
        [KeyboardButton("🔹 UDVAS")],
        [KeyboardButton("🔙 Back"), KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

def get_subject_keyboard(plat):
    if plat == "ACS":
        return ReplyKeyboardMarkup([
            [KeyboardButton("🧪 Physics"), KeyboardButton("🧪 Chemistry")],
            [KeyboardButton("📐 Math"), KeyboardButton("🧬 Biology")],
            [KeyboardButton("📝 EBI")],
            [KeyboardButton("🔙 Back"), KeyboardButton("🏠 Main Menu")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            [KeyboardButton("📚 Physics"), KeyboardButton("📚 Chemistry")],
            [KeyboardButton("📚 Math"), KeyboardButton("📚 Biology")],
            [KeyboardButton("🔙 Back"), KeyboardButton("🏠 Main Menu")]
        ], resize_keyboard=True)

def get_cycle_keyboard(sub):
    if "Chemistry" in sub:
        cycles = [["Cycle 1", "Cycle 2"], ["Cycle 3", "Cycle 4"], ["Cycle 5"], ["Combo"]]
    elif "EBI" in sub:
        cycles = [["EBI Link"]]
    else:
        cycles = [["Cycle 1", "Cycle 2"], ["Cycle 3", "Cycle 4"], ["Cycle 5", "Cycle 6"], ["Combo"]]
    
    cycles.append(["🔙 Back", "🏠 Main Menu"])
    return ReplyKeyboardMarkup(cycles, resize_keyboard=True)

# --- মেইন হ্যান্ডলার ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0].replace("ref_", ""))
            if ref_id != user_id:
                async with aiosqlite.connect(DB_NAME) as db:
                    async with db.execute("SELECT 1 FROM referrals WHERE referee_id = ?", (user_id,)) as cursor:
                        existing = await cursor.fetchone()
                    
                    if not existing:
                        await db.execute(
                            "INSERT INTO referrals (referrer_id, referee_id, status) VALUES (?, ?, ?)",
                            (ref_id, user_id, "active")
                        )
                        await db.execute(
                            "UPDATE users SET points = points + 5 WHERE user_id = ?",
                            (ref_id,)
                        )
                        await db.commit()
                        
                        try:
                            await context.bot.send_message(
                                chat_id=ref_id,
                                text=f"🎉 কেউ আপনার রেফারেল লিংক ব্যবহার করে জয়েন করেছে!\n👤 ইউজার: {update.effective_user.full_name}\n💰 পেলেন ৫ পয়েন্ট!"
                            )
                        except:
                            pass
        except:
            pass
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name, points) VALUES (?, ?, ?, ?)",
            (user_id, update.effective_user.username, update.effective_user.full_name, 5.0 if TEST_MODE else 0.0)
        )
        await db.commit()
    
    if not await is_user_joined(context, user_id):
        keyboard = [
            [InlineKeyboardButton("💬 Join Group", url=f"https://t.me/{REQUIRED_GROUP[1:]}")],
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
            [InlineKeyboardButton("✅ Joined", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ **আপনাকে প্রথমে গ্রুপ ও চ্যানেলে জয়েন করতে হবে!**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await update.message.reply_text(
        "👋 স্বাগতম! নিচের মেনু থেকে অপশন নির্বাচন করুন:",
        reply_markup=get_main_keyboard()
    )

# --- টেক্সট বাটন হ্যান্ডলার ---
async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name, points) VALUES (?, ?, ?, ?)",
            (user_id, update.effective_user.username, update.effective_user.full_name, 5.0 if TEST_MODE else 0.0)
        )
        await db.commit()
    
    if not await is_user_joined(context, user_id):
        keyboard = [
            [InlineKeyboardButton("💬 Join Group", url=f"https://t.me/{REQUIRED_GROUP[1:]}")],
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
            [InlineKeyboardButton("✅ Joined", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ **আপনাকে প্রথমে গ্রুপ ও চ্যানেলে জয়েন করতে হবে!**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if 'nav' not in context.user_data:
        context.user_data['nav'] = {'state': 'MAIN', 'batch': None, 'plat': None, 'sub': None}
    nav = context.user_data['nav']
    
    if text == "🏠 Main Menu":
        nav.update({'state': 'MAIN', 'batch': None, 'plat': None, 'sub': None})
        await update.message.reply_text("🏠 মেইন মেনু:", reply_markup=get_main_keyboard())
        return
    
    elif text == "🔙 Back":
        if nav['state'] == 'BATCH':
            nav.update({'state': 'MAIN', 'batch': None})
            await update.message.reply_text("🏠 মেইন মেনু:", reply_markup=get_main_keyboard())
        elif nav['state'] == 'PLATFORM':
            nav.update({'state': 'BATCH', 'plat': None})
            await update.message.reply_text("📚 ব্যাচ নির্বাচন:", reply_markup=get_batch_keyboard())
        elif nav['state'] == 'SUBJECT':
            nav.update({'state': 'PLATFORM', 'sub': None})
            await update.message.reply_text(f"🏫 {nav['batch'].upper()} প্ল্যাটফর্ম:", reply_markup=get_platform_keyboard())
        elif nav['state'] == 'CYCLE':
            nav.update({'state': 'SUBJECT'})
            await update.message.reply_text(f"🗂 {nav['plat'].upper()} সাবজেক্ট:", reply_markup=get_subject_keyboard(nav['plat']))
        return
    
    if text == "👤 প্রোফাইল":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                pts = row[0] if row else 0.0
            
            async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status='active'", (user_id,)) as cursor:
                ref_count = (await cursor.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM user_access WHERE user_id = ? AND used = 1", (user_id,)) as cursor:
                course_count = (await cursor.fetchone())[0]
        
        msg = (
            f"👤 **প্রোফাইল ড্যাশবোর্ড**\n\n"
            f"🆔 আইডি: `{user_id}`\n"
            f"👑 নাম: {update.effective_user.full_name}\n"
            f"💰 পয়েন্ট: {pts:.2f}\n"
            f"👥 রেফারেল: {ref_count} জন\n"
            f"📚 কোর্স: {course_count} টি\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    elif text == "🏆 লিডারবোর্ড":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT user_id, full_name, points FROM users ORDER BY points DESC LIMIT 10"
            ) as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await update.message.reply_text("📊 এখনও কোনো ডেটা নেই!")
            return
        
        msg = "🏆 **টপ ১০ লিডারবোর্ড**\n━━━━━━━━━━━━━━━━\n"
        for idx, (uid, name, pts) in enumerate(rows, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            msg += f"{medal} {name[:20]} - {pts:.1f} pts\n"
        
        await update.message.reply_text(msg)
    
    elif text == "🔗 রেফারেল লিংক":
        ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        await update.message.reply_text(
            f"🔗 **আপনার রেফারেল লিংক:**\n\n`{ref_link}`\n\n📌 প্রতি রেফারেলে পাবেন ৫ পয়েন্ট!",
            parse_mode="Markdown"
        )
    
    elif text == "💬 সাপোর্ট":
        await update.message.reply_text("💬 **সাপোর্ট ডেস্ক**\n\nআপনার সমস্যা লিখুন:")
        return SUPPORT_MSG
    
    elif text == "📂 সকল কোর্সসমূহ":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT course_key, course_name FROM courses") as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await update.message.reply_text("📂 কোনো কোর্স পাওয়া যায়নি!")
            return
        
        msg = "📋 **সকল কোর্সসমূহ:**\n\n"
        for idx, (key, name) in enumerate(rows, 1):
            msg += f"{idx}. 📘 {name} (`{key}`)\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    elif text == "📚 আমার কোর্স":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT c.course_key, c.course_name FROM user_access ua JOIN courses c ON ua.course_key = c.course_key WHERE ua.user_id = ? AND ua.used = 1",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await update.message.reply_text("📂 আপনি এখনও কোনো কোর্স আনলক করেননি!")
            return
        
        msg = "🎓 **আপনার কোর্সসমূহ:**\n\n"
        for idx, (key, name) in enumerate(rows, 1):
            msg += f"{idx}. 📘 {name}\n"
        
        await update.message.reply_text(msg)
    
    elif text == "🛒 কোর্স কিনুন":
        cost = await get_course_cost()
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                current_points = row[0] if row else 0.0
                
        if current_points < cost:
            await update.message.reply_text(
                f"❌ **আপনার পর্যাপ্ত পয়েন্ট নেই!**\n\n"
                f"• কোর্স কিনতে প্রয়োজন: `{cost:.1f}` পয়েন্ট\n"
                f"• আপনার বর্তমান পয়েন্ট: `{current_points:.1f}` পয়েন্ট\n\n"
                f"📌 অনুগ্রহ করে রেফার করে পর্যাপ্ত পয়েন্ট অর্জন করুন!"
            )
            return
            
        nav['state'] = 'BATCH'
        await update.message.reply_text("📚 **ব্যাচ নির্বাচন:**", reply_markup=get_batch_keyboard())
    
    elif text in ["📚 HSC 27", "📚 HSC 28"]:
        nav['state'] = 'PLATFORM'
        nav['batch'] = "hsc27" if "27" in text else "hsc28"
        await update.message.reply_text(f"🏫 **{nav['batch'].upper()} প্ল্যাটফর্ম:**", reply_markup=get_platform_keyboard())
    
    elif text in ["🔹 ACS", "🔹 BP", "🔹 UDVAS"]:
        nav['state'] = 'SUBJECT'
        nav['plat'] = text.split(" ")[1].lower()
        await update.message.reply_text(f"🗂 **{nav['plat'].upper()} সাবজেক্ট:**", reply_markup=get_subject_keyboard(nav['plat']))
    
    elif text in ["🧪 Physics", "📚 Physics"]:
        nav['state'] = 'CYCLE'
        nav['sub'] = "phy"
        await update.message.reply_text(f"🔄 **Physics সাইকেল:**", reply_markup=get_cycle_keyboard("Physics"))
    
    elif text in ["🧪 Chemistry", "📚 Chemistry"]:
        nav['state'] = 'CYCLE'
        nav['sub'] = "chem"
        await update.message.reply_text(f"🔄 **Chemistry সাইকেল:**", reply_markup=get_cycle_keyboard("Chemistry"))
    
    elif text in ["📐 Math", "📚 Math"]:
        nav['state'] = 'CYCLE'
        nav['sub'] = "math"
        await update.message.reply_text(f"🔄 **Math সাইকেল:**", reply_markup=get_cycle_keyboard("Math"))
    
    elif text in ["🧬 Biology", "📚 Biology"]:
        nav['state'] = 'CYCLE'
        nav['sub'] = "bio"
        await update.message.reply_text(f"🔄 **Biology সাইকেল:**", reply_markup=get_cycle_keyboard("Biology"))
    
    elif text == "📝 EBI":
        nav['state'] = 'CYCLE'
        nav['sub'] = "ebi"
        await update.message.reply_text(f"🔄 **EBI সাইকেল:**", reply_markup=get_cycle_keyboard("EBI"))
    
    elif nav['state'] == 'CYCLE' and text not in ["🔙 Back", "🏠 Main Menu"]:
        cycle_slug = text.lower().replace(" ", "")
        
        if nav['sub'] == "ebi":
            course_key = f"{nav['batch']}_{nav['plat']}_ebi_link"
        else:
            course_key = f"{nav['batch']}_{nav['plat']}_{nav['sub']}_{cycle_slug}"
        
        cost = await get_course_cost()
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT used FROM user_access WHERE user_id = ? AND course_key = ?", (user_id, course_key)) as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                if existing[0] == 1:
                    await update.message.reply_text(
                        "⚠️ **আপনি ইতিমধ্যে এই কোর্সে জয়েন করেছেন!**\n\n"
                        "📌 এই লিংকটি এক্সপায়ার হয়ে গেছে।\n"
                        "আপনি এটি আর ব্যবহার করতে পারবেন না।"
                    )
                    return
                else:
                    await update.message.reply_text(
                        "⏳ **আপনার জন্য ইতিমধ্যে একটি লিংক তৈরি করা হয়েছে!**\n\n"
                        "📌 দয়া করে আপনার ইনবক্স চেক করুন।"
                    )
                    return
            
            async with db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)) as cursor:
                pts_row = await cursor.fetchone()
                current_points = pts_row[0] if pts_row else 0.0
                
            if current_points < cost:
                await update.message.reply_text(
                    f"❌ **দুঃখিত! курсটি কিনতে আপনার পর্যাপ্ত পয়েন্ট নেই।**\n\n"
                    f"• কোর্স কিনতে প্রয়োজন: `{cost:.1f}` পয়েন্ট\n"
                    f"• আপনার বর্তমান পয়েন্ট: `{current_points:.1f}` পয়েন্ট"
                )
                return

            async with db.execute("SELECT course_name, image_id, info_text, channel_id FROM courses WHERE course_key = ?", (course_key,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            await update.message.reply_text(
                f"❌ এই কোর্সটি এখনও আপলোড করা হয়নি!\n\n📌 কোর্স কি: `{course_key}`"
            )
            return
        
        c_name, img_id, info, channel_id = row
        final_link = None
        
        try:
            bot_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ বট চ্যানেলের এডমিন নয়!")
                return
            
            invite_link_obj = await context.bot.create_chat_invite_link(chat_id=channel_id, creates_join_request=True)
            final_link = invite_link_obj.invite_link
            
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (cost, user_id))
                await db.execute("INSERT INTO user_access (user_id, course_key, invite_link, used) VALUES (?, ?, ?, ?)", (user_id, course_key, final_link, 0))
                await db.commit()
            
            await update.message.reply_text(
                f"✅ **আপনার ইউজার-স্পেসিফিক লিংক তৈরি হয়েছে!**\n\n"
                f"📚 **কোর্স:** {c_name}\n"
                f"💰 **পয়েন্ট কাটা হয়েছে:** {cost:.1f} point\n\n"
                f"⚠️ **গুরুত্বপূর্ণ:**\n"
                f"• এই লিংক শুধুমাত্র **আপনি** ব্যবহার করতে পারবেন\n"
                f"• অন্য কাউকে দিলে কাজ করবে না ❌\n"
                f"• **একবার ব্যবহার করলেই** এক্সপায়ার হয়ে যাবে\n\n"
                f"✅ নিচের বাটনে ক্লিক করে জয়েন করুন:"
            )
            
        except Exception as e:
            logger.error(f"Link Error: {e}")
            await update.message.reply_text(f"❌ লিংক তৈরি করতে ব্যর্থ: {e}")
            final_link = None
        
        caption = f"📚 **{c_name}**\n\n📝 **ইনফো:**\n{info}\n\n⚠️ এই লিংক শুধুমাত্র আপনার জন্য!"
        keyboard = []
        if final_link:
            keyboard.append([InlineKeyboardButton("🚀 Join Now", url=final_link)])
        else:
            keyboard.append([InlineKeyboardButton("❌ লিংক তৈরি করা যায়নি", callback_data="error")])
        
        if img_id:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img_id, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    return ConversationHandler.END

async def handle_support_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return ConversationHandler.END
    
    user = update.effective_user
    admin_msg = (
        f"📩 **নতুন সাপোর্ট মেসেজ**\n\n"
        f"👤 ইউজার: {user.full_name}\n"
        f"🆔 আইডি: `{user.id}`\n"
        f"📝 বার্তা: {update.message.text}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
        await update.message.reply_text("✅ আপনার বার্তা এডমিনের কাছে পাঠানো হয়েছে!")
    except Exception as e:
        logger.error(f"Support Error: {e}")
        await update.message.reply_text("❌ সাময়িক ত্রুটি!")
    return ConversationHandler.END

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_user_joined(context, query.from_user.id):
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(chat_id=query.message.chat_id, text="✅ ভেরিফিকেশন সফল!", reply_markup=get_main_keyboard())
    else:
        await query.message.reply_text("❌ আপনি এখনও জয়েন করেননি!")

async def auto_approve_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_join_request = update.chat_join_request
    user_id = chat_join_request.from_user.id
    
    if chat_join_request.invite_link and hasattr(chat_join_request.invite_link, 'invite_link'):
        invite_link = chat_join_request.invite_link.invite_link
    else:
        try:
            await chat_join_request.decline()
        except:
            pass
        return

    invite_link = invite_link.strip()
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id, course_key FROM user_access WHERE invite_link = ? AND used = 0", (invite_link,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                try:
                    await chat_join_request.decline()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ **এই লিংকটি বৈধ নয়!**\n\n• লিংকটি ইতিমধ্যে ব্যবহার করা হয়েছে\n• অথবা এটি মেয়াদ উত্তীর্ণ\n\n🔄 নতুন লিংক পেতে আবার কোর্স কিনুন।"
                )
                return
            
            original_user_id = row[0]
            if original_user_id != user_id:
                try:
                    await chat_join_request.decline()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ **এই লিংকটি আপনার জন্য নয়!**\n\n• এই লিংক অন্য একজন ইউজারের জন্য তৈরি করা হয়েছে\n• আপনি এটি ব্যবহার করতে পারবেন না\n\n🔄 আপনার নিজের লিংক পেতে কোর্স কিনুন।"
                )
                return
            
            await chat_join_request.approve()
            await db.execute("UPDATE user_access SET used = 1 WHERE user_id = ? AND invite_link = ?", (user_id, invite_link))
            await db.commit()
        
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ **জয়েন রিকোয়েস্ট অ্যাপ্রুভ করা হয়েছে!**\n\n🎉 আপনি এখন চ্যানেলে যুক্ত হয়েছেন।\n\n⚠️ **এই লিংকটি এখন এক্সপায়ার হয়ে গেছে!**\nআপনি এটি আর ব্যবহার করতে পারবেন না।"
        )
    except Exception as e:
        logger.error(f"Approve Error: {e}")
        try:
            await chat_join_request.decline()
        except:
            pass

# ==================== এডমিন প্যানেল ====================

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cost = await get_course_cost()
    msg = (
        "🛠 **এডমিন কন্ট্রোল প্যানেল**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚙️ **কোর্স প্রাইস কনফিগ:**\n"
        f"• বর্তমান কোর্স প্রাইস: `{cost:.1f}` পয়েন্ট\n"
        f"👉 পরিবর্তন করতে: `/needpoint <পয়েন্ট>`\n\n"
        "📚 **কোর্স ম্যানেজমেন্ট:**\n"
        "➕ /add_course - নতুন কোর্স যোগ\n"
        "✏️ /edit_course - কোর্স এডিট\n"
        "🗑 /delete_course course_key - কোর্স ডিলিট\n\n"
        "👥 **ইউজার ম্যানেজমেন্ট:**\n"
        "📊 /users - সব ইউজারের তালিকা\n"
        "💰 /add_points user_id amount - পয়েন্ট যোগ\n"
        "🔗 /referrals - কে কাকে রেফার করেছে তা দেখুন\n"
        "🎓 /user_courses user_id - ইউজারের কেনা কোর্স দেখুন\n\n"
        "📢 **ব্রডকাস্ট:**\n"
        "📨 /broadcast message - সবাইকে মেসেজ"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_needpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ ফরম্যাট: `/needpoint amount` (যেমন: `/needpoint 15`)")
        return
    try:
        new_cost = float(context.args[0])
        if new_cost < 0:
            await update.message.reply_text("❌ পয়েন্ট অবশ্যই পজিটিভ সংখ্যা হতে হবে!")
            return
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('course_cost', ?)", (str(new_cost),))
            await db.commit()
        await update.message.reply_text(f"✅ কোর্স ক্রয়ের জন্য প্রয়োজনীয় পয়েন্ট সফলভাবে পরিবর্তন করা হয়েছে!\n🎯 এখন থেকে প্রতিটি কোর্স কিনতে `{new_cost:.1f}` পয়েন্ট লাগবে।")
    except ValueError:
        await update.message.reply_text("❌ অনুগ্রহ করে একটি সঠিক সংখ্যা দিন।")

async def view_user_courses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ ফরম্যাট: `/user_courses user_id`")
        return
    try:
        target_user_id = int(context.args[0])
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT full_name FROM users WHERE user_id = ?", (target_user_id,)) as cursor:
                user_row = await cursor.fetchone()
                user_name = user_row[0] if user_row else "Unknown User"
            async with db.execute("SELECT c.course_name, c.course_key, ua.used FROM user_access ua JOIN courses c ON ua.course_key = c.course_key WHERE ua.user_id = ?", (target_user_id,)) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await update.message.reply_text(f"📂 ইউজার `{target_user_id}` ({user_name}) কোনো কোর্স আনলক করেননি।")
            return
        msg = f"🎓 **ইউজার কোর্স হিস্টোরি**\n👤 নাম: {user_name}\n🆔 আইডি: `{target_user_id}`\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        for idx, (c_name, c_key, used) in enumerate(rows, 1):
            status = "✅ জয়েন করেছে" if used == 1 else "⏳ লিংক এখনও ব্যবহৃত হয়নি"
            msg += f"{idx}. 📘 {c_name} (`{c_key}`)\n   └ স্ট্যাটাস: {status}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ অনুগ্রহ করে সঠিক ইউজার আইডি দিন।")

async def view_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        query = "SELECT r.referrer_id, u1.full_name, COUNT(r.referee_id) as total FROM referrals r JOIN users u1 ON r.referrer_id = u1.user_id WHERE r.status = 'active' GROUP BY r.referrer_id ORDER BY total DESC"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
    if not rows:
        await update.message.reply_text("📊 এখনও পর্যন্ত কোনো রেফারাল ডেটা রেকর্ড করা হয়নি!")
        return
    msg = "🔗 **রেফারাল ট্র্যাকিং তালিকা**\n━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, (ref_id, name, total) in enumerate(rows, 1):
        msg += f"{idx}. {name[:15]} (`{ref_id}`) ➡️ {total} জন\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def start_add_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("🆕 **কোর্স যোগ করুন**\n\nফরম্যাট: `course_key | কোর্সের নাম`\nউদাহরণ: `hsc27_acs_phy_cycle1 | HSC 27 ACS Physics Cycle 1`")
    return ADD_KEY

async def save_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "|" not in update.message.text:
        await update.message.reply_text("❌ ভুল ফরম্যাট! আবার চেষ্টা করুন।")
        return ADD_KEY
    parts = update.message.text.split("|")
    ckey = parts[0].strip().lower()
    cname = parts[1].strip()
    context.user_data['temp_course'] = {'key': ckey, 'name': cname}
    await update.message.reply_text(f"✅ কী: `{ckey}`\n✅ নাম: {cname}\n\nএখন ইনফো ও চ্যানেল আইডি দিন:\nফরম্যাট: `ইনফো | চ্যানেল_আইডি`")
    return ADD_INFO

async def save_add_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "|" not in update.message.text:
        await update.message.reply_text("❌ ভুল ফরম্যাট! আবার চেষ্টা করুন।")
        return ADD_INFO
    parts = update.message.text.split("|")
    info = parts[0].strip()
    channel = parts[1].strip()
    context.user_data['temp_course']['info'] = info
    context.user_data['temp_course']['channel'] = channel
    await update.message.reply_text("📸 এখন কোর্সের জন্য একটি ছবি পাঠান (অথবা `/skip` দিন):")
    return ADD_IMG

async def save_add_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['temp_course']
    img_id = update.message.photo[-1].file_id if update.message.photo else None
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO courses (course_key, course_name, image_id, info_text, channel_id) VALUES (?, ?, ?, ?, ?)", (data['key'], data['name'], img_id, data['info'], data['channel']))
        await db.commit()
    await update.message.reply_text(f"✅ **{data['name']}** কোর্সটি যোগ করা হয়েছে!")
    return ConversationHandler.END

async def skip_add_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['temp_course']
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO courses (course_key, course_name, image_id, info_text, channel_id) VALUES (?, ?, ?, ?, ?)", (data['key'], data['name'], None, data['info'], data['channel']))
        await db.commit()
    await update.message.reply_text(f"✅ **{data['name']}** কোর্সটি (ছবি ছাড়া) যোগ করা হয়েছে!")
    return ConversationHandler.END

async def start_edit_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("✏️ কোন কোর্স এডিট করবেন? কোর্স কি দিন:")
    return EDIT_KEY

async def save_edit_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ckey = update.message.text.strip().lower()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT course_name FROM courses WHERE course_key = ?", (ckey,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        await update.message.reply_text("❌ এই কোর্সটি পাওয়া যায়নি! আবার চেষ্টা করুন:")
        return EDIT_KEY
    context.user_data['edit_ckey'] = ckey
    keyboard = [
        [InlineKeyboardButton("📝 নাম", callback_data="edit_name"), InlineKeyboardButton("📄 ইনফো", callback_data="edit_info")],
        [InlineKeyboardButton("🔗 চ্যানেল", callback_data="edit_chan"), InlineKeyboardButton("🖼 ছবি", callback_data="edit_img")]
    ]
    await update.message.reply_text(f"📘 কোর্স: **{row[0]}**\n\nকী এডিট করতে চান?", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_FIELD

async def handle_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edit_", "")
    context.user_data['edit_field'] = field
    msgs = {'name': "📝 নতুন নাম দিন:", 'info': "📝 নতুন ইনফো দিন:", 'chan': "🔗 নতুন চ্যানেল আইডি দিন:", 'img': "🖼 নতুন ছবি পাঠান:"}
    await query.message.reply_text(msgs.get(field, "দয়া করে দিন:"))
    return EDIT_VALUE

async def save_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ckey = context.user_data['edit_ckey']
    field = context.user_data['edit_field']
    async with aiosqlite.connect(DB_NAME) as db:
        if field == "name":
            await db.execute("UPDATE courses SET course_name = ? WHERE course_key = ?", (update.message.text.strip(), ckey))
        elif field == "info":
            await db.execute("UPDATE courses SET info_text = ? WHERE course_key = ?", (update.message.text.strip(), ckey))
        elif field == "chan":
            await db.execute("UPDATE courses SET channel_id = ? WHERE course_key = ?", (update.message.text.strip(), ckey))
        elif field == "img":
            if not update.message.photo:
                await update.message.reply_text("❌ এটি ফটো নয়!")
                return ConversationHandler.END
            file_id = update.message.photo[-1].file_id
            await db.execute("UPDATE courses SET image_id = ? WHERE course_key = ?", (file_id, ckey))
        await db.commit()
    await update.message.reply_text("✅ কোর্স আপডেট করা হয়েছে!")
    return ConversationHandler.END

async def delete_course_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        await update.message.reply_text("❌ ফরম্যাট: `/delete_course course_key`")
        return
    ckey = context.args[0].lower()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM courses WHERE course_key = ?", (ckey,))
        await db.execute("DELETE FROM user_access WHERE course_key = ?", (ckey,))
        await db.commit()
    await update.message.reply_text(f"🗑 `{ckey}` কোর্সটি ডিলিট করা হয়েছে!")

async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute("SELECT user_id, full_name, points FROM users ORDER BY points DESC LIMIT 20") as cursor:
            rows = await cursor.fetchall()
    msg = f"👥 **মোট ইউজার:** {total}\n\n"
    for idx, (uid, name, pts) in enumerate(rows, 1):
        msg += f"{idx}. {name[:20]} - {pts:.1f} pts\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or len(context.args) < 2:
        await update.message.reply_text("❌ ফরম্যাট: `/add_points user_id amount`")
        return
    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
        await update.message.reply_text(f"✅ ইউজার {user_id} পেয়েছে {amount} পয়েন্ট!")
    except:
        await update.message.reply_text("❌ ভুল ইনপুট!")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        await update.message.reply_text("❌ ফরম্যাট: `/broadcast your message`")
        return
    msg = " ".join(context.args)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    sent = 0
    for (uid,) in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **ব্রডকাস্ট:**\n\n{msg}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ {sent} জনকে মেসেজ পাঠানো হয়েছে!")

# --- মেইন ফাংশন ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db
    
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add_course", start_add_course)],
        states={
            ADD_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_add_key)],
            ADD_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_add_info)],
            ADD_IMG: [MessageHandler(filters.PHOTO, save_add_img), CommandHandler("skip", skip_add_img)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edit_course", start_edit_course)],
        states={
            EDIT_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_key)],
            EDIT_FIELD: [CallbackQueryHandler(handle_edit_field, pattern="^edit_")],
            EDIT_VALUE: [MessageHandler(filters.TEXT | filters.PHOTO, save_edit_value)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["💬 সাপোর্ট"]), handle_text_buttons)],
        states={SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_input)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    # CRITICAL FIX: সমস্ত কমান্ড হ্যান্ডলারগুলোকে সবার উপরে রাখা হলো
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CommandHandler("needpoint", set_needpoint))
    app.add_handler(CommandHandler("user_courses", view_user_courses))
    app.add_handler(CommandHandler("referrals", view_referrals))
    app.add_handler(CommandHandler("delete_course", delete_course_command))
    app.add_handler(CommandHandler("users", users_list))
    app.add_handler(CommandHandler("add_points", add_points))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # কনভারসেশন হ্যান্ডলারসমূহ
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    app.add_handler(support_conv)
    
    # অন্যান্য ইভেন্ট ও বাটন হ্যান্ডলার
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(ChatJoinRequestHandler(auto_approve_join_request))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    
    print("🚀 Combo Bot Started Successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
