import re, sys, pathlib

p = pathlib.Path("assistant.py")
src = p.read_text(encoding="utf-8")

pattern = re.compile(
    r"def _make_openai_client\([\s\S]*?^\s*return client\s*\n",
    re.MULTILINE
)

replacement = r'''def _make_openai_client() -> OpenAI:
    """
    Создаёт OpenAI-клиент с httpx и прокси.
    Совместимо с httpx, где нет параметра proxies в Client.__init__.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")

    # Берём прокси из ENV (HTTPS_PROXY приоритетнее)
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")

    # Транспорт с прокси (если есть)
    transport = httpx.HTTPTransport(proxy=proxy) if proxy else httpx.HTTPTransport()

    # Важно: прокси задаём через transport, а не через Client(proxies=...)
    http_client = httpx.Client(
        timeout=TIMEOUT,
        transport=transport,
        headers={"User-Agent": "coffee-bot-assistant/1.0"},
    )

    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE.rstrip("/"),
        http_client=http_client,
    )
    return client
'''

new, n = pattern.subn(replacement, src, count=1)
if n != 1:
    print("PATCH ERROR: не нашёл ровно одну функцию _make_openai_client() для замены.", file=sys.stderr)
    sys.exit(1)

# делаем бэкап
bak = p.with_suffix(".py.bak")
bak.write_text(src, encoding="utf-8")

p.write_text(new, encoding="utf-8")
print("OK: assistant.py пропатчен. Бэкап:", bak)
