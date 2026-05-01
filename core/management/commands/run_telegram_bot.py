import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from django.core.management.base import BaseCommand
from core.models import Plan, UserService, PaymentSettings, PaymentReceipt, SystemConfig


MESSAGES = {
    "fa": {
        "start": "سلام! به ربات فروش اشتراک خوش آمدید.",
        "menu": "یکی از گزینه‌ها را انتخاب کنید:",
        "language": "زبان شما فارسی است.",
        "plans": "پلن‌های فعال:",
        "no_plans": "هیچ پلن فعالی وجود ندارد.",
        "pay_info": "لطفا مبلغ پلن را کارت زیر واریز کنید و عکس رسید را با کپشن receipt:PLAN_ID بفرستید:\n{text}",
        "receipt_ok": "رسید ثبت شد و منتظر تایید ادمین است. ✅",
        "receipt_fail": "فرمت کپشن نادرست است. مثال: receipt:1",
        "my_services": "سرویس‌های شما:",
    },
    "en": {
        "start": "Hello! Welcome to the subscription seller bot.",
        "menu": "Choose an option:",
        "language": "Your language is English.",
        "plans": "Active plans:",
        "no_plans": "No active plans found.",
        "pay_info": "Please transfer payment and send receipt photo with caption receipt:PLAN_ID\n{text}",
        "receipt_ok": "Receipt submitted and waiting admin approval. ✅",
        "receipt_fail": "Invalid caption. Example: receipt:1",
        "my_services": "Your services:",
    },
}


def pick_lang(update: Update) -> str:
    lang = (update.effective_user.language_code or "fa").lower()
    return "fa" if lang.startswith("fa") else "en"


def main_menu(lang: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Plans" if lang == "en" else "🛒 پلن‌ها", callback_data="plans")],
        [InlineKeyboardButton("💳 Bank Transfer" if lang == "en" else "💳 کارت به کارت", callback_data="bank_info")],
        [InlineKeyboardButton("📦 My Services" if lang == "en" else "📦 سرویس‌های من", callback_data="my_services")],
    ])


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = pick_lang(update)
    await update.message.reply_text(MESSAGES[lang]["start"])
    await update.message.reply_text(MESSAGES[lang]["menu"], reply_markup=main_menu(lang))


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = pick_lang(update)
    await update.message.reply_text(MESSAGES[lang]["menu"], reply_markup=main_menu(lang))


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = pick_lang(update)
    await update.message.reply_text(MESSAGES[lang]["language"])


async def receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = pick_lang(update)
    caption = (update.message.caption or "").strip().lower()
    if not caption.startswith("receipt:"):
        await update.message.reply_text(MESSAGES[lang]["receipt_fail"])
        return
    try:
        plan_id = int(caption.split(":", 1)[1])
    except ValueError:
        await update.message.reply_text(MESSAGES[lang]["receipt_fail"])
        return

    plan = Plan.objects.filter(id=plan_id, is_active=True).first()
    if not plan:
        await update.message.reply_text(MESSAGES[lang]["no_plans"])
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    os.makedirs("media/receipts", exist_ok=True)
    local_path = f"media/receipts/tg_{update.effective_user.id}_{photo.file_unique_id}.jpg"
    await file.download_to_drive(local_path)

    PaymentReceipt.objects.create(
        telegram_user_id=update.effective_user.id,
        plan=plan,
        amount=plan.price,
        screenshot=f"receipts/{os.path.basename(local_path)}",
    )
    await update.message.reply_text(MESSAGES[lang]["receipt_ok"])


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = pick_lang(update)
    user_id = update.effective_user.id

    if query.data == "plans":
        plans = Plan.objects.filter(is_active=True)
        if not plans.exists():
            await query.message.reply_text(MESSAGES[lang]["no_plans"])
            return
        rows = [f"{p.id}) {p.name_en} - {p.traffic_gb}GB - {p.price}" for p in plans]
        await query.message.reply_text(MESSAGES[lang]["plans"] + "\n" + "\n".join(rows))
        return

    if query.data == "bank_info":
        s = PaymentSettings.objects.filter(is_active=True).first()
        text = s.bank_transfer_text_fa if (s and lang == "fa") else (s.bank_transfer_text_en if s else "")
        await query.message.reply_text(MESSAGES[lang]["pay_info"].format(text=text))
        return

    if query.data == "my_services":
        services = UserService.objects.filter(telegram_user_id=user_id).order_by("-id")[:10]
        if not services:
            await query.message.reply_text(MESSAGES[lang]["no_plans"])
            return
        text = [MESSAGES[lang]["my_services"]]
        for s in services:
            text.append(f"- {s.plan.name_en} | {s.status} | {s.config_link}")
        await query.message.reply_text("\n".join(text))


class Command(BaseCommand):
    help = "Run Telegram bot in polling mode"

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            cfg = SystemConfig.objects.filter(title="default").first()
            token = cfg.telegram_bot_token if cfg and cfg.telegram_bot_token else ""
        if not token:
            self.stderr.write("TELEGRAM_BOT_TOKEN is required (env or SystemConfig)")
            return

        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("menu", menu_cmd))
        app.add_handler(CommandHandler("language", language_cmd))
        app.add_handler(CallbackQueryHandler(callback_router))
        app.add_handler(MessageHandler(filters.PHOTO, receipt_photo))

        self.stdout.write("Starting Telegram bot polling...")
        app.run_polling(drop_pending_updates=True)
