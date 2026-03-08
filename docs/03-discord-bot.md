# 03 - Discord Bot

## Bot architecture

Main file: `discord_bot/bot.py`

Bot state kept in memory:

- `bot.team_configs`
- `bot.team_context_cache`
- `bot.email_draft_cache`
- `bot.chat_threads`
- `bot.synced`

Command tree uses `BotTree.interaction_check` to reject commands while startup sync is not done.

## Cogs and what each one does

### Setup and membership

- `/setup-team` (`cogs/setup_team.py`)
  - Registers team in `teams` table
  - Ingests GitHub and optional website/Notion/Confluence
  - Embeds chunks and stores derived `team_context`

- `/configure-team` (`cogs/configure_team.py`)
  - `add`: join team and set active
  - `remove`: leave one team

- `/my-team`
  - Shows user memberships and active team

- `/set-active-team`
  - Switches active team row in `user_teams`

### Team analysis and memory edits

- `/analyze-team` (`cogs/analyze_team.py`)
  - Loads stored team context
  - Infers recruiting gaps from blockers/needs
  - Caches context in bot memory for user/guild pair

- `/add-context` (`cogs/add_context.py`)
  - Scrapes one new source and inserts new chunks by content hash
  - Re-runs context extraction

- `/remove_from_memory` (`cogs/remove_from_memory.py`)
  - Deletes chunks matching keyword query
  - Rebuilds team context from remaining chunks

- `/nuke` (`cogs/nuke.py`)
  - Confirmation reaction required
  - Deletes chunks, team_context, membership links, team row

### Retrieval and explanation

- `/find-support` (`cogs/find_support.py`)
  - Calls `retrieval.api.find_support_dict`
  - Adds contact info from Gemini helper

- `/find-providers`
  - Calls `retrieval.api.find_providers_dict`

- `/explain-match` (`cogs/explain_match.py`)
  - Calls `retrieve_context_pack_dict`
  - Builds explanation embed + expanded ask text

- `/recruit-gap`
  - Displays inferred support gaps

### Chat and email

- `/chat` (`cogs/chat.py`)
  - Creates thread
  - Thread messages trigger RAG retrieval + Gemini reply
  - Cooldown is 8 sec per user-thread pair

- `/sample_email` (`cogs/sample_email.py`)
  - Gemini draft generation from team context
  - Stores draft in `bot.email_draft_cache[guild_id]`

- `/send_email` (`cogs/send_email.py`)
  - Sends latest draft through Gmail SMTP (`aiosmtplib`)

### Utility

- `/help` (`cogs/help_cog.py`)

## UI pieces

- `ui/embeds.py`
  - Candidate ranking embed
  - Explanation embed
  - Team context embed
  - Email draft/sent embeds

- `ui/buttons.py`
  - Candidate explain buttons
  - Email edit modal + copy button

## Cache key gotcha

There are mixed key shapes in code paths:

- Some places use key `(guild_id, user_id)` as strings
- Some places use ints

The helper `team_ctx.get_team_context_for_member` normalizes to string tuple.
If cache misses feel weird, this is first place to inspect.
