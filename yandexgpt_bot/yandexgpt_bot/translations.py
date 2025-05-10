"""
Translation module for the YandexGPT bot interface.
Provides multilingual text for bot messages.
"""
from .config import LANGUAGE
import yaml

# Translation dictionary
TRANSLATIONS = {
    # Admin panel
    "admin_panel_title": {
        "english": "Admin Panel - YandexGPT",
        "russian": "Панель администратора - YandexGPT"
    },
    "admin_panel_welcome": {
        "english": "Choose an action from the menu below:",
        "russian": "Выберите действие из меню ниже:"
    },
    "btn_unlimited_users": {
        "english": "👥 Unlimited Users",
        "russian": "👥 Пользователи с безлимитом"
    },
    "btn_statistics": {
        "english": "📊 Statistics",
        "russian": "📊 Статистика"
    },
    "btn_add_user": {
        "english": "➕ Add User",
        "russian": "➕ Добавить пользователя"
    },
    "btn_remove_user": {
        "english": "➖ Remove User",
        "russian": "➖ Удалить пользователя"
    },
    "btn_language": {
        "english": "🌐 Change Language",
        "russian": "🌐 Сменить язык"
    },
    "btn_back": {
        "english": "« Back",
        "russian": "« Назад"
    },
    "btn_back_to_admin": {
        "english": "« Back to Admin Panel",
        "russian": "« Назад к админке"
    },
    "access_denied": {
        "english": "⛔ You do not have permission to access the admin panel.",
        "russian": "⛔ У вас нет прав для доступа к панели администратора."
    },

    # Language settings
    "language_title": {
        "english": "🌐 Language Settings",
        "russian": "🌐 Настройки языка"
    },
    "language_description": {
        "english": "Select the interface language:",
        "russian": "Выберите язык интерфейса:"
    },
    "btn_english": {
        "english": "🇬🇧 English",
        "russian": "🇬🇧 Английский"
    },
    "btn_russian": {
        "english": "🇷🇺 Russian",
        "russian": "🇷🇺 Русский"
    },
    "language_changed": {
        "english": "✅ Language changed to English.",
        "russian": "✅ Язык изменен на Русский."
    },

    # Add user
    "add_user_title": {
        "english": "➕ Add User with Unlimited Access",
        "russian": "➕ Добавление пользователя с безлимитом"
    },
    "add_user_description": {
        "english": "Please enter the chat ID of the user you want to grant unlimited access to.",
        "russian": "Пожалуйста, отправьте ID чата пользователя, которому нужно предоставить безлимитный доступ."
    },
    "add_user_share_contact": {
        "english": "You can also share a contact to add them.",
        "russian": "Вы также можете поделиться контактом для добавления пользователя."
    },
    "contact_no_userid": {
        "english": "⚠️ This contact doesn't have a Telegram user ID. Make sure the contact is using Telegram.",
        "russian": "⚠️ У этого контакта нет ID пользователя Telegram. Убедитесь, что контакт использует Telegram."
    },
    "user_not_found": {
        "english": "⚠️ User with ID {user_id} not found in the database.",
        "russian": "⚠️ Пользователь с ID {user_id} не найден в базе."
    },
    "confirm_add_user": {
        "english": "⚠️ Are you sure you want to add user with ID {user_id} to the unlimited list?",
        "russian": "⚠️ Вы уверены, что хотите добавить пользователя с ID {user_id} в список безлимитных?"
    },
    "btn_yes": {
        "english": "✅ Yes",
        "russian": "✅ Да"
    },
    "btn_no": {
        "english": "❌ No",
        "russian": "❌ Нет"
    },
    "invalid_id": {
        "english": "⚠️ Invalid chat ID. Please enter a numeric ID.",
        "russian": "⚠️ Некорректный ID чата. Пожалуйста, введите числовой ID."
    },
    "user_added": {
        "english": "✅ User with ID `{user_id}` has been successfully added to the unlimited list.",
        "russian": "✅ Пользователь с ID `{user_id}` успешно добавлен в список безлимитных."
    },
    "add_user_error": {
        "english": "⚠️ Error adding user: {error}",
        "russian": "⚠️ Ошибка при добавлении пользователя: {error}"
    },

    # Remove user
    "remove_user_title": {
        "english": "➖ Remove User from Unlimited Access",
        "russian": "➖ Удаление пользователя с безлимитом"
    },
    "remove_user_description": {
        "english": "Please enter the chat ID of the user whose unlimited access you want to revoke.",
        "russian": "Пожалуйста, отправьте ID чата пользователя, у которого нужно отозвать безлимитный доступ."
    },
    "user_not_unlimited": {
        "english": "⚠️ User with ID {user_id} does not have unlimited access.",
        "russian": "⚠️ Пользователь с ID {user_id} не имеет безлимитного доступа."
    },
    "confirm_remove_user": {
        "english": "⚠️ Are you sure you want to remove user with ID {user_id} from the unlimited list?",
        "russian": "⚠️ Вы уверены, что хотите удалить пользователя с ID {user_id} из списка безлимитных?"
    },
    "user_removed": {
        "english": "✅ User with ID `{user_id}` has been successfully removed from the unlimited list.",
        "russian": "✅ Пользователь с ID `{user_id}` успешно удален из списка безлимитных."
    },
    "remove_user_error": {
        "english": "⚠️ Error removing user: {error}",
        "russian": "⚠️ Ошибка при удалении пользователя: {error}"
    },

    # Unlimited users list
    "unlimited_users_title": {
        "english": "👥 Users with Unlimited Access",
        "russian": "👥 Пользователи с безлимитом"
    },
    "unlimited_users_empty": {
        "english": "No users with unlimited access.",
        "russian": "Список пуст."
    },
    "loading_users": {
        "english": "Loading users, please wait...",
        "russian": "Загрузка пользователей, пожалуйста, подождите..."
    },
    "remove_user_select": {
        "english": "Select a user to remove from unlimited access by clicking on the button or entering their number from the list below:",
        "russian": "Выберите пользователя для удаления из безлимитного доступа, нажав на кнопку или введя его номер из списка ниже:"
    },
    "invalid_selection": {
        "english": "⚠️ Invalid selection. Please enter a valid number from the list.",
        "russian": "⚠️ Некорректный выбор. Пожалуйста, введите корректный номер из списка."
    },
    "general_error": {
        "english": "⚠️ An error occurred: {error}",
        "russian": "⚠️ Произошла ошибка: {error}"
    },

    # Statistics
    "stats_title": {
        "english": "📊 Bot Statistics",
        "russian": "📊 Статистика бота"
    },
    "stats_total_chats": {
        "english": "• Total chats: {count}",
        "russian": "• Всего чатов: {count}"
    },
    "stats_unlimited_chats": {
        "english": "• Unlimited chats: {count}",
        "russian": "• Чатов с безлимитом: {count}"
    },
    "stats_total_messages": {
        "english": "• Total messages: {count}",
        "russian": "• Всего сообщений: {count}"
    },
    "stats_today_requests": {
        "english": "• Requests today: {count}",
        "russian": "• Запросов сегодня: {count}"
    },
    "stats_today_images": {
        "english": "• Images today: {count}",
        "russian": "• Изображений сегодня: {count}"
    },
    "stats_basic": {
        "english": "• Unlimited chats: {count}\n• Other statistics not available without DB",
        "russian": "• Чатов с безлимитом: {count}\n• Другая статистика недоступна без БД"
    },
    "stats_error": {
        "english": "⚠️ Error retrieving statistics: {error}",
        "russian": "⚠️ Ошибка при получении статистики: {error}"
    },
    "stats_tokens_title": {
        "english": "Token Statistics:",
        "russian": "Статистика токенов:"
    },
    "stats_total_tokens": {
        "english": "• Total tokens: {count}",
        "russian": "• Всего токенов: {count}"
    },
    "stats_today_tokens": {
        "english": "• Tokens today: {count}",
        "russian": "• Токенов сегодня: {count}"
    },
    "stats_24h_tokens": {
        "english": "• Tokens in last 24h: {count}",
        "russian": "• Токенов за 24ч"
    },
    "chart_requests_24h": {
        "english": "User activity chart (requests in last 24h)",
        "russian": "График активности пользователей (запросы за 24ч)"
    },
    "chart_tokens_24h": {
        "english": "Token usage per user (last 24h)",
        "russian": "Использование токенов по пользователям (за 24ч)"
    },
    "chart_tokens_7days": {
        "english": "Token usage over the last 7 days",
        "russian": "Использование токенов за последние 7 дней"
    },
    "chart_requests_x": {
        "english": "Requests in 24h",
        "russian": "Запросов за 24ч"
    },
    "chart_requests_title": {
        "english": "User activity over the last 24 hours",
        "russian": "Активность пользователей за последние 24 часа"
    },
    "chart_tokens_x": {
        "english": "Tokens in 24h",
        "russian": "Токенов за 24ч"
    },
    "chart_tokens_title": {
        "english": "Token usage per user in the last 24 hours",
        "russian": "Использование токенов по пользователям за 24 часа"
    },
    "chart_date": {
        "english": "Date",
        "russian": "Дата"
    },
    "chart_tokens": {
        "english": "Tokens",
        "russian": "Токены"
    },
    "chart_7days_title": {
        "english": "Token usage over the last 7 days",
        "russian": "Использование токенов за последние 7 дней"
    }
}


def get_text(key, lang=None, **format_args):
    """
    Retrieve translation text by key.

    Args:
        key (str): Translation key.
        lang (str, optional): Language code. If None, uses default from config.
        **format_args: Arguments for string formatting.

    Returns:
        str: Translated text or key if not found.
    """
    if lang is None:
        lang = LANGUAGE

    # Fallback to English if unsupported language
    if lang not in ["english", "russian"]:
        lang = "english"

    # Attempt to get translation
    translation = TRANSLATIONS.get(key, {}).get(lang)

    # Fallback to English or key
    if translation is None:
        translation = TRANSLATIONS.get(key, {}).get("english") or key

    return translation.format(**format_args) if format_args else translation


def get_current_language():
    """
    Load current interface language from config file.

    Returns:
        str: Current language code.
    """
    return LANGUAGE
