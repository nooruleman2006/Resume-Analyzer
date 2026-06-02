-- ============================================================
--  ResumeAI  —  Full Database Schema
--  Run: mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS resume_analyzer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE resume_analyzer;

-- ── USERS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    first_name    VARCHAR(80)  NOT NULL,
    last_name     VARCHAR(80)  NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     DEFAULT NOW(),
    last_login    DATETIME     NULL
);

-- ── RESUMES ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resumes (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    user_id          INT          NOT NULL,
    filename         VARCHAR(255) NOT NULL,
    stored_path      VARCHAR(500) NOT NULL,
    raw_text         LONGTEXT,
    skills_extracted TEXT,
    job_title        VARCHAR(200),
    industry         VARCHAR(100),
    job_description  LONGTEXT,
    upload_date      DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── ANALYSIS RESULTS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_results (
    id                INT PRIMARY KEY AUTO_INCREMENT,
    resume_id         INT  NOT NULL,
    ats_score         INT  DEFAULT 0,
    readability_score INT  DEFAULT 0,
    keyword_score     INT  DEFAULT 0,
    ai_summary        LONGTEXT,
    ai_suggestions    LONGTEXT,   -- JSON string
    present_skills    TEXT,       -- JSON string
    missing_skills    TEXT,       -- JSON string
    score_breakdown   TEXT,       -- JSON string
    analyzed_at       DATETIME DEFAULT NOW(),
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
);

-- ── JOB APPLICATIONS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    user_id     INT          NOT NULL,
    resume_id   INT          NULL,
    job_title   VARCHAR(200) NOT NULL,
    company     VARCHAR(200) NOT NULL,
    job_url     VARCHAR(1000),
    location    VARCHAR(200),
    salary      VARCHAR(100),
    match_score INT          DEFAULT 0,
    source      VARCHAR(50)  DEFAULT 'manual',   -- linkedin / rozee / indeed / manual
    status      ENUM('pending','applied','viewed','interview','rejected','failed')
                DEFAULT 'pending',
    applied_at  DATETIME DEFAULT NOW(),
    updated_at  DATETIME DEFAULT NOW() ON UPDATE NOW(),
    FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE SET NULL
);

-- ── INDEXES ──────────────────────────────────────────────────
CREATE INDEX idx_resumes_user      ON resumes(user_id);
CREATE INDEX idx_analysis_resume   ON analysis_results(resume_id);
CREATE INDEX idx_applications_user ON applications(user_id);
CREATE INDEX idx_applications_status ON applications(status);