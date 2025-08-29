import re, sys, pathlib

p = pathlib.Path("assistant.py")
src = p.read_text(encoding="utf-8")

# найдём тело _call и заменим
pattern = re.compile(
    r"def _call\([\s\S]*?^\s*def ask\(",
    re.MULTILINE
)

replacement = r'''def _call(self, messages: list[dict[str, str]], max_tokens: int = 800) -> str:
        """
        Унифицированный вызов Responses API с ретраями (без .with_options).
        Таймаут прокинут в httpx.Client при создании клиента.
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
                    logger.warning("Retry %d/%d после ошибки: %s (sleep %.1fs)", attempt, MAX_RETRIES, e, sleep_s)
                    time.sleep(sleep_s)
                    continue
            except Exception as e:
                err = e
                if attempt < MAX_RETRIES:
                    sleep_s = 1.25 * attempt
                    logger.warning("Retry %d/%d: %s (sleep %.1fs)", attempt, MAX_RETRIES, e, sleep_s)
                    time.sleep(sleep_s)
                    continue
            break
        raise RuntimeError(f"OpenAI error: {err}")

    def ask('''  # <-- аккуратно оставляем def ask как было
new, n = pattern.subn(replacement, src, count=1)
if n != 1:
    print("PATCH ERROR: не смог заменить метод _call()", file=sys.stderr)
    sys.exit(1)

bak = p.with_suffix(".py.bak3")
bak.write_text(src, encoding="utf-8")
p.write_text(new, encoding="utf-8")
print("OK: _call() переписан. Бэкап:", bak)
