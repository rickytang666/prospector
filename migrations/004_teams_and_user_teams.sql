-- Teams: one per (guild, team_name). Setup-team creates these (no per-user state).
CREATE TABLE IF NOT EXISTS teams (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    guild_id    text NOT NULL,
    team_name   text NOT NULL,
    repo_url    text,
    created_at  timestamptz DEFAULT now(),
    UNIQUE (guild_id, team_name)
);

CREATE INDEX IF NOT EXISTS teams_guild_idx ON teams (guild_id);

-- User-team assignment: which team a user is in per server. Configure-team add/remove.
CREATE TABLE IF NOT EXISTS user_teams (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    guild_id    text NOT NULL,
    user_id     text NOT NULL,
    team_name   text NOT NULL,
    created_at  timestamptz DEFAULT now(),
    UNIQUE (guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS user_teams_guild_user_idx ON user_teams (guild_id, user_id);
