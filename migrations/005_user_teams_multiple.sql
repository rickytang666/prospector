-- Allow users to be in multiple teams; one "active" team per user per guild.
-- Run after 004_teams_and_user_teams.sql.

-- Drop one-team-per-user constraint.
-- If this fails, list constraints with: SELECT conname FROM pg_constraint WHERE conrelid = 'user_teams'::regclass;
ALTER TABLE user_teams DROP CONSTRAINT IF EXISTS user_teams_guild_id_user_id_key;

-- One row per (guild, user, team); same user can have multiple rows
ALTER TABLE user_teams ADD CONSTRAINT user_teams_guild_user_team_key UNIQUE (guild_id, user_id, team_name);

-- Which team to use for /chat, /find-support, etc. (one active per user per guild)
ALTER TABLE user_teams ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;

-- Ensure only one active per (guild_id, user_id): optional trigger or enforce in app.
-- App will set is_active = false on others when setting one active.
