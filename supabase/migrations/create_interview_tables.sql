CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS interview_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    target_job_id text NULL,
    target_job_title text NOT NULL,
    target_company_name text NULL,
    status text NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'report_generated', 'report_failed')),
    consent_given boolean NOT NULL DEFAULT false,
    consent_given_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz NULL
);

CREATE TABLE IF NOT EXISTS interview_answers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_session_id uuid NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    question text NOT NULL,
    answer_text text NOT NULL,
    answer_order int NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(interview_session_id, answer_order)
);

CREATE TABLE IF NOT EXISTS interview_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_session_id uuid NOT NULL UNIQUE REFERENCES interview_sessions(id) ON DELETE CASCADE,
    candidate_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    target_job_title text NOT NULL,
    report_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    overall_score int NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    recommendation text NULL,
    status text NOT NULL DEFAULT 'generated'
        CHECK (status IN ('generated', 'failed')),
    generation_error text NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_interview_sessions_candidate_user_id
ON interview_sessions(candidate_user_id);

CREATE INDEX IF NOT EXISTS idx_interview_answers_session_id
ON interview_answers(interview_session_id);

CREATE INDEX IF NOT EXISTS idx_interview_reports_candidate_user_id
ON interview_reports(candidate_user_id);

CREATE INDEX IF NOT EXISTS idx_interview_reports_session_id
ON interview_reports(interview_session_id);

ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own sessions" ON interview_sessions;
CREATE POLICY "Users can view their own sessions" ON interview_sessions
    FOR SELECT TO authenticated
    USING (auth.uid() = candidate_user_id);

DROP POLICY IF EXISTS "Users can insert their own sessions" ON interview_sessions;
CREATE POLICY "Users can insert their own sessions" ON interview_sessions
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = candidate_user_id);

DROP POLICY IF EXISTS "Users can update their own sessions" ON interview_sessions;
CREATE POLICY "Users can update their own sessions" ON interview_sessions
    FOR UPDATE TO authenticated
    USING (auth.uid() = candidate_user_id)
    WITH CHECK (auth.uid() = candidate_user_id);

DROP POLICY IF EXISTS "Users can view answers for their own sessions" ON interview_answers;
CREATE POLICY "Users can view answers for their own sessions" ON interview_answers
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM interview_sessions
            WHERE interview_sessions.id = interview_answers.interview_session_id
            AND interview_sessions.candidate_user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert answers for their own sessions" ON interview_answers;
CREATE POLICY "Users can insert answers for their own sessions" ON interview_answers
    FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM interview_sessions
            WHERE interview_sessions.id = interview_answers.interview_session_id
            AND interview_sessions.candidate_user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can view their own reports" ON interview_reports;
CREATE POLICY "Users can view their own reports" ON interview_reports
    FOR SELECT TO authenticated
    USING (auth.uid() = candidate_user_id);

DROP POLICY IF EXISTS "Users can insert their own reports" ON interview_reports;
CREATE POLICY "Users can insert their own reports" ON interview_reports
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = candidate_user_id);
