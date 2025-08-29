import re, sys, pathlib

p = pathlib.Path("assistant.py")
if not p.exists():
    print("ERROR: assistant.py not found in current directory", file=sys.stderr)
    sys.exit(1)

src = p.read_text(encoding="utf-8")
orig = src

# 1) ensure `import httpx` exists
if "import httpx" not in src:
    # вставим после блока импортов, встаем после строки 'from typing ...' если есть
    m = re.search(r"^(from\s+typing\s+import[^\n]*\n)", src, re.MULTILINE)
    if m:
        pos = m.end()
        src = src[:pos] + "import httpx\n" + src[pos:]
    else:
        # иначе после первой строки imports
        m2 = re.search(r"^(import[^\n]*\n)", src, re.MULTILINE)
        if m2:
            pos = m2.end()
            src = src[:pos] + "import httpx\n" + src[pos:]
        else:
            # если что-то совсем нестандартно — добавим в начало после shebang/encoding
            m3 = re.search(r"^#.*coding[:=].*\n", src)
            pos = m3.end() if m3 else 0
            src = src[:pos] + "import httpx\n" + src[pos:]

# helpers to replace a whole def block until the next def
def replace_def_block(src_text: str, def_name: str, new_block: str) -> tuple[str, bool]:
    # захватываем от "def name(" до ПЕРЕД следующей строкой, начинающейся с def
    pattern = re.compile(rf"(def\s+{def_name}\s*\([\s\S]*?)(?=^\s*def\s)", re.MULTILINE)
    m = pattern.search(src_text)
    if not m:
        return src_text, False
    start, end = m.span(1)
    return src_text[:start] + new_block + src_text[end:], True

# 2) replace _make_openai_client
make_block = r'''def _make_openai_client() -> OpenAI:
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

    # Прокси задаём через transport
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
src, ok1 = replace_def_block(src, r"_make_openai_client", make_block)
if not ok1:
    print("WARN: _make_openai_client() not found; skip", file=sys.stderr)

# 3) replace _call
call_block = r'''def _call(self, messages: list[dict[str, str]], max_tokens: int = 800) -> str:
    """
    Унифицированный вызов Responses API с ретраями (без .with_options).
    Таймаут задаётся в httpx.Client при создании клиента.
    """
    err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = self.client.responses.create(
                model=self.model,
                input=messages,
                temperature=self.temperature,
                max_output_tokens=max_tokens,
            )
            # Нормализация ответа
            if getattr(r, "output_text", None):
                text = (r.output_text or "").strip()
                if text:
                    return text

            output = getattr(r, "output", None) or []
            for item in output:
                if getattr(item, "type", "") == "message":
                    for c in getattr(item, "content", []) or []:
                        if getattr(c, "type", "") == "output_text":
                            text = (getattr(c, "text", "") or "").strip()
                            if text:
                                return text

            raise RuntimeError("Empty response")
        except (RateLimitError, APIStatusError, APIConnectionError, APITimeoutError) as e:
            err = e
            emsg = str(e)
            if "unsupported_country_region_territory" in emsg.lower():
                logger.error(
                    "OpenAI блокирует по региону (unsupported_country_region_territory). "
                    "Проверь VLESS-прокси (sing-box) и переменные HTTP(S)_PROXY."
                )
            if attempt < MAX_RETRIES:
                sleep_s = 1.25 * attempt
                logger.warning("Retry %d/%d после ошибки: %s (sleep %.1fs)",
                               attempt, MAX_RETRIES, e, sleep_s)
                time.sleep(sleep_s)
                continue
        except Exception as e:
            err = e
            if attempt < MAX_RETRIES:
                sleep_s = 1.25 * attempt
                logger.warning("Retry %d/%d: %s (sleep %.1fs)",
                               attempt, MAX_RETRIES, e, sleep_s)
                time.sleep(sleep_s)
                continue
        break
    raise RuntimeError(f"OpenAI error: {err}")
'''
src, ok2 = replace_def_block(src, r"_call", call_block)
if not ok2:
    print("WARN: _call() not found; skip", file=sys.stderr)

if src == orig:
    print("PATCH WARNING: nothing changed (patterns not found).", file=sys.stderr)
else:
    # backup
    bak = p.with_suffix(".py.bak_patch")
    bak.write_text(orig, encoding="utf-8")
    p.write_text(src, encoding="utf-8")
    print("OK: assistant.py patched. Backup saved to", bak)
