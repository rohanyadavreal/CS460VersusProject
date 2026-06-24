######################################
# VERSUS skeleton app.py
# CS460 Final Project
######################################
# Covers the core: register/login, create bracket, browse, view.
# Students extend with: predictions, voting, round-closing (stored
# procedure), triggers, leaderboard (window functions), recursive CTE,
# follows, comments, indexes.
###################################################

import flask
from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
import flask_login
import datetime

app = Flask(__name__)
app.secret_key = 'super secret string'  # Change this!

# These will need to be changed according to your credentials.
DB_USER     = 'root'
DB_PASSWORD = 'YOUR_PASSWORD'
DB_NAME     = 'versus'
DB_HOST     = 'localhost'

def get_conn():
	return mysql.connector.connect(
		host=DB_HOST,
		user=DB_USER,
		password=DB_PASSWORD,
		database=DB_NAME,
		autocommit=False,
	)

conn = get_conn()


# begin code used for login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)


def getUserList():
	cursor = conn.cursor()
	cursor.execute("SELECT username from Users")
	rows = cursor.fetchall()
	cursor.close()
	return rows


class User(flask_login.UserMixin):
	pass

@login_manager.user_loader
def user_loader(username):
    if not username:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username FROM Users WHERE username = %s",
        (username,)
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return None
    user = User()
    user.id = row[0]
    return user


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password FROM Users WHERE username = %s",
        (username,)
    )
    data = cursor.fetchone()
    cursor.close()
    if data and password == data[0]:
        user = User()
        user.id = username
        flask_login.login_user(user)
        return redirect(url_for('home'))
    return """
        <p>Invalid username or password.</p>
        <a href='/login'>Try again</a><br>
        <a href='/register'>or make an account</a>
    """


@login_manager.unauthorized_handler
def unauthorized_handler():
	return render_template('unauth.html')


# you can specify specific methods (GET/POST) in the function header instead
# of inside the function body
@app.route("/register", methods=['GET'])
def register():
	return render_template('register.html')

@app.route("/register", methods=['POST'])
def register_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    bio = request.form.get('bio', '').strip()
    if not username or not email or not password:
        return simpleError(
            "Username, email, and password are required."
        )
    if not isUsernameUnique(username):
        return simpleError(
            "That username is already in use."
        )
    if not isEmailUnique(email):
        return simpleError(
            "That email address is already in use."
        )
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Users "
            "(username, email, password, bio) "
            "VALUES (%s, %s, %s, %s)",
            (username, email, password, bio)
        )
        conn.commit()
    except mysql.connector.Error as error:
        conn.rollback()
        cursor.close()
        return simpleError(error)
    cursor.close()
    user = User()
    user.id = username
    flask_login.login_user(user)
    return render_template(
        'hello.html',
        name=username,
        message='account created'
    )


def isUsernameUnique(username):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM Users WHERE username = %s",
        (username,)
    )
    row = cursor.fetchone()
    cursor.close()
    return row is None

def isEmailUnique(email):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM Users WHERE email = %s",
        (email,)
    )
    row = cursor.fetchone()
    cursor.close()
    return row is None

def getUserIdFromUsername(username):
	cursor = conn.cursor()
	cursor.execute("SELECT user_id FROM Users WHERE username = '{0}'".format(username))
	row = cursor.fetchone()
	cursor.close()
	return row[0] if row else None


def getUsernameFromUserId(uid):
	cursor = conn.cursor()
	cursor.execute("SELECT username FROM Users WHERE user_id = '{0}'".format(uid))
	row = cursor.fetchone()
	cursor.close()
	return row[0] if row else None

# end login code


# begin bracket creation code
@app.route('/create', methods=['GET', 'POST'])
@flask_login.login_required
def create_bracket():
	if request.method == 'POST':
		uid           = getUserIdFromUsername(flask_login.current_user.id)
		title         = request.form.get('title')
		description   = request.form.get('description')
		entrant_count = int(request.form.get('entrant_count'))
		cursor = conn.cursor()

		# 1. insert the bracket row
		cursor.execute(
			"INSERT INTO Brackets (host_id, title, description, entrant_count) VALUES ('{0}', '{1}', '{2}', '{3}')".format(
				uid, title, description or "", entrant_count))
		cursor.execute("SELECT LAST_INSERT_ID()")
		bracket_id = cursor.fetchone()[0]

		# 2. insert all entrants in seed order
		entrant_ids = []
		for seed in range(1, entrant_count + 1):
			entrant_name = request.form.get('entrant_' + str(seed))
			cursor.execute(
				"INSERT INTO Entrants (bracket_id, seed, name) VALUES ('{0}', '{1}', '{2}')".format(
					bracket_id, seed, entrant_name))
			cursor.execute("SELECT LAST_INSERT_ID()")
			entrant_ids.append(cursor.fetchone()[0])

		# 3. create Round 1 matchups (seed pairs: 1v2, 3v4, ...)
		round_1_slots = entrant_count // 2
		for slot in range(1, round_1_slots + 1):
			a = entrant_ids[(slot - 1) * 2]
			b = entrant_ids[(slot - 1) * 2 + 1]
			cursor.execute(
				"INSERT INTO Matchups (bracket_id, `round`, slot, entrant_a_id, entrant_b_id) VALUES ('{0}', 1, '{1}', '{2}', '{3}')".format(
					bracket_id, slot, a, b))

		# 4. create empty shells for later rounds
		slots = round_1_slots // 2
		round_num = 2
		while slots >= 1:
			for slot in range(1, slots + 1):
				cursor.execute(
					"INSERT INTO Matchups (bracket_id, `round`, slot) VALUES ('{0}', '{1}', '{2}')".format(
						bracket_id, round_num, slot))
			slots //= 2
			round_num += 1

		conn.commit()
		cursor.close()
		return redirect(url_for('view_bracket', bracket_id=bracket_id))
	else:
		return render_template('create.html')
# end bracket creation code


# begin browse code
def getAllBrackets():
	cursor = conn.cursor()
	cursor.execute(
		"SELECT b.bracket_id, b.title, b.status, b.entrant_count, b.created_at, u.username "
		"FROM Brackets b JOIN Users u ON b.host_id = u.user_id "
		"ORDER BY b.created_at DESC")
	rows = cursor.fetchall()
	cursor.close()
	return rows


@app.route('/browse', methods=['GET'])
def browse():
	brackets = getAllBrackets()
	return render_template('browse.html', brackets=brackets)
# end browse code


# begin bracket view code
def getCurrentUserId(): #username to user_id
	if not flask_login.current_user.is_authenticated:
		return None
	return getUserIdFromUsername(flask_login.current_user.id)

def getBracketInfo(bracket_id):
	# tuple order:
	# 0 bracket_id, 1 title, 2 description, 3 status,
	# 4 entrant_count, 5 host_id, 6 host_username
	cursor = conn.cursor()
	cursor.execute(
		"SELECT b.bracket_id, b.title, b.description, b.status, b.entrant_count, b.host_id, u.username "
		"FROM Brackets b JOIN Users u ON b.host_id = u.user_id "
		"WHERE b.bracket_id = '{0}'".format(bracket_id))
	row = cursor.fetchone()
	cursor.close()
	return row


def getMatchupsForBracket(bracket_id):
	# tuple order:
	# 0 matchup_id, 1 round, 2 slot, 3 entrant_a_id, 4 entrant_b_id,
	# 5 entrant_a_name, 6 entrant_b_name, 7 winner_name, 8 votes_a, 9 votes_b
	cursor = conn.cursor()
	cursor.execute(
		"SELECT m.matchup_id, m.`round`, m.slot, m.entrant_a_id, m.entrant_b_id, ea.name, eb.name, ew.name, m.votes_a, m.votes_b "
		"FROM Matchups m "
		"LEFT JOIN Entrants ea ON ea.entrant_id = m.entrant_a_id "
		"LEFT JOIN Entrants eb ON eb.entrant_id = m.entrant_b_id "
		"LEFT JOIN Entrants ew ON ew.entrant_id = m.winner_entrant_id "
		"WHERE m.bracket_id = '{0}' "
		"ORDER BY m.`round`, m.slot".format(bracket_id))
	rows = cursor.fetchall()
	cursor.close()
	return rows

def getCommentsForBracket(bracket_id): #gets every comment for every matchup in a bracket
	cursor = conn.cursor()
	cursor.execute(
		"SELECT "
		"c.matchup_id, "
		"u.username, "
		"c.body, "
		"c.created_at "
		"FROM Comments c "
		"JOIN Users u ON c.user_id = u.user_id "
		"JOIN Matchups m ON c.matchup_id = m.matchup_id "
		"WHERE m.bracket_id = '{0}' "
		"ORDER BY c.created_at".format(bracket_id)
	)
	rows = cursor.fetchall()
	cursor.close()
	return rows

def userHasPredictionsForBracket(user_id, bracket_id):
	cursor = conn.cursor()
	cursor.execute(
		"SELECT COUNT(*) "
		"FROM Predictions p "
		"JOIN Matchups m ON p.matchup_id = m.matchup_id "
		"WHERE p.user_id = '{0}' "
		"AND m.bracket_id = '{1}'".format(
			user_id,
			bracket_id
		)
	)
	total = cursor.fetchone()[0]
	cursor.close()
	return total > 0

def getVotedMatchupIds(user_id, bracket_id): #returns python set that has matchupIDs where user has casted vote
	cursor = conn.cursor()
	cursor.execute(
		"SELECT v.matchup_id "
		"FROM Votes v "
		"JOIN Matchups m ON v.matchup_id = m.matchup_id "
		"WHERE v.user_id = '{0}' "
		"AND m.bracket_id = '{1}'".format(
			user_id,
			bracket_id
		)
	)
	rows = cursor.fetchall()
	cursor.close()
	voted_matchup_ids = set()
	for row in rows:
		voted_matchup_ids.add(row[0])
	return voted_matchup_ids

def getActiveRound(status):
	if status.startswith("round_"):
		return int(status.split("_")[1])
	return None

def simpleError(message): 
	return """
		<h2>Error</h2>
		<p>{0}</p>
		<p><a href='javascript:history.back()'>Go back</a></p>
	""".format(message)

@app.route('/bracket/<int:bracket_id>', methods=['GET'])
def view_bracket(bracket_id):
	bracket = getBracketInfo(bracket_id)
	if not bracket:
		return simpleError("Bracket does not exist.")
	matchups = getMatchupsForBracket(bracket_id)
	comments = getCommentsForBracket(bracket_id)
	current_user_id = getCurrentUserId()
	is_host = (
		current_user_id is not None
		and current_user_id == bracket[5]
	)
	active_round = getActiveRound(bracket[3])
	voted_matchup_ids = set()
	user_has_predictions = False
	if current_user_id is not None:
		voted_matchup_ids = getVotedMatchupIds(
			current_user_id,
			bracket_id
		)
		user_has_predictions = userHasPredictionsForBracket(
			current_user_id,
			bracket_id
		)
	return render_template(
		'bracket.html',
		bracket=bracket,
		matchups=matchups,
		comments=comments,
		is_host=is_host,
		active_round=active_round,
		voted_matchup_ids=voted_matchup_ids,
		user_has_predictions=user_has_predictions
	)

#@app.route('/bracket<bracket_id>', methods=['GET'])
#def view_bracket(bracket_id):
#	bracket  = getBracketInfo(bracket_id)
#	matchups = getMatchupsForBracket(bracket_id)
#	return render_template('bracket.html', bracket=bracket, matchups=matchups)
# end bracket view code

#Open the predictions
@app.route('/bracket/<int:bracket_id>/open_predictions', methods=['POST'])
@flask_login.login_required 
def open_predictions(bracket_id):
	current_user_id = getCurrentUserId()
	bracket = getBracketInfo(bracket_id)
	if not bracket:
		return simpleError("Bracket does not exist.")
	if current_user_id != bracket[5]:
		return simpleError("Only the bracket host can open predictions.")
	if bracket[3] != 'draft':
		return simpleError("Bracket must be in draft status first.")
	cursor = conn.cursor()
	try:
		cursor.execute(
			"UPDATE Brackets "
			"SET status = 'predictions_open' "
			"WHERE bracket_id = '{0}'".format(bracket_id)
		)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(url_for('view_bracket', bracket_id=bracket_id))


#Submitting predictions
@app.route('/bracket/<int:bracket_id>/predict', methods=['POST'])
@flask_login.login_required
def submit_predictions(bracket_id):
	current_user_id = getCurrentUserId()
	cursor = conn.cursor()
	try:
		cursor.execute(
			"SELECT matchup_id "
			"FROM Matchups "
			"WHERE bracket_id = '{0}' "
			"AND `round` = 1 "
			"ORDER BY slot".format(bracket_id)
		)
		round_1_matchups = cursor.fetchall()
		for matchup in round_1_matchups:
			matchup_id = matchup[0]
			selected_entrant_id = request.form.get('prediction_' + str(matchup_id))
			if not selected_entrant_id:
				raise Exception("You must choose a prediction for every Round 1 matchup.")
			cursor.execute(
				"INSERT INTO Predictions "
				"(user_id, matchup_id, selected_entrant_id) "
				"VALUES ('{0}', '{1}', '{2}')".format(
					current_user_id,
					matchup_id,
					selected_entrant_id
				)
			)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(url_for('view_bracket', bracket_id=bracket_id))


#Start Round 1
@app.route('/bracket/<int:bracket_id>/start_round_1', methods=['POST'])
@flask_login.login_required
def start_round_1(bracket_id):
	current_user_id = getCurrentUserId()
	bracket = getBracketInfo(bracket_id)
	if not bracket:
		return simpleError("Bracket does not exist.")
	if current_user_id != bracket[5]:
		return simpleError("Only the bracket host can start Round 1.")
	if bracket[3] != 'predictions_open':
		return simpleError("Bracket must be in predictions_open status.")
	cursor = conn.cursor()
	try:
		cursor.execute(
			"UPDATE Brackets "
			"SET status = 'round_1' "
			"WHERE bracket_id = '{0}'".format(bracket_id)
		)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(url_for('view_bracket', bracket_id=bracket_id))


#Cast Vote
@app.route('/matchup/<int:matchup_id>/vote', methods=['POST'])
@flask_login.login_required
def cast_vote(matchup_id):
	current_user_id = getCurrentUserId()
	bracket_id = request.form.get('bracket_id')
	selected_entrant_id = request.form.get('selected_entrant_id')
	cursor = conn.cursor()
	try:
		cursor.execute(
			"INSERT INTO Votes "
			"(user_id, matchup_id, selected_entrant_id) "
			"VALUES ('{0}', '{1}', '{2}')".format(
				current_user_id,
				matchup_id,
				selected_entrant_id
			)
		)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(url_for('view_bracket', bracket_id=bracket_id))


#Close Round
@app.route('/bracket/<int:bracket_id>/close_round/<int:round_number>', methods=['POST'])
@flask_login.login_required
def close_round_route(bracket_id, round_number):
	current_user_id = getCurrentUserId()
	bracket = getBracketInfo(bracket_id)
	if not bracket:
		return simpleError("Bracket does not exist.")
	if current_user_id != bracket[5]:
		return simpleError("Only the bracket host can close a round.")
	cursor = conn.cursor()
	try:
		cursor.callproc(
			'close_round',
			[
				bracket_id,
				round_number
			]
		)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(url_for('view_bracket', bracket_id=bracket_id))


#Add Comment
@app.route('/matchup/<int:matchup_id>/comment', methods=['POST'])
@flask_login.login_required
def add_comment(matchup_id):
	current_user_id = getCurrentUserId()
	bracket_id = request.form.get('bracket_id')
	body = request.form.get('body')
	cursor = conn.cursor()
	try:
		cursor.execute(
			"INSERT INTO Comments "
			"(user_id, matchup_id, body) "
			"VALUES ('{0}', '{1}', '{2}')".format(
				current_user_id,
				matchup_id,
				body
			)
		)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(url_for('view_bracket', bracket_id=bracket_id))

#Profile Page
@app.route('/profile/<int:user_id>')
def profile(user_id):
	cursor = conn.cursor()
	cursor.execute(
		"SELECT user_id, username, bio "
		"FROM Users "
		"WHERE user_id = '{0}'".format(user_id)
	)
	profile_user = cursor.fetchone()
	if not profile_user:
		cursor.close()
		return simpleError("User does not exist.")
	cursor.execute(
		"SELECT "
		"COUNT(prediction_id), "
		"COALESCE(SUM(points_earned), 0), "
		"COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) "
		"FROM Predictions "
		"WHERE user_id = '{0}'".format(user_id)
	)
	stats = cursor.fetchone()
	cursor.execute(
		"SELECT a.name, a.description "
		"FROM UserAchievements ua "
		"JOIN Achievements a "
		"ON ua.achievement_code = a.achievement_code "
		"WHERE ua.user_id = '{0}'".format(user_id)
	)
	achievements = cursor.fetchall()
	cursor.execute(
		"SELECT bracket_id, title, status "
		"FROM Brackets "
		"WHERE host_id = '{0}'".format(user_id)
	)
	hosted_brackets = cursor.fetchall()
	cursor.execute(
		"SELECT u.user_id, u.username "
		"FROM Follows f "
		"JOIN Users u ON f.follower_id = u.user_id "
		"WHERE f.followed_id = '{0}'".format(user_id)
	)
	followers = cursor.fetchall()
	cursor.execute(
		"SELECT u.user_id, u.username "
		"FROM Follows f "
		"JOIN Users u ON f.followed_id = u.user_id "
		"WHERE f.follower_id = '{0}'".format(user_id)
	)
	following = cursor.fetchall()
	current_user_id = getCurrentUserId()
	already_following = False
	if current_user_id is not None and current_user_id != user_id:
		cursor.execute(
			"SELECT COUNT(*) "
			"FROM Follows "
			"WHERE follower_id = '{0}' "
			"AND followed_id = '{1}'".format(
				current_user_id,
				user_id
			)
		)
		already_following = cursor.fetchone()[0] > 0
	cursor.close()
	return render_template(
		'profile.html',
		profile_user=profile_user,
		stats=stats,
		achievements=achievements,
		hosted_brackets=hosted_brackets,
		followers=followers,
		following=following,
		already_following=already_following
	)

#Follow User
@app.route('/profile/<int:user_id>/follow', methods=['POST'])
@flask_login.login_required
def follow_user(user_id):
	current_user_id = getCurrentUserId()
	if current_user_id == user_id:
		return simpleError("You cannot follow yourself.")
	cursor = conn.cursor()
	try:
		cursor.execute(
			"INSERT INTO Follows "
			"(follower_id, followed_id) "
			"VALUES ('{0}', '{1}')".format(
				current_user_id,
				user_id
			)
		)
		conn.commit()
	except Exception as error:
		conn.rollback()
		cursor.close()
		return simpleError(error)
	cursor.close()
	return redirect(
		url_for(
			'profile',
			user_id=user_id
		)
	)

#Unfollow User
@app.route('/profile/<int:user_id>/unfollow', methods=['POST'])
@flask_login.login_required
def unfollow_user(user_id):
	current_user_id = getCurrentUserId()
	cursor = conn.cursor()
	cursor.execute(
		"DELETE FROM Follows "
		"WHERE follower_id = '{0}' "
		"AND followed_id = '{1}'".format(
			current_user_id,
			user_id
		)
	)
	conn.commit()
	cursor.close()
	return redirect(
		url_for(
			'profile',
			user_id=user_id
		)
	)

#Leaderboard
@app.route('/leaderboard')
def leaderboard():
	cursor = conn.cursor()
	cursor.execute(
		"WITH totals AS ("
		"    SELECT "
		"        u.user_id, "
		"        u.username, "
		"        COALESCE(SUM(p.points_earned), 0) AS total_points, "
		"        COUNT(p.prediction_id) AS prediction_count "
		"    FROM Users u "
		"    LEFT JOIN Predictions p ON u.user_id = p.user_id "
		"    GROUP BY u.user_id, u.username "
		") "
		"SELECT "
		"    user_id, "
		"    username, "
		"    total_points, "
		"    prediction_count, "
		"    RANK() OVER (ORDER BY total_points DESC) AS rank_number, "
		"    DENSE_RANK() OVER (ORDER BY total_points DESC) AS dense_rank_number, "
		"    PERCENT_RANK() OVER (ORDER BY total_points DESC) AS percent_rank_number "
		"FROM totals "
		"ORDER BY total_points DESC, username"
	)
	rows = cursor.fetchall()
	cursor.close()
	return render_template(
		'leaderboard.html',
		rows=rows,
		current_user_id=getCurrentUserId()
	)

#Champion Path
@app.route('/bracket/<int:bracket_id>/champion_path')
def champion_path(bracket_id):
	bracket = getBracketInfo(bracket_id)
	if not bracket:
		return simpleError("Bracket does not exist.")
	if bracket[3] != 'completed':
		return simpleError("Bracket must be completed first.")
	cursor = conn.cursor()
	cursor.execute(
		"WITH RECURSIVE ChampionPath AS ("
		"    SELECT "
		"        m.matchup_id, "
		"        m.bracket_id, "
		"        m.`round`, "
		"        m.slot, "
		"        m.entrant_a_id, "
		"        m.entrant_b_id, "
		"        m.winner_entrant_id "
		"    FROM Matchups m "
		"    WHERE m.bracket_id = '{0}' "
		"      AND m.`round` = ("
		"          SELECT MAX(`round`) "
		"          FROM Matchups "
		"          WHERE bracket_id = '{0}'"
		"      ) "
		"      AND m.winner_entrant_id IS NOT NULL "
		"    UNION ALL "
		"    SELECT "
		"        m.matchup_id, "
		"        m.bracket_id, "
		"        m.`round`, "
		"        m.slot, "
		"        m.entrant_a_id, "
		"        m.entrant_b_id, "
		"        m.winner_entrant_id "
		"    FROM Matchups m "
		"    JOIN ChampionPath cp "
		"      ON m.bracket_id = cp.bracket_id "
		"     AND m.winner_entrant_id = cp.winner_entrant_id "
		"     AND m.`round` = cp.`round` - 1"
		") "
		"SELECT "
		"    cp.`round`, "
		"    cp.slot, "
		"    ea.name, "
		"    eb.name, "
		"    ew.name "
		"FROM ChampionPath cp "
		"LEFT JOIN Entrants ea ON cp.entrant_a_id = ea.entrant_id "
		"LEFT JOIN Entrants eb ON cp.entrant_b_id = eb.entrant_id "
		"LEFT JOIN Entrants ew ON cp.winner_entrant_id = ew.entrant_id "
		"ORDER BY cp.`round`".format(bracket_id)
	)
	path_rows = cursor.fetchall()
	cursor.close()
	return render_template(
		'champion_path.html',
		bracket=bracket,
		path_rows=path_rows
	)


# Admin SQL Console
@app.route('/admin/sql', methods=['GET', 'POST'])
@flask_login.login_required
def admin_sql():
    if flask_login.current_user.id != 'admin':
        return simpleError(
            "Only the admin user can access the SQL console."
        )
    sql = ''
    columns = []
    rows = []
    message = None
    error_message = None
    if request.method == 'POST':
        sql = request.form.get('sql', '').strip()
        if not sql:
            error_message = "Enter a SQL statement."
        elif ';' in sql.rstrip(';'):
            error_message = "Run one SQL statement at a time."

        else:
            cursor = conn.cursor()

            try:
                cursor.execute(sql)
                if cursor.with_rows:
                    columns = list(cursor.column_names)
                    rows = cursor.fetchall()
                    message = (
                        "Query returned "
                        + str(len(rows))
                        + " row(s)."
                    )
                else:
                    conn.commit()
                    message = (
                        "Statement completed. "
                        + str(cursor.rowcount)
                        + " row(s) affected."
                    )
            except mysql.connector.Error as error:
                conn.rollback()
                error_message = str(error)
            cursor.close()
    return render_template(
        'admin.html',
        sql=sql,
        columns=columns,
        rows=rows,
        message=message,
        error_message=error_message
    )


# default page
@app.route('/', methods=['GET', 'POST'])
def home():
	if request.method == 'POST':
		flask_login.logout_user()
	try:
		username = flask_login.current_user.id
		return render_template('hello.html', name=username, message='welcome to VERSUS')
	except AttributeError:  # not logged in
		return render_template('hello.html', message=None)


if __name__ == "__main__":
	# this is invoked when in the shell you run
	# $ python app.py
	app.debug = True
	app.run(port=5001, debug=True)
