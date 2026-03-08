# 03. Discord Bot

## Bot Initialization

File: `discord_bot/bot.py`

Key startup steps:

- Ensure project root is on `sys.path`
- Initialize intents and custom command tree
- Load cogs in sequence
- Perform guild command sync (`GUILD_ID`)
- Mark bot as ready (`bot.synced = True`)

## In-Memory State

`bot.py` initializes shared in-memory structures:

- `team_configs`
- `team_context_cache`
- `email_draft_cache`
- `chat_threads`
- `synced`

These are process-local and reset on restart.

## Command Modules

### Team and Membership

- `setup_team.py`: register a team and ingest initial context
- `configure_team.py`: add/remove user team membership
- `set-active-team` and `my-team`: active team selection and visibility

### Context and Analysis

- `analyze_team.py`: load team context and infer recruiting gaps
- `add_context.py`: ingest additional source URLs into existing team context
- `remove_from_memory.py`: remove chunks by query and regenerate context
- `nuke.py`: delete all data for a team after reaction confirmation

### Retrieval and Explanations

- `find_support.py`: ranked support/provider discovery
- `explain_match.py`: detailed rationale for a selected entity
- `recruit_gap.py`: inferred team gap display

### Conversation and Email

- `chat.py`: thread-based chat with RAG context retrieval
- `sample_email.py`: generate outreach draft using Gemini
- `send_email.py`: send cached draft through Gmail SMTP

### Utilities

- `help_cog.py`: command reference

## UI Layer

- `ui/embeds.py`: structured output rendering
- `ui/buttons.py`: interaction controls and modal handlers
- `ui/selects.py`: candidate selection control

## Team Context Resolution

`discord_bot/team_ctx.py` resolves context in this order:

1. Bot cache lookup by `(guild_id, user_id)`
2. Database lookup via `storage/db.get_team_context_for_user`
3. Cache population for subsequent requests
