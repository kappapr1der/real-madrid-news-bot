import re, sys, pathlib

p = pathlib.Path("assistant.py")
src = p.read_text(encoding="utf-8")
orig = src

pattern = re.compile(r"(def\s+_make_openai_client\s*\([\s\S]*?^\s*class\s+Assistant\b)", re.MULTILINE)

replacement = r'''def _make_openai_client() -> OpenAI:
    """
    Создаёт OpenAI-клиент и полагается на переменные окружения (HTTPS_PROXY/HTTP_PROXY).
    Без кастомного httpx-клиента — чтобы исключить ошибки транспорта.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")
    return OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE.rstrip("/"),
    )

class Assistant:
'''
new, n = pattern.subn(replacement, src, count=1)
if n != 1:
    print("PATCH ERROR: не удалось найти блок _make_openai_client()", file=sys.stderr)
    sys.exit(1)

bak = p.with_suffix(".py.bak_envproxy")
bak.write_text(orig, encoding="utf-8")
p.write_text(new, encoding="utf-8")
print("OK: assistant.py обновлён. Бэкап:", bak)
