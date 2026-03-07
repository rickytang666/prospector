CREATE TABLE team_context (
    id             uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    team_name      text UNIQUE NOT NULL,
    tech_stack     text[],
    focus_areas    text[],
    blockers       text[],
    needs          text[],
    raw_llm_output text,
    updated_at     timestamptz DEFAULT now()
);
