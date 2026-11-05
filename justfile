# Airlock commands. Needs uv; the live ones need a Switch server (see README).
# Switch's .env is read from ../switch/.env unless SWITCH_ENV says otherwise.

switch_env := env_var_or_default("SWITCH_ENV", "../switch/.env")

default:
    @just --list

# Offline proof: claims, PSI, Customs, the 401 -> fix -> 200 replay. No server.
test:
    uv run pytest -q

# Create the two companies, four agents and three rooms on Switch (and Mattermost).
setup *ARGS:
    set -a && . {{switch_env}} && set +a && \
    SWITCH_ADMIN_EMAIL="$GATEWAY_ADMIN_EMAIL" SWITCH_ADMIN_PASSWORD="$GATEWAY_ADMIN_PASSWORD" \
    uv run python scripts/setup.py --mattermost {{ARGS}}

# Re-apply the Customs icons: through Switch (needs the repo public) and straight to Mattermost.
icons:
    set -a && . {{switch_env}} && set +a && uv run python scripts/setup.py --icons-only

# The whole incident, scripted, on the live server. No model.
e2e:
    uv run python scripts/e2e_live.py

# Run everything live: webhook endpoint, both Customs, both Claude Code investigators.
up *ARGS:
    uv run python scripts/up.py --reset {{ARGS}}

# Post as an engineer and print the replies, e.g. just ask kudimart "@investigator what's failing?"
ask COMPANY TEXT *ARGS:
    uv run python scripts/ask.py {{COMPANY}} "{{TEXT}}" {{ARGS}}

# KudiMart ships verifier v2.14.1 to the canary.
fix:
    uv run python -m airlock.sim fix state/kudimart

# Regenerate the committed synthetic data (deterministic).
data:
    rm -rf data && uv run python -m airlock.sim generate data
