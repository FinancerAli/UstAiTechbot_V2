from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from locales import t

STATUS_EMOJI = {
    "pending": "\u23f3",
    "confirmed": "\u2705",
    "rejected": "\u274c",
    "cancelled": "\U0001f6ab",
}


ENABLE_TOP_SERVICES = False
ENABLE_SEARCH = False
ENABLE_REVIEWS = False

def main_menu(lang: str = "uz"):
    """
    Generate the main reply keyboard for end users.
    
    Args:
        lang (str): Two-letter language code ("uz" or "ru"). Defaults to "uz".

    Returns:
        ReplyKeyboardMarkup: A keyboard markup with localized button texts.
    """
    if lang == "ru":
        keyboard = [
            [
                KeyboardButton(text="🛍 Услуги"),
                KeyboardButton(text="📦 Мои заказы"),
            ],
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="🌐 Язык"),
            ]
        ]
        
        row_3 = []
        if ENABLE_TOP_SERVICES:
            row_3.append(KeyboardButton(text=t(lang, "btn_top_services")))
        row_3.append(KeyboardButton(text=t(lang, "btn_promos")))
        if row_3:
            keyboard.append(row_3)
            
        keyboard.append([
            KeyboardButton(text=t(lang, "btn_referral")),
            KeyboardButton(text=t(lang, "btn_support")),
        ])
        
        row_5 = []
        if ENABLE_SEARCH:
            row_5.append(KeyboardButton(text=t(lang, "btn_search")))
        row_5.extend([
            KeyboardButton(text="📞 Контакты"),
            KeyboardButton(text=t(lang, "btn_faq")),
        ])
        keyboard.append(row_5)

        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    # Default: Uzbek
    keyboard = [
        [
            KeyboardButton(text="🛍 Xizmatlar"),
            KeyboardButton(text="📦 Buyurtmalarim"),
        ],
        [
            KeyboardButton(text="👤 Profil"),
            KeyboardButton(text="🌐 Til"),
        ]
    ]
    
    row_3 = []
    if ENABLE_TOP_SERVICES:
        row_3.append(KeyboardButton(text=t(lang, "btn_top_services")))
    row_3.append(KeyboardButton(text=t(lang, "btn_promos")))
    if row_3:
        keyboard.append(row_3)
        
    keyboard.append([
        KeyboardButton(text=t(lang, "btn_referral")),
        KeyboardButton(text=t(lang, "btn_support")),
    ])
    
    row_5 = []
    if ENABLE_SEARCH:
        row_5.append(KeyboardButton(text=t(lang, "btn_search")))
    row_5.extend([
        KeyboardButton(text="📞 Aloqa"),
        KeyboardButton(text=t(lang, "btn_faq")),
    ])
    keyboard.append(row_5)

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001f1fa\U0001f1ff O'zbekcha", callback_data="set_lang:uz"),
            InlineKeyboardButton(text="\U0001f1f7\U0001f1fa Русский", callback_data="set_lang:ru"),
        ]
    ])


def categories_keyboard(categories, lang="uz"):
    buttons = []
    for c in categories:
        buttons.append([InlineKeyboardButton(
            text=c["name"],
            callback_data=f"category:{c['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def services_keyboard(services, lang="uz", page: int = 1, total_count: int = 0, query: str = ""):
    cur = t(lang, "currency")
    buttons = []
    for s in services:
        stock_val = s["stock"] if "stock" in s.keys() else None
        stock_text = f" [\U0001f4e6 {stock_val}]" if stock_val is not None else ""
        text_lbl = f"{s['name']}{stock_text} — {s['price']:,} {cur}"
        if dict(s).get("promo_active"):
            text_lbl += f" | 🎁 {s['cashback_percent']}% cashback"
        buttons.append([InlineKeyboardButton(
            text=text_lbl,
            callback_data=f"service:{s['id']}:{page}"
        )])
        
    nav_buttons = []
    q_param = f":{query}" if query else ":"
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{page-1}{q_param}"))
    if total_count > page * 10:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{page+1}{q_param}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
        
    if query:
        buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="back_home")])
    else:
        buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="back_categories")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def service_detail_keyboard(service_id: int, lang="uz", stock: int = -1, back_page: int = 1):
    buttons = []
    if stock > 0 or stock == -1:
        buttons.append([InlineKeyboardButton(text=t(lang, "btn_order"), callback_data=f"order:{service_id}")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"back_services_list:{back_page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard(lang="uz"):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "cancel"))]],
        resize_keyboard=True,
    )


def skip_cancel_keyboard(lang="uz"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_skip"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )


def confirm_order_keyboard(order_id: int, lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_confirm_order"), callback_data=f"confirm_order:{order_id}")],
    ])


def quantity_keyboard(service_id: int, lang="uz"):
    btn_1_text = "1 dona" if lang == "uz" else "1 шт."
    btn_3_text = "3 dona" if lang == "uz" else "3 шт."
    btn_5_text = "5 dona" if lang == "uz" else "5 шт."
    btn_10_text = "10 dona 🔥" if lang == "uz" else "10 шт. 🔥"
    cancel_text = "❌ Bekor qilish" if lang == "uz" else "❌ Отмена"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn_1_text, callback_data=f"qty:{service_id}:1"),
            InlineKeyboardButton(text=btn_3_text, callback_data=f"qty:{service_id}:3"),
            InlineKeyboardButton(text=btn_5_text, callback_data=f"qty:{service_id}:5"),
        ],
        [
            InlineKeyboardButton(text=btn_10_text, callback_data=f"qty:{service_id}:10"),
            InlineKeyboardButton(text=t(lang, "btn_other_qty"), callback_data=f"qty_custom:{service_id}")
        ],
        [InlineKeyboardButton(text=cancel_text, callback_data="cancel_quantity_prompt")]
    ])


def rating_keyboard(order_id: int):
    stars = [InlineKeyboardButton(text="\u2b50" * i, callback_data=f"rate:{order_id}:{i}") for i in range(1, 6)]
    return InlineKeyboardMarkup(inline_keyboard=[stars[:3], stars[3:]])


def bonus_keyboard(lang="uz"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_skip"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )


def contact_keyboard(lang="uz"):
    op_text = t(lang, "btn_support")
    ch_text = "📢 Kanalga o‘tish" if lang == "uz" else "📢 Перейти в канал"
    back_text = t(lang, "btn_back_arrow")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=op_text, url="https://t.me/UstAiTechsupportbot")],
        [InlineKeyboardButton(text=ch_text, url="https://t.me/UstAiTech")],
        [InlineKeyboardButton(text=back_text, callback_data="back_home")]
    ])
