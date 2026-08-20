# Emergency failover runbook

Use this when the current VPS or region is unavailable for long enough to miss Telegram posts.

## Rules

- Run only one live bot at a time. If the old VPS comes back after failover, stop one of the services before both can post.
- Never commit `.env`, `state/`, `logs/`, `config/matches.json`, or sent-link files.
- Prefer a new VPS outside the failed region/provider.
- Run bot Python commands as `coffee`, not as `root`. Root-owned files inside `state/` block the systemd service from updating dedupe and lifecycle data.

## New VPS bootstrap

Run as `root` on the new VPS:

```bash
apt update
apt install -y git python3 python3-venv python3-pip ca-certificates

id coffee >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin coffee
mkdir -p /opt/coffee-bot
chown coffee:coffee /opt/coffee-bot

sudo -u coffee git clone https://github.com/kappapr1der/real-madrid-news-bot.git /opt/coffee-bot
cd /opt/coffee-bot
sudo -u coffee git checkout codex/server-runtime-sync
sudo -u coffee python3 -m venv .venv
sudo -u coffee .venv/bin/pip install --upgrade pip
sudo -u coffee .venv/bin/pip install -r requirements.txt

sudo -u coffee mkdir -p logs state config
```

## Restore config and runtime state

If the old VPS is reachable, copy config and state from it:

```bash
scp root@OLD_SERVER:/opt/coffee-bot/.env /opt/coffee-bot/.env
scp -r root@OLD_SERVER:/opt/coffee-bot/state/* /opt/coffee-bot/state/
scp root@OLD_SERVER:/opt/coffee-bot/config/matches.json /opt/coffee-bot/config/matches.json
chown -R coffee:coffee /opt/coffee-bot
chmod 600 /opt/coffee-bot/.env
sudo -u coffee test -w /opt/coffee-bot/state
if [ -e /opt/coffee-bot/state/story_lifecycle.json ]; then
  sudo -u coffee test -w /opt/coffee-bot/state/story_lifecycle.json
fi
```

If the old VPS is not reachable, recreate `/opt/coffee-bot/.env` from `.env.example` and fill at least:

```env
TELEGRAM_BOT_TOKEN=replace_me
TARGET_CHAT_ID=@slivochniyfootball
DRY_RUN=false
DIGEST_MISSED_CATCHUP_ENABLED=true
DIGEST_MISSED_GRACE_MINUTES=360
HEARTBEAT_HOST=0.0.0.0
HEARTBEAT_PORT=8000
HEARTBEAT_TOKEN=replace_with_long_random_string
```

Also add Yandex Translate and YandexGPT variables if they are used in production.

## Smoke test

Before live start:

```bash
cd /opt/coffee-bot
sudo -u coffee .venv/bin/python scripts/preflight.py
sudo -u coffee env DRY_RUN=true .venv/bin/python digest.py day
```

## Install and start systemd

```bash
cp /opt/coffee-bot/deploy/systemd/coffee-bot.service.example /etc/systemd/system/coffee-bot.service
systemctl daemon-reload
systemctl enable coffee-bot.service
systemctl start coffee-bot.service
systemctl status coffee-bot.service --no-pager
journalctl -u coffee-bot.service -n 80 --no-pager
```

Health check:

```bash
curl -fsS http://127.0.0.1:8000/
```

If `HEARTBEAT_TOKEN` is set:

```bash
curl -fsS "http://127.0.0.1:8000/health?token=replace_with_long_random_string"
```

## When the old VPS returns

Stop either the old or new service before both are live:

```bash
systemctl stop coffee-bot.service
systemctl disable coffee-bot.service
```

Then compare `state/` before choosing the long-term active server.
