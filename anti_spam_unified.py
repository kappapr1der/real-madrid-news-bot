import os
import logging

# 🔹 Файл для хранения уже отправленных ссылок (дайджест + breaking)
SENT_FILE = "sent_links_unified.txt"
os.makedirs("logs", exist_ok=True)

# Лог
LOG_FILE = "logs/anti_spam.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

# Загрузка ссылок в память
def load_sent_links():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

sent_links = load_sent_links()

# Сохранение ссылок в файл
def save_sent_links():
    global sent_links
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        for link in sorted(sent_links):
            f.write(link + "\n")

# Проверка, отправляли ли уже
def is_sent(link: str) -> bool:
    global sent_links
    return link in sent_links

# Добавление новой ссылки
def mark_as_sent(link: str):
    global sent_links
    if link not in sent_links:
        sent_links.add(link)
        save_sent_links()
        logging.info(f"Ссылка добавлена в антиспам: {link}")
    else:
        logging.info(f"Ссылка уже была в антиспаме: {link}")
        
# Очистка всех ссылок (если нужно сбросить)
def clear_sent_links():
    global sent_links
    sent_links.clear()
    save_sent_links()
    logging.info("Все ссылки в антиспаме очищены.")

if __name__ == "__main__":
    print("Anti-spam unified module ready.")
    print(f"Загружено ссылок: {len(sent_links)}")
