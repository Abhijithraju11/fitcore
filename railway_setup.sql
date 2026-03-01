-- ═══════════════════════════════════════════════════════════
-- FitCore — Railway Database Setup Script
-- Paste this entire file into:
-- Railway Dashboard → your PostgreSQL service → Data → Query
-- ═══════════════════════════════════════════════════════════

-- 1. ACCOUNTS (users + owners)
CREATE TABLE IF NOT EXISTS accounts (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password      TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'member',
    age           INTEGER,
    height        REAL,
    weight        REAL,
    fitness_level TEXT DEFAULT 'Beginner',
    goal          TEXT DEFAULT 'General Fitness',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. WORKOUTS
CREATE TABLE IF NOT EXISTS workouts (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    exercise_name  TEXT NOT NULL,
    duration       INTEGER,
    calories_burned REAL,
    workout_date   DATE,
    notes          TEXT
);

-- 3. NUTRITION
CREATE TABLE IF NOT EXISTS nutrition (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    meal_name   TEXT NOT NULL,
    calories    REAL,
    protein     REAL,
    carbs       REAL,
    fats        REAL,
    meal_date   DATE
);

-- 4. GOALS
CREATE TABLE IF NOT EXISTS goals (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    goal_type     TEXT NOT NULL,
    target_value  REAL,
    current_value REAL DEFAULT 0,
    deadline      DATE,
    status        TEXT DEFAULT 'Active'
);

-- ── SEED DATA ────────────────────────────────────────────────
-- Default owner account (password: owner123)
INSERT INTO accounts (name, email, password, role)
VALUES ('Gym Owner', 'owner@fitcore.com',
        'a5b0e12571eeef73c2f856d25e81b5d5a94dbd36a95db59a3ccb14624f0e2a9a', 'owner')
ON CONFLICT (email) DO NOTHING;

-- Sample member account (password: alex123)
INSERT INTO accounts (name, email, password, role, age, height, weight, fitness_level, goal)
VALUES ('Alex Johnson', 'alex@example.com',
        '5a5b18ddbf7be73bad4c1e4c2ef52c37f77ee7de0a4dfcb1ba5e5c6ff6c4d6e4',
        'member', 25, 175, 78, 'Intermediate', 'Weight Loss')
ON CONFLICT (email) DO NOTHING;

-- Sample workout for Alex
INSERT INTO workouts (user_id, exercise_name, duration, calories_burned, workout_date, notes)
SELECT id, 'Running', 45, 450, '2024-01-15', 'Morning run'
FROM accounts WHERE email = 'alex@example.com'
ON CONFLICT DO NOTHING;

-- Sample meal for Alex
INSERT INTO nutrition (user_id, meal_name, calories, protein, carbs, fats, meal_date)
SELECT id, 'Grilled Chicken & Rice', 520, 42, 55, 8, '2024-01-15'
FROM accounts WHERE email = 'alex@example.com'
ON CONFLICT DO NOTHING;

-- Sample goal for Alex
INSERT INTO goals (user_id, goal_type, target_value, current_value, deadline, status)
SELECT id, 'Target Weight (kg)', 70, 78, '2024-06-01', 'Active'
FROM accounts WHERE email = 'alex@example.com'
ON CONFLICT DO NOTHING;

-- ── VERIFY ───────────────────────────────────────────────────
SELECT 'accounts' as table_name, COUNT(*) as rows FROM accounts
UNION ALL
SELECT 'workouts', COUNT(*) FROM workouts
UNION ALL
SELECT 'nutrition', COUNT(*) FROM nutrition
UNION ALL
SELECT 'goals',    COUNT(*) FROM goals;
