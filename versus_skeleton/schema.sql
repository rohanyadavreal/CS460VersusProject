-- VERSUS skeleton schema
-- Run:  mysql -u root -p versus < schema.sql
--
-- The four core tables for Phase I.
-- Students will extend with: predictions, votes, achievements,
-- user_achievements, follows, comments, plus triggers and a stored procedure.

DROP DATABASE IF EXISTS versus;
CREATE DATABASE versus;
USE versus;

CREATE TABLE Users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password      VARCHAR(255) NOT NULL,
    bio           TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- achievements table
CREATE TABLE Achievements (
    achievement_code VARCHAR(40) PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    description TEXT
);
-- initial achievement data where user hosts first brack and locked in achievemnt
INSERT INTO Achievements (achievement_code, name, description)
VALUES (
    'bracket_maker',
    'Bracket Maker',
    'Awarded when a user hosts their first bracket.'
),
(
    'locked_in',
    'Locked In',
    'Awarded when a user submits their 10th prediction'
);

CREATE TABLE Brackets (
    bracket_id           INT AUTO_INCREMENT PRIMARY KEY,
    host_id              INT NOT NULL,
    title                VARCHAR(255) NOT NULL,
    description          TEXT,
    entrant_count        INT NOT NULL,
    status               ENUM(
                             'draft',
                             'predictions_open',
                             'round_1','round_2','round_3','round_4','round_5',
                             'completed'
                         ) NOT NULL DEFAULT 'draft', -- switch from pred_open to draft 
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_entrant_count CHECK (entrant_count IN (4,8,16,32)),
    CONSTRAINT fk_brackets_host  FOREIGN KEY (host_id) REFERENCES Users(user_id),
    -- brack size check
    CONSTRAINT chk_bracket_size CHECK (entrant_count IN (4, 8, 16, 32))
);

CREATE TABLE Entrants (
    entrant_id   INT AUTO_INCREMENT PRIMARY KEY,
    bracket_id   INT NOT NULL,
    seed         INT NOT NULL,
    name         VARCHAR(255) NOT NULL,
    CONSTRAINT fk_entrants_bracket FOREIGN KEY (bracket_id) REFERENCES Brackets(bracket_id),
    CONSTRAINT uq_entrants_seed    UNIQUE (bracket_id, seed)
);

CREATE TABLE Matchups (
    matchup_id          INT AUTO_INCREMENT PRIMARY KEY,
    bracket_id          INT NOT NULL,
    round               INT NOT NULL,
    slot                INT NOT NULL,
    entrant_a_id        INT,
    entrant_b_id        INT,
    winner_entrant_id   INT,
    votes_a             INT NOT NULL DEFAULT 0,
    votes_b             INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_matchups_bracket FOREIGN KEY (bracket_id)        REFERENCES Brackets(bracket_id),
    CONSTRAINT fk_matchups_a       FOREIGN KEY (entrant_a_id)      REFERENCES Entrants(entrant_id),
    CONSTRAINT fk_matchups_b       FOREIGN KEY (entrant_b_id)      REFERENCES Entrants(entrant_id),
    CONSTRAINT fk_matchups_winner  FOREIGN KEY (winner_entrant_id) REFERENCES Entrants(entrant_id),
    CONSTRAINT uq_matchups_slot    UNIQUE (bracket_id, round, slot)
);
-- prediciton table
CREATE TABLE Predictions (
    prediction_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    matchup_id INT NOT NULL,
    selected_entrant_id INT NOT NULL,
    is_correct TINYINT, -- tinyint! 1 for correct 0 for wrong
    points_earned INT NOT NULL DEFAULT 0,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_predictions_user FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE, -- user exist
    CONSTRAINT fk_predictions_matchup FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id) ON DELETE CASCADE, -- matchup exist
    CONSTRAINT fk_predictions_entrant FOREIGN KEY (selected_entrant_id) REFERENCES Entrants(entrant_id), -- entrant exist
    CONSTRAINT uq_prediction_once UNIQUE (user_id, matchup_id), -- one user per matchuiop
    CONSTRAINT chk_prediction_correct CHECK (is_correct IS NULL OR is_correct IN (0, 1)),
    CONSTRAINT chk_prediction_points CHECK (points_earned >= 0)
);
-- vote table time
CREATE TABLE Votes (
    vote_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    matchup_id INT NOT NULL,
    selected_entrant_id INT NOT NULL,
    voted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_votes_user FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_votes_matchup FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id) ON DELETE CASCADE,
    CONSTRAINT fk_votes_entrant FOREIGN KEY (selected_entrant_id) REFERENCES Entrants(entrant_id),
    CONSTRAINT uq_vote_once UNIQUE (user_id, matchup_id)
);
-- comments table 
CREATE TABLE Comments (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    matchup_id INT NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_matchup FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id) ON DELETE CASCADE
);
-- follows table 
CREATE TABLE Follows (
    follower_id INT NOT NULL,
    followed_id INT NOT NULL,
    followed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id),
    CONSTRAINT fk_follows_follower FOREIGN KEY (follower_id) REFERENCES Users(user_id) ON DELETE CASCADE, -- follower exist
    CONSTRAINT fk_follows_followed FOREIGN KEY (followed_id) REFERENCES Users(user_id) ON DELETE CASCADE, -- followed exist
    CONSTRAINT chk_no_self_follow CHECK (follower_id <> followed_id) -- user cant follow themsleves
);
-- users achievement table
CREATE TABLE UserAchievements (
    user_id INT NOT NULL,
    achievement_code VARCHAR(40) NOT NULL, 
    earned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_code),
    CONSTRAINT fk_user_achievements_user FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_achievements_achievement FOREIGN KEY (achievement_code) REFERENCES Achievements(achievement_code) ON DELETE CASCADE
);
-- index creations
CREATE INDEX idx_brackets_host ON Brackets(host_id);
CREATE INDEX idx_matchups_bracket_round ON Matchups(bracket_id, `round`);
CREATE INDEX idx_predictions_user ON Predictions(user_id);
CREATE INDEX idx_predictions_matchup ON Predictions(matchup_id);
CREATE INDEX idx_votes_matchup ON Votes(matchup_id);
CREATE INDEX idx_comments_matchup ON Comments(matchup_id);
CREATE INDEX idx_follows_follower ON Follows(follower_id);
CREATE INDEX idx_follows_followed ON Follows(followed_id);
-- triggers 
DELIMITER //
-- trigger to prevent a host from opening predictions to early by checking num entrants and num matchups
CREATE TRIGGER bracket_before_open
BEFORE UPDATE ON Brackets
FOR EACH ROW
BEGIN 
    DECLARE entrant_total INT DEFAULT 0;
    DECLARE matchup_total INT DEFAULT 0;
    IF NEW.status = 'predictions_open' THEN
        SELECT COUNT(*) -- count entrants
        INTO entrant_total
        FROM Entrants
        WHERE bracket_id = NEW.bracket_id;
        SELECT COUNT(*) -- count matchups
        INTO matchup_total
        FROM Matchups
        WHERE bracket_id = NEW.bracket_id;
        IF entrant_total <> NEW.entrant_count THEN -- no open prediction if wrong entrant count
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Bracket does not have correct number of entrants.';
        END IF;
        IF matchup_total <> NEW.entrant_count - 1 THEN -- no open prediction if wrong matchup count
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Bracket must have entrant_count minus one matchups before opening predictions.';
        END IF;
    END IF;
END//
-- trigger for bracket maker achievement
CREATE TRIGGER bracket_maker_after_insert
AFTER INSERT ON Brackets
FOR EACH ROW
BEGIN
    DECLARE bracket_total INT;
    SELECT COUNT(*) -- count btackets
    INTO bracket_total
    FROM Brackets
    WHERE host_id = NEW.host_id;
    IF bracket_total = 1 THEN -- when they make first bracket give achievement
        INSERT IGNORE INTO UserAchievements (user_id, achievement_code)
        VALUES (NEW.host_id, 'bracket_maker');
    END IF;
END//
-- trigger so entrant seed cant be larger than bracket size 
CREATE TRIGGER entrant_before_insert
BEFORE INSERT ON Entrants
FOR EACH ROW
BEGIN
    DECLARE max_entrants INT;
    SELECT entrant_count -- bracket size
    INTO max_entrants
    FROM Brackets
    WHERE bracket_id = NEW.bracket_id; -- no seed larger than size
    IF NEW.seed > max_entrants THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Entrant seed cannot be bigger than bracket size.';
    END IF;
END//
-- trigger so predictions are valid 
CREATE TRIGGER prediction_before_insert
BEFORE INSERT ON Predictions
FOR EACH ROW
BEGIN
    DECLARE bracket_status VARCHAR(40);
    DECLARE matchup_round INT;
    DECLARE entrant_a INT;
    DECLARE entrant_b INT;
    SELECT -- bracet status and matchup info
        B.status,
        M.`round`,
        M.entrant_a_id,
        M.entrant_b_id
    INTO
        bracket_status,
        matchup_round,
        entrant_a,
        entrant_b
    FROM Matchups M
    JOIN Brackets B ON M.bracket_id = B.bracket_id
    WHERE M.matchup_id = NEW.matchup_id;
    IF bracket_status <> 'predictions_open' THEN -- valid when predictions_open
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Predictions must happen when predictions are open.';
    END IF;
    IF matchup_round <> 1 THEN -- valid predictions for round 1 matchups
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Predictions only for Round 1 matchups.';
    END IF;
    IF entrant_a IS NULL OR entrant_b IS NULL OR (NEW.selected_entrant_id <> entrant_a AND NEW.selected_entrant_id <> entrant_b) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Prediction must choose entrant A or B.';
    END IF;
END//
-- trigger to give user locked_in achievement
CREATE TRIGGER locked_in_after_10_prediction
AFTER INSERT ON Predictions
FOR EACH ROW
BEGIN
    DECLARE prediction_total INT;
    SELECT COUNT(*) -- count predictions
    INTO prediction_total
    FROM Predictions
    WHERE user_id = NEW.user_id;
    IF prediction_total = 10 THEN -- hit 10 get locked_in
        INSERT IGNORE INTO UserAchievements (user_id, achievement_code)
        VALUES (NEW.user_id, 'locked_in');
    END IF;
END//
-- trigger so votes are valid
CREATE TRIGGER vote_before_insert
BEFORE INSERT ON Votes
FOR EACH ROW
BEGIN
    DECLARE bracket_status VARCHAR(40);
    DECLARE matchup_round INT;
    DECLARE entrant_a INT;
    DECLARE entrant_b INT;
    SELECT -- bracket and matchup info
        B.status,
        M.`round`,
        M.entrant_a_id,
        M.entrant_b_id
    INTO
        bracket_status,
        matchup_round,
        entrant_a,
        entrant_b
    FROM Matchups M
    JOIN Brackets B ON M.bracket_id = B.bracket_id
    WHERE M.matchup_id = NEW.matchup_id;
    IF bracket_status <> CONCAT('round_', matchup_round) THEN -- bracket status matches matchup round
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Vote must be for the current active round.';
    END IF;
    IF entrant_a IS NULL OR entrant_b IS NULL OR (
        NEW.selected_entrant_id <> entrant_a AND NEW.selected_entrant_id <> entrant_b) THEN -- vote must choose one of the entrants
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Vote must choose entrant A or entrant B.';
    END IF;
END//
-- trigger to update num votes
CREATE TRIGGER vote_after_insert
AFTER INSERT ON Votes
FOR EACH ROW
BEGIN
    UPDATE Matchups -- increase entrant A vote count if selected
    SET votes_a = votes_a + 1
    WHERE matchup_id = NEW.matchup_id AND entrant_a_id = NEW.selected_entrant_id;
    UPDATE Matchups -- increase entrant B vote count if selected
    SET votes_b = votes_b + 1
    WHERE matchup_id = NEW.matchup_id AND entrant_b_id = NEW.selected_entrant_id;
END//
-- trigger to reject comments on matchups outside round 1
CREATE TRIGGER comment_before_insert
BEFORE INSERT ON Comments
FOR EACH ROW
BEGIN
    DECLARE matchup_round INT;
    SELECT `round` -- find round
    INTO matchup_round
    FROM Matchups
    WHERE matchup_id = NEW.matchup_id;
    IF matchup_round <> 1 THEN -- comments only after round one
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Comments are only allowed on Round 1 matchups.';
    END IF;
END//
-- maine transaction baby oh yeah time to close tha round
CREATE PROCEDURE close_round(IN p_bracket_id INT, IN p_round INT)
BEGIN
    DECLARE v_status VARCHAR(40);
    DECLARE v_entrant_count INT;
    DECLARE v_total_rounds INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION -- if we error
    BEGIN
        ROLLBACK; -- undo changes
        RESIGNAL; 
    END;
    START TRANSACTION;
    IF NOT EXISTS ( -- bracket exists
        SELECT 1
        FROM Brackets
        WHERE bracket_id = p_bracket_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Bracket does not exist.';
    END IF;

    SELECT -- lock bracket row while closing
        status,
        entrant_count
    INTO
        v_status,
        v_entrant_count
    FROM Brackets
    WHERE bracket_id = p_bracket_id

    FOR UPDATE; -- prevent 2 closings from happening at same time
    SET v_total_rounds = CEIL(LOG(v_entrant_count) / LOG(2)); -- total rounds 
    IF v_status <> CONCAT('round_', p_round) THEN -- bracket has to be in round host wants to close up
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Bracket is not in the round being closed.';
    END IF;

    IF EXISTS ( -- matchup needs to have both entrants otherwise problema
        SELECT 1
        FROM Matchups
        WHERE bracket_id = p_bracket_id AND `round` = p_round AND (entrant_a_id IS NULL OR entrant_b_id IS NULL)
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot close round with missing entrants.';
    END IF;

    UPDATE Matchups -- winner winner chicken dinner
    SET winner_entrant_id = CASE
        WHEN votes_a >= votes_b THEN entrant_a_id
        ELSE entrant_b_id
    END
    WHERE bracket_id = p_bracket_id AND `round` = p_round;

    UPDATE Predictions P
    JOIN Matchups M ON P.matchup_id = M.matchup_id
    SET
        P.is_correct = CASE -- correct prediction, is correct becomes one
            WHEN P.selected_entrant_id = M.winner_entrant_id THEN 1
            ELSE 0
        END,
        P.points_earned = CASE -- points earned otherwise is 2^(round-1) so like round 3 correct you get 4 pts
            WHEN P.selected_entrant_id = M.winner_entrant_id
                THEN POW(2, p_round - 1)
            ELSE 0
        END
    WHERE M.bracket_id = p_bracket_id AND M.`round` = p_round;

    -- bracket movement
    -- have next round slot get previous round winner as one entrant, the other winner as other
    -- prev entrant A matchup = next slot * 2 - 1
    -- prev entrant B matchup = next slot * 2
    IF p_round < v_total_rounds THEN
    UPDATE Matchups NextM
        JOIN Matchups PrevA ON PrevA.bracket_id = NextM.bracket_id
            AND PrevA.`round` = p_round
            AND PrevA.slot = (NextM.slot * 2 - 1)
        JOIN Matchups PrevB ON PrevB.bracket_id = NextM.bracket_id
            AND PrevB.`round` = p_round
            AND PrevB.slot = (NextM.slot * 2)
        SET NextM.entrant_a_id = PrevA.winner_entrant_id, NextM.entrant_b_id = PrevB.winner_entrant_id,
            NextM.winner_entrant_id = NULL, -- next matcchup ready for votes
            NextM.votes_a = 0,
            NextM.votes_b = 0
        WHERE NextM.bracket_id = p_bracket_id AND NextM.`round` = p_round + 1;
        UPDATE Brackets -- advance bracket to next active ronud
        SET status = CONCAT('round_', p_round + 1)
        WHERE bracket_id = p_bracket_id;
    ELSE -- we are on final round
        UPDATE Brackets
        SET status = 'completed'
        WHERE bracket_id = p_bracket_id;
    END IF;
    COMMIT;
END//
DELIMITER ;

