# app.py
# This is the main flask application file
# It contains all the routes and the logic for the web application

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, send_file, flash, send_from_directory
)

import os
import re
import subprocess
import bcrypt
import pytz
import psycopg2
import psycopg2.extras

from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from itsdangerous import (
    URLSafeTimedSerializer, SignatureExpired, BadSignature
)

from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler

from dotenv import load_dotenv
from translations import TRANSLATIONS

# -----------------------------
# Env / basic setup
# -----------------------------
load_dotenv()

ATHENS_TZ = pytz.timezone("Europe/Athens")
UTC_TZ = pytz.utc
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret")
app.permanent_session_lifetime = timedelta(days=30)
s = URLSafeTimedSerializer(app.secret_key)

# (Προαιρετικό) πιο “σωστό” logging σε production
# Αν θέλεις πιο verbose logs, μπορείς να βάλεις:
# import logging
# logging.basicConfig(level=logging.INFO)

# -----------------------------
# Uploads
# -----------------------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -------------------------------------------------------------------
# Settings Email (μέσω Gmail) - Flask-Mail ONLY
# -------------------------------------------------------------------
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USE_TLS"] = False

app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

# καλύτερα να “δένει” με το username για να μην έχει mismatch
app.config["MAIL_DEFAULT_SENDER"] = (
    "TheraHand",
    app.config["MAIL_USERNAME"] or "handexercises.app@gmail.com"
)

mail = Mail(app)

if not app.config["MAIL_USERNAME"] or not app.config["MAIL_PASSWORD"]:
    print("⚠️ MAIL_USERNAME/MAIL_PASSWORD missing from env (Render Environment Variables)")

# -------------------------------------------------------------------
# ✅ Settings Database (Postgres via DATABASE_URL)
# -------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Render μερικές φορές δίνει postgres://, το κάνουμε postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


class TranslatingCursor:
    """
    Μεταφράζει λίγα MySQL-specific πράγματα σε Postgres,
    ώστε να ΜΗΝ αλλάξεις SQL μέσα στα routes.
    """
    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, query, params=None):
        q = query
        q = q.replace("UTC_TIMESTAMP()", "(NOW() AT TIME ZONE 'UTC')")
        q = q.replace("CURDATE()", "CURRENT_DATE")
        q = re.sub(r"DATE\s*\(\s*created_at\s*\)", "created_at::date", q, flags=re.IGNORECASE)
        return self._cur.execute(q, params)

    def executemany(self, query, param_seq):
        q = query
        q = q.replace("UTC_TIMESTAMP()", "(NOW() AT TIME ZONE 'UTC')")
        q = q.replace("CURDATE()", "CURRENT_DATE")
        q = re.sub(r"DATE\s*\(\s*created_at\s*\)", "created_at::date", q, flags=re.IGNORECASE)
        return self._cur.executemany(q, param_seq)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        return self._cur.close()

    def __getattr__(self, name):
        return getattr(self._cur, name)


class PostgresConnection:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    def _connect(self):
        if self._conn is None or self._conn.closed != 0:
            self._conn = psycopg2.connect(self.dsn)
        return self._conn

    def cursor(self, cursorclass=None):
        conn = self._connect()

        # Συμβατότητα: cursor(MySQLdb.cursors.DictCursor)
        if cursorclass is not None:
            real = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            return TranslatingCursor(real)

        real = conn.cursor()
        return TranslatingCursor(real)

    def commit(self):
        self._connect().commit()

    def ping(self, reconnect=False):
        try:
            c = self.cursor()
            c.execute("SELECT 1;")
            c.close()
        except Exception:
            if reconnect:
                self._conn = None
                self._connect()


class PG:
    def __init__(self, dsn: str):
        self.connection = PostgresConnection(dsn)


# ✅ Κρατάμε το ίδιο όνομα "mysql" για να ΜΗΝ αλλάξεις routes
mysql = PG(DATABASE_URL)


# ✅ Fake MySQLdb.cursors.DictCursor για να μη πειράξεις τα routes
class MySQLdb:
    class cursors:
        DictCursor = object()


# -----------------------------
# Static assets routes
# -----------------------------
@app.route("/assets/first_game/<path:filename>")
def first_game_assets(filename):
    folder = os.path.join(BASE_DIR, "hand_exercises", "first_game")
    return send_from_directory(folder, filename)

@app.route("/assets/third_game/<path:filename>")
def third_game_assets(filename):
    folder = os.path.join(BASE_DIR, "hand_exercises", "third_game")
    return send_from_directory(folder, filename)

@app.route("/assets/last_game/<path:filename>")
def last_game_assets(filename):
    folder = os.path.join(BASE_DIR, "hand_exercises", "last_game")
    return send_from_directory(folder, filename)


# -----------------------------
# Translations helpers
# -----------------------------
def get_user_lang_by_email(email: str) -> str:
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT language FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    cur.close()

    lang = (row.get("language") if row else None) or "el"
    return lang if lang in ("el", "en") else "el"


def get_lang():
    return session.get("lang", "el")


def get_t_dict():
    lang = get_lang()
    base = TRANSLATIONS.get("el", {})
    current = TRANSLATIONS.get(lang, base)
    merged = {**base, **current}
    return merged, lang


@app.context_processor
def inject_translations():
    t_dict, lang = get_t_dict()
    return {"t": t_dict, "lang": lang}


# -----------------------------
# DB keep-alive
# -----------------------------
@app.before_request
def ensure_db_alive():
    try:
        mysql.connection.ping(True)
    except Exception:
        pass


# -----------------------------
# PWA
# -----------------------------
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest",
                               mimetype="application/manifest+json")

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory("static", "service-worker.js",
                               mimetype="application/javascript")

@app.after_request
def add_pwa_no_cache_headers(response):
    if request.path in ("/service-worker.js", "/manifest.webmanifest"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# -----------------------------
# DB test
# -----------------------------
@app.route("/db_test")
def db_test():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()
    cur.close()
    return f"DB OK – users rows: {count}"


# -------------------------------------------------------------------
# 1️⃣ Welcome Page
# -------------------------------------------------------------------
@app.route("/")
def welcome():
    if "username" in session:
        return redirect(url_for("menu"))
    return render_template("welcome_page/welcome_page.html")


# -------------------------------------------------------------------
# 2️⃣ Index Page
# -------------------------------------------------------------------
@app.route("/index")
def index():
    if "username" in session:
        return redirect(url_for("menu"))
    return render_template("index.html")


# -------------------------------------------------------------------
# 3️⃣ Προφίλ χρήστη
# -------------------------------------------------------------------
@app.route("/profile/<username>")
def profile(username):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        session.clear()
        return redirect(url_for("index"))

    cursor.execute("SELECT * FROM game_statistics WHERE username = %s", (username,))
    stats = cursor.fetchall()
    cursor.close()

    is_owner = ("username" in session and session["username"] == username)
    session["avatar"] = user.get("avatar")

    return render_template("profile.html", user=user, stats=stats, is_owner=is_owner)


# -----------------------------
# Normalize / display helpers
# -----------------------------
def normalize_result_key(result: str) -> str:
    if not result:
        return ""
    r = str(result).strip().lower()
    mapping = {
        "completed": "completed",
        "complete": "completed",
        "done": "completed",

        "win": "win",
        "won": "win",
        "victory": "win",

        "lose": "lose",
        "loss": "lose",
        "failed": "lose",

        "νικη": "win",
        "νίκη": "win",
        "επιτυχια": "win",
        "επιτυχία": "win",

        "ηττα": "lose",
        "ήττα": "lose",
        "αποτυχια": "lose",
        "αποτυχία": "lose",

        "game over": "game_over",
        "game_over": "game_over",
        "gameover": "game_over",

        "exit": "exit",
        "quit": "exit",
    }
    return mapping.get(r, r)


def display_result(db_result: str, lang: str) -> str:
    key = normalize_result_key(db_result)

    tt = TRANSLATIONS.get(lang, TRANSLATIONS.get("el", {}))
    base = TRANSLATIONS.get("el", {})

    key_to_label = {
        "completed": "result_completed",
        "win": "result_win",
        "lose": "result_lose",
        "game_over": "result_game_over",
        "exit": "result_exit",
    }

    label_key = key_to_label.get(key)
    if not label_key:
        return db_result

    return tt.get(label_key) or base.get(label_key) or db_result


def normalize_game_key(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    mapping = {
        "Άσκηση 1": "exercise_1",
        "Άσκηση 2": "exercise_2",
        "Άσκηση 3": "exercise_3",
        "Άσκηση 4": "exercise_4",
        "Exercise 1": "exercise_1",
        "Exercise 2": "exercise_2",
        "Exercise 3": "exercise_3",
        "Exercise 4": "exercise_4",
    }
    return mapping.get(name, name)


def display_game_name(db_game_name: str, lang: str) -> str:
    key = normalize_game_key(db_game_name)
    tt = TRANSLATIONS.get(lang, TRANSLATIONS.get("el", {}))
    base = TRANSLATIONS.get("el", {})

    key_to_label = {
        "exercise_1": "exercise_1_title",
        "exercise_2": "exercise_2_title",
        "exercise_3": "exercise_3_title",
        "exercise_4": "exercise_4_title",
    }

    label_key = key_to_label.get(key)
    if not label_key:
        return db_game_name

    return tt.get(label_key) or base.get(label_key) or db_game_name


# -------------------------------------------------------------------
# Forgot / Reset Password (✅ Flask-Mail ONLY)
# -------------------------------------------------------------------
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form["email"].strip()

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if not user:
        flash("Το email δεν βρέθηκε.")
        return redirect(url_for("forgot_password"))

    lang = get_user_lang_by_email(email)
    tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

    token = s.dumps(email, salt="password-reset")
    reset_link = url_for("reset_password", token=token, _external=True)

    subject = tt.get("reset_subject", "Password Reset")
    message = f"""{tt.get("email_hi","Hi")},

{tt.get("reset_email_intro","A password reset was requested for your account.")}

{tt.get("reset_email_click","Click the link below to set a new password:")}

{reset_link}

{tt.get("reset_email_expire","The link is valid for 24 hours.")}

TheraHand Team
"""

    try:
        msg = Message(
            subject=subject,
            recipients=[email],
            body=message
        )
        mail.send(msg)
    except Exception:
        app.logger.exception("⚠️ forgot_password email error")
        flash("Σφάλμα αποστολής email. Δοκίμασε αργότερα.")
        return redirect(url_for("forgot_password"))

    flash(tt.get("reset_email_sent", "Reset email sent."))
    return redirect(url_for("index"))


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = s.loads(token, salt="password-reset", max_age=86400)
    except SignatureExpired:
        flash("Ο σύνδεσμος έληξε. Ζήτησε νέο.")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Μη έγκυρος σύνδεσμος.")
        return redirect(url_for("forgot_password"))

    lang = get_user_lang_by_email(email)
    tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

    if request.method == "POST":
        new_pass = request.form["password"]
        confirm = request.form.get("confirm_password")

        if confirm is not None and new_pass != confirm:
            flash(tt.get("passwords_mismatch", "Passwords do not match."))
            return redirect(url_for("reset_password", token=token))

        hashed = bcrypt.hashpw(new_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))
        mysql.connection.commit()
        cur.close()

        flash(tt.get("password_reset_success", "Password changed successfully. You can log in."))
        return redirect(url_for("index"))

    return render_template("reset_password.html", email=email)


# -------------------------------------------------------------------
# Edit profile
# -------------------------------------------------------------------
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "username" not in session:
        return redirect(url_for("index"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session["username"],))
    user = cursor.fetchone()

    if request.method == "POST":
        new_username = request.form.get("new_username")
        old_username = user["username"]

        cursor.execute(
            "UPDATE users SET username=%s WHERE id=%s",
            (new_username, user["id"])
        )

        cursor.execute(
            "UPDATE game_statistics SET username=%s WHERE username=%s",
            (new_username, old_username)
        )

        mysql.connection.commit()
        cursor.close()

        session["username"] = new_username
        return redirect(url_for("profile", username=new_username))

    cursor.close()
    return render_template("edit_profile.html", user=user)


# -------------------------------------------------------------------
# Change password (με email ειδοποίησης)
# -------------------------------------------------------------------
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "username" not in session:
        return redirect(url_for("index"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session["username"],))
    user = cursor.fetchone()

    if request.method == "POST":
        old_pw = request.form.get("old_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")

        lang = (user.get("language") or "el")
        if lang not in ("el", "en"):
            lang = "el"
        tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

        if not bcrypt.checkpw(old_pw.encode(), user["password"].encode()):
            return f"""
            <script>
                alert("{tt.get('old_password_wrong','Wrong old password!')}");
                window.history.back();
            </script>
            """

        if len(new_pw) < 8:
            return f"""
            <script>
                alert("{tt.get('password_min_length','Password must be at least 8 characters!')}");
                window.history.back();
            </script>
            """

        if new_pw != confirm_pw:
            return f"""
            <script>
                alert("{tt.get('passwords_mismatch','Passwords do not match!')}");
                window.history.back();
            </script>
            """

        hashed_pw = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()

        cursor.execute(
            "UPDATE users SET password=%s WHERE id=%s",
            (hashed_pw, user["id"])
        )
        mysql.connection.commit()

        # Email notification
        try:
            msg = Message(
                subject=tt.get("password_changed_subject", "🔐 Password changed"),
                recipients=[user["email"]],
                body=f"{tt.get('email_hi','Hi')} {user['username']},\n{tt.get('password_changed_body','Your password was changed successfully.')}"
            )
            mail.send(msg)
        except Exception:
            app.logger.exception("⚠️ change_password email error")

        cursor.close()

        return f"""
        <script>
            alert("{tt.get('password_changed_logout_alert','Password changed successfully. You will be logged out.')}");
            window.location.href = '/logout';
        </script>
        """

    cursor.close()
    return render_template("change_password.html")


# -------------------------------------------------------------------
# Delete account
# -------------------------------------------------------------------
@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "username" not in session:
        return redirect(url_for("index"))

    username = session["username"]

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT language FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()

    lang = (user.get("language") if user else None) or "el"
    if lang not in ("el", "en"):
        lang = "el"
    tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

    cursor.execute("DELETE FROM users WHERE username = %s", (username,))
    mysql.connection.commit()
    cursor.close()

    session.clear()

    return f"""
    <script>
        alert("{tt.get('account_deleted_alert','Account deleted successfully.')}");
        window.location.href = "/";
    </script>
    """


# -------------------------------------------------------------------
# Theme change
# -------------------------------------------------------------------
@app.route("/change_theme", methods=["POST"])
def change_theme():
    if "username" not in session:
        return redirect(url_for("index"))

    new_theme = request.form.get("theme")

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET theme=%s WHERE username=%s",
                   (new_theme, session["username"]))
    mysql.connection.commit()
    cursor.close()
    session["theme"] = new_theme

    return """
    <script>
        alert('Το θέμα άλλαξε επιτυχώς!');
        window.location.href = '/profile/%s';
    </script>
    """ % session["username"]


@app.route("/api/theme", methods=["POST"])
def api_theme():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    new_theme = data.get("theme")

    if new_theme not in ("Light", "Dark"):
        return jsonify({"ok": False, "error": "Invalid theme"}), 400

    cursor = mysql.connection.cursor()
    cursor.execute(
        "UPDATE users SET theme=%s WHERE username=%s",
        (new_theme, session["username"])
    )
    mysql.connection.commit()
    cursor.close()

    session["theme"] = new_theme
    return jsonify({"ok": True, "theme": new_theme})


# -------------------------------------------------------------------
# Avatar upload
# -------------------------------------------------------------------
@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "username" not in session:
        return redirect(url_for("index"))

    avatar = request.files.get("avatar")
    if not avatar:
        return redirect(url_for("profile", username=session["username"]))

    filename = secure_filename(session["username"] + "_avatar.png")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    avatar.save(filepath)

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET avatar=%s WHERE username=%s",
                   (filename, session["username"]))
    session["avatar"] = filename

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for("profile", username=session["username"]))


# -------------------------------------------------------------------
# 4️⃣ Έλεγχος / Εγγραφή χρήστη
# -------------------------------------------------------------------
@app.route("/check_user", methods=["POST"])
def check_user():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return "Συμπλήρωσε όλα τα πεδία!", 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user:
        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            pref_lang = session.get("lang")
            db_lang = user.get("language")
            lang = pref_lang or db_lang or "el"
            if lang not in ("el", "en"):
                lang = "el"
            session["lang"] = lang
            session.permanent = True
            session.modified = True

            if db_lang != lang:
                cursor.execute("UPDATE users SET language=%s WHERE id=%s", (lang, user["id"]))
                mysql.connection.commit()

            cursor.close()
            return "menu" if user.get("profile_completed") else "steps"

        cursor.close()
        return "Λάθος κωδικός!", 401

    cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
    existing_username = cursor.fetchone()
    if existing_username:
        cursor.close()
        return "Το username υπάρχει ήδη!", 409

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    lang = session.get("lang") or "el"
    if lang not in ("el", "en"):
        lang = "el"

    cursor.execute("""
        INSERT INTO users (username, email, password, language, profile_completed, reminder)
        VALUES (%s, %s, %s, %s, FALSE, 'no')
    """, (username, email, hashed, lang))

    mysql.connection.commit()

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    new_user = cursor.fetchone()
    cursor.close()

    session["user_id"] = new_user["id"]
    session["username"] = username
    session["lang"] = lang
    session.permanent = True
    session.modified = True

    return "steps"


# -------------------------------------------------------------------
# Signup steps
# -------------------------------------------------------------------
@app.route("/sign_up/step<int:step_number>")
def sign_up_steps(step_number):
    if "username" not in session:
        return redirect(url_for("index"))
    return render_template(f"sign_up/step{step_number}.html")


@app.route("/save_step1", methods=["POST"])
def save_step1():
    if "user_id" not in session:
        return redirect(url_for("index"))
    age = request.form.get("age")
    goal = request.form.get("goal")
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET age=%s, goal=%s WHERE id=%s", (age, goal, session["user_id"]))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for("sign_up_steps", step_number=2))


@app.route("/save_step2", methods=["POST"])
def save_step2():
    if "user_id" not in session:
        return redirect(url_for("index"))
    exercise_time = request.form.get("exercise_time")
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET exercise_time=%s WHERE id=%s", (exercise_time, session["user_id"]))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for("sign_up_steps", step_number=3))


@app.route("/save_step3", methods=["POST"])
def save_step3():
    if "user_id" not in session:
        return redirect(url_for("index"))

    reminder = request.form.get("reminder")
    exercise_time = request.form.get("exercise_time")

    if reminder == "no":
        exercise_time = None

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users
        SET reminder=%s, exercise_time=%s
        WHERE id=%s
    """, (reminder, exercise_time, session["user_id"]))

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for("sign_up_steps", step_number=4))


@app.route("/complete_profile", methods=["POST"])
def complete_profile():
    if "user_id" not in session:
        return redirect(url_for("index"))

    stage = request.form.get("stage")
    type_ = request.form.get("type")
    frequency = request.form.get("frequency")
    duration = request.form.get("duration")
    next_exercise = request.form.get("next_exercise")

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users
        SET profile_completed = TRUE,
            stage = %s,
            type = %s,
            frequency = %s,
            duration = %s,
            next_exercise = %s
        WHERE id = %s
    """, (stage, type_, frequency, duration, next_exercise, session["user_id"]))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for("menu"))


# -------------------------------------------------------------------
# 6️⃣ Reminders μέσω email (Scheduler)
# -------------------------------------------------------------------
def send_daily_reminders():
    with app.app_context():
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT username, email, exercise_time, language
            FROM users
            WHERE reminder = 'yes' AND exercise_time IS NOT NULL
        """)
        users = cursor.fetchall()
        cursor.close()

        now = datetime.now(pytz.timezone("Europe/Athens")).strftime("%H:%M")

        for user in users:
            raw_time = str(user["exercise_time"]).strip()

            if ":" in raw_time:
                parts = raw_time.split(":")
                ex_time_str = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
            else:
                ex_time_str = raw_time

            if ex_time_str == now:
                lang = (user.get("language") or "el")
                if lang not in ("el", "en"):
                    lang = "el"
                tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

                try:
                    msg = Message(
                        subject=tt["email_reminder_subject"],
                        recipients=[user["email"]],
                        body=f"{tt['email_hi']} {user['username']}!\n\n{tt['email_reminder_body']}"
                    )
                    mail.send(msg)
                    print(f"✅ Reminder email sent to {user['username']} ({lang})")
                except Exception:
                    app.logger.exception("⚠️ Reminder email error")


scheduler = BackgroundScheduler(timezone="Europe/Athens")
scheduler.add_job(func=send_daily_reminders, trigger="cron", minute="*")

# ✅ Render/production: ξεκινάει κανονικά (WERKZEUG_RUN_MAIN δεν ισχύει στο Render)
if not app.debug:
    scheduler.start()


@app.route("/update_reminder", methods=["POST"])
def update_reminder():
    if "username" not in session:
        return redirect(url_for("index"))

    reminder = request.form.get("reminder")
    exercise_time = request.form.get("exercise_time")

    if reminder == "no":
        exercise_time = None

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users
        SET reminder=%s, exercise_time=%s
        WHERE username=%s
    """, (reminder, exercise_time, session["username"]))

    mysql.connection.commit()
    cursor.close()

    return """
    <script>
        alert("Οι ρυθμίσεις υπενθύμισης αποθηκεύτηκαν!");
        window.location.href = '/profile/%s';
    </script>
    """ % session["username"]


# -------------------------------------------------------------------
# 7️⃣ Menu Page
# -------------------------------------------------------------------
@app.route("/menu")
def menu():
    if "username" not in session:
        return redirect(url_for("index"))
    return render_template("menu.html", username=session["username"])


# -------------------------------------------------------------------
# 8️⃣ Dashboard
# -------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("index"))

    username = session["username"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT
            game_name,
            COUNT(*) AS plays,
            SUM(score) AS total_score,
            AVG(score) AS avg_score,
            SUM(time_seconds) AS total_time
        FROM game_statistics
        WHERE username = %s
        GROUP BY game_name
        ORDER BY game_name;
    """, (username,))

    stats = cursor.fetchall()
    cursor.close()

    total_plays = sum(row["plays"] for row in stats)
    total_score = sum(row["total_score"] or 0 for row in stats)
    total_time = sum(row["total_time"] or 0 for row in stats)

    return render_template("dashboard.html",
                           username=username,
                           stats=stats,
                           total_plays=total_plays,
                           total_score=total_score,
                           total_time=total_time)


# -------------------------------------------------------------------
# 9️⃣ Add stat
# -------------------------------------------------------------------
@app.route("/add_stat", methods=["POST"])
def add_stat():
    data = request.get_json()

    username = data.get("username") or session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized – no username provided"}), 401

    game_name = data.get("game_name")
    score = data.get("score")
    time_seconds = data.get("time_seconds")
    result = data.get("result")
    age = data.get("age")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT age FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    db_age = user["age"] if user else age

    cursor.execute("""
        INSERT INTO game_statistics (username, age, game_name, score, time_seconds, result, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
    """, (username, db_age, game_name, score, time_seconds, result))
    mysql.connection.commit()
    cursor.close()

    print(f"📊 Στατιστικά αποθηκεύτηκαν για τον {username} ({game_name})")

    return jsonify({"message": "✅ Τα στατιστικά αποθηκεύτηκαν επιτυχώς!"}), 200


# -------------------------------------------------------------------
# 🔟 Start exercises
# -------------------------------------------------------------------
BASE_GAME_FOLDER = os.path.join(os.getcwd(), "hand_exercises")

@app.route("/start/<int:exercise_num>", methods=["POST"])
def start_exercise(exercise_num):
    if "username" not in session:
        return redirect(url_for("index"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT age, language FROM users WHERE username = %s", (session["username"],))
    user = cursor.fetchone()
    cursor.close()

    username = session["username"]
    age = user["age"] if user else 0

    lang = (user.get("language") if user else None) or session.get("lang") or "el"
    if lang not in ("el", "en"):
        lang = "el"

    game_paths = {
        1: os.path.join(BASE_GAME_FOLDER, "first_game", "first_game.py"),
        2: os.path.join(BASE_GAME_FOLDER, "second_game", "second_game_shape_moving.py"),
        3: os.path.join(BASE_GAME_FOLDER, "third_game", "game_8_puzzle_main.py"),
        4: os.path.join(BASE_GAME_FOLDER, "last_game", "last_game.py")
    }

    game_path = game_paths.get(exercise_num)

    if not game_path or not os.path.exists(game_path):
        print("❌ Δεν βρέθηκε αρχείο για άσκηση:", exercise_num)
        return f"Το παιχνίδι {exercise_num} δεν βρέθηκε.", 404

    try:
        subprocess.Popen(["python", game_path, username, str(age), lang])
        print(f"🎮 Εκκίνηση {os.path.basename(game_path)} για {username} ({age} ετών)")
    except Exception:
        app.logger.exception("⚠️ Σφάλμα εκτέλεσης παιχνιδιού")

    return redirect(url_for("dashboard"))


# -------------------------------------------------------------------
# 11️⃣ Exercises pages
# -------------------------------------------------------------------
@app.route("/exercise_1")
def exercise_1():
    return render_template("exercises/exercise_1.html")

@app.route("/exercise_2")
def exercise_2():
    return render_template("exercises/exercise_2.html")

@app.route("/exercise_3")
def exercise_3():
    return render_template("exercises/exercise_3.html")

@app.route("/exercise_4")
def exercise_4():
    return render_template("exercises/exercise_4.html")


# -------------------------------------------------------------------
# 12️⃣ API stats
# -------------------------------------------------------------------
@app.route("/api/stats")
def api_stats():
    if "username" not in session:
        return jsonify([])

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT username, age, game_name, score, time_seconds, result, created_at
        FROM game_statistics
        WHERE username = %s
        ORDER BY created_at DESC
    """, (session["username"],))
    stats = cursor.fetchall()
    cursor.close()

    lang = session.get("lang", "el")

    for row in stats:
        row["game_name"] = display_game_name(row.get("game_name"), lang)
        row["result"] = display_result(row.get("result"), lang)

        dt = row.get("created_at")
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = UTC_TZ.localize(dt)
            row["created_at"] = dt.astimezone(ATHENS_TZ).isoformat()
        else:
            row["created_at"] = str(dt)

    return jsonify(stats)


# -------------------------------------------------------------------
# Today (όπως είχες)
# -------------------------------------------------------------------
@app.route("/today")
def today():
    if "username" not in session:
        return redirect(url_for("index"))

    username = session["username"]

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT game_name, COUNT(*) AS plays, SUM(score) AS total_score, SUM(time_seconds) AS total_time
        FROM game_statistics
        WHERE username = %s AND DATE(created_at) = CURDATE()
        GROUP BY game_name
    """, (username,))
    today_stats = cursor.fetchall()
    cursor.close()

    lang = session.get("lang", "el")
    for row in today_stats:
        row["game_name"] = display_game_name(row["game_name"], lang)

    total_plays = sum(item["plays"] for item in today_stats)
    total_score = sum(item["total_score"] or 0 for item in today_stats)
    total_time = sum(item["total_time"] or 0 for item in today_stats)

    return render_template("today.html",
                           username=username,
                           today_stats=today_stats,
                           total_plays=total_plays,
                           total_score=total_score,
                           total_time=total_time)


@app.route("/api/today_stats")
def api_today_stats():
    if "username" not in session:
        return jsonify([])

    username = session["username"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT game_name, COUNT(*) AS plays
        FROM game_statistics
        WHERE username = %s AND DATE(created_at) = CURDATE()
        GROUP BY game_name
    """, (username,))
    data = cursor.fetchall()
    cursor.close()

    lang = session.get("lang", "el")
    for row in data:
        row["game_name"] = display_game_name(row.get("game_name"), lang)

    return jsonify(data)


@app.route("/api_dashboard_stats")
def api_dashboard_stats():
    if "username" not in session:
        return jsonify([])

    username = session["username"]
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT game_name,
               COUNT(*) AS plays,
               ROUND(AVG(score), 1) AS avg_score,
               MAX(created_at) AS last_played
        FROM game_statistics
        WHERE username = %s
        GROUP BY game_name
        ORDER BY game_name
    """, (username,))

    data = cursor.fetchall()
    cursor.close()

    lang = session.get("lang", "el")
    for row in data:
        row["game_name"] = display_game_name(row.get("game_name"), lang)

    return jsonify(data)


# -------------------------------------------------------------------
# Language
# -------------------------------------------------------------------
@app.route("/change_language", methods=["POST"])
def change_language():
    new_lang = request.form.get("language", "el")
    if new_lang not in ("el", "en"):
        new_lang = "el"

    session["lang"] = new_lang
    session.permanent = True
    session.modified = True

    if "username" in session:
        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE users SET language=%s WHERE username=%s",
            (new_lang, session["username"])
        )
        mysql.connection.commit()
        cursor.close()

    return redirect(request.referrer or url_for("welcome"))


@app.before_request
def load_language():
    if request.path.startswith("/sign_up/"):
        if session.get("lang") not in ("el", "en"):
            session["lang"] = "el"
        return

    if "username" in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT language FROM users WHERE username=%s", (session["username"],))
        user = cursor.fetchone()
        cursor.close()

        db_lang = (user.get("language") if user else None) or "el"
        if db_lang not in ("el", "en"):
            db_lang = "el"
        session["lang"] = db_lang
    else:
        if session.get("lang") not in ("el", "en"):
            session["lang"] = "el"


# -------------------------------------------------------------------
# Play pages
# -------------------------------------------------------------------
@app.route("/play/<int:ex_id>")
def play_exercise(ex_id):
    if "username" not in session:
        return redirect(url_for("index"))

    if ex_id == 1:
        return render_template("play_exercise1.html")
    if ex_id == 2:
        return render_template("play_exercise2.html")
    if ex_id == 3:
        return render_template("play_exercise3.html")
    if ex_id == 4:
        return render_template("play_exercise4.html")

    return "Not found", 404


# -------------------------------------------------------------------
# 13️⃣ Logout
# -------------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))


# -------------------------------------------------------------------
# 14️⃣ Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
