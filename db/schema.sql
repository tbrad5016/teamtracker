-- schema.sql : TeamTracker.gg (League of Legends teammate-performance tracker)
-- Implements the normalized relational schema from Project Phase 3.
-- Run order: schema.sql first, then seed.sql.
-- Phase 5 change: Registered_Users gained a "role" column (user / admin).

CREATE TABLE Registered_Users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(30)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    -- Phase 5: two user roles. Everyone who signs up is a 'user'; admins are
    -- created with backend/create_admin.py (no admin password lives in the code).
    role          VARCHAR(10)  NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Players (
    puuid             VARCHAR(78) PRIMARY KEY,
    riot_id_game_name VARCHAR(32) NOT NULL,
    riot_id_tagline   VARCHAR(10) NOT NULL,
    updated_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- queue_id holds Riot's own queue numbers (420, 440, ...), so it is not auto-numbered.
CREATE TABLE Queue_Types (
    queue_id    INT PRIMARY KEY,
    description VARCHAR(50) NOT NULL UNIQUE,
    category    VARCHAR(10) NOT NULL CHECK (category IN ('RANKED', 'CASUAL'))
);

CREATE TABLE Matches (
    match_id      VARCHAR(20) PRIMARY KEY,
    queue_id      INT    NOT NULL REFERENCES Queue_Types(queue_id) ON DELETE RESTRICT,
    game_creation BIGINT NOT NULL,                              -- milliseconds since 1970
    game_duration INT    NOT NULL CHECK (game_duration > 0)     -- seconds
);

-- Created by normalization: win depends on (match_id, team_id), not on a participant.
CREATE TABLE Match_Teams (
    match_id VARCHAR(20) NOT NULL REFERENCES Matches(match_id) ON DELETE CASCADE,
    team_id  INT         NOT NULL,
    win      BOOLEAN     NOT NULL,
    PRIMARY KEY (match_id, team_id)
);

CREATE TABLE Participants (
    match_id      VARCHAR(20) NOT NULL,
    puuid         VARCHAR(78) NOT NULL REFERENCES Players(puuid) ON DELETE RESTRICT,
    team_id       INT         NOT NULL,
    role          VARCHAR(10) CHECK (role IN ('TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY')),
    champion_name VARCHAR(30) NOT NULL,
    kills         INT NOT NULL CHECK (kills >= 0),
    deaths        INT NOT NULL CHECK (deaths >= 0),
    assists       INT NOT NULL CHECK (assists >= 0),
    total_damage_dealt_to_champions INT NOT NULL CHECK (total_damage_dealt_to_champions >= 0),
    gold_earned   INT NOT NULL CHECK (gold_earned >= 0),
    vision_score  INT NOT NULL CHECK (vision_score >= 0),
    PRIMARY KEY (match_id, puuid),
    FOREIGN KEY (match_id, team_id) REFERENCES Match_Teams(match_id, team_id) ON DELETE CASCADE
);

CREATE TABLE Player_Ranks (
    puuid         VARCHAR(78) NOT NULL REFERENCES Players(puuid) ON DELETE CASCADE,
    queue_id      INT         NOT NULL REFERENCES Queue_Types(queue_id) ON DELETE RESTRICT,
    tier          VARCHAR(12) NOT NULL CHECK (tier IN ('IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM',
                                                       'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER')),
    rank_division VARCHAR(3)  NOT NULL CHECK (rank_division IN ('I', 'II', 'III', 'IV')),
    league_points INT NOT NULL CHECK (league_points >= 0),
    wins          INT NOT NULL CHECK (wins >= 0),
    losses        INT NOT NULL CHECK (losses >= 0),
    PRIMARY KEY (puuid, queue_id)
);

CREATE TABLE Saved_Searches (
    search_id          SERIAL PRIMARY KEY,
    user_id            INT         NOT NULL REFERENCES Registered_Users(user_id) ON DELETE CASCADE,
    puuid              VARCHAR(78) NOT NULL REFERENCES Players(puuid) ON DELETE CASCADE,
    queue_category     VARCHAR(10) CHECK (queue_category IN ('RANKED', 'CASUAL')),   -- NULL = any queue
    time_period_months SMALLINT    CHECK (time_period_months BETWEEN 1 AND 6),       -- NULL = full 6 months
    created_at         TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);
