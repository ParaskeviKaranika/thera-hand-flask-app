#app.py
#This is the main flask application file 
#It contains all the routes and the logic for the web application

from flask import Flask, render_template, request, jsonify, redirect, url_for, session,send_file #import flask modules
import psycopg2
import psycopg2.extras
import re

import bcrypt #import bcrypt for the password hashing
from flask_mail import Mail, Message  #import flask mail module
from apscheduler.schedulers.background import BackgroundScheduler  #import background scheduler
from datetime import datetime #import datetime module
import pytz  #import pytz module for timezone handling
import os  #import os module for file path handling
import subprocess  #import subprocess module to run external scripts
from werkzeug.utils import secure_filename  #import secure filename for file upload handling
from itsdangerous import URLSafeTimedSerializer  #import url safe timed serializer for token generation
from flask import url_for  #import url for generating urls
from flask import flash   #import flash for flashing messages
import smtplib  #import smtplib for sending emails
from email.mime.text import MIMEText  #import mime text for email content
from datetime import timedelta #import timedelta for session lifetime
from reportlab.pdfgen import canvas  #import report lab for pdf generation
from reportlab.lib.pagesizes import A4  #import a4 image for pdf size
from reportlab.lib.utils import ImageReader  #import image reader for reading images
from io import BytesIO  #import bytes io for byte stream handling
from flask import session #import session for session management
from translations import TRANSLATIONS #import translations dictionary
from itsdangerous import SignatureExpired, BadSignature  #import exceptions for taken handling
from flask import send_from_directory  #import send from directory for serving static files


from dotenv import load_dotenv
load_dotenv()

ATHENS_TZ = pytz.timezone("Europe/Athens")
UTC_TZ = pytz.utc
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#Flask app configuration
app = Flask(__name__)
#App secret key for session management
#app.secret_key = 'super_secret_key'
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret")

#App session lifetime configuration
app.permanent_session_lifetime = timedelta(days=30)
#Serializer for generating tokens
s = URLSafeTimedSerializer(app.secret_key)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# -------------------------------------------------------------------
# Settings MySQL (XAMPP)
# -------------------------------------------------------------------






# -------------------------------------------------------------------
# Settings Email (μέσω Gmail)
# -------------------------------------------------------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False

app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")

app.config['MAIL_DEFAULT_SENDER'] = ('TheraHand', 'handexercises.app@gmail.com')
app.config["MAIL_TIMEOUT"] = 15


mail = Mail(app)
import threading
import time

def send_email_async(subject: str, recipients: list[str], body: str, attempts: int = 3, delay_sec: int = 2):
    """
    Στέλνει email σε background thread με retries.
    Έτσι ΔΕΝ μπλοκάρει το request (άρα δεν έχουμε WORKER TIMEOUT στο Render).
    """
    def _worker():
        with app.app_context():
            last_err = None
            for i in range(attempts):
                try:
                    msg = Message(subject=subject, recipients=recipients, body=body)
                    mail.send(msg)
                    app.logger.info("✅ Email sent to %s", recipients)
                    return
                except Exception as e:
                    last_err = e
                    app.logger.exception("⚠️ Email send failed (attempt %s/%s)", i + 1, attempts)
                    time.sleep(delay_sec)
            app.logger.error("❌ Email failed after %s attempts: %s", attempts, last_err)

    threading.Thread(target=_worker, daemon=True).start()

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

        # Συμβατότητα με το ήδη υπάρχον code: cursor(MySQLdb.cursors.DictCursor)
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


#Translation helper functions
def get_user_lang_by_email(email: str) -> str:
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT language FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    cur.close()

    lang = (row.get("language") if row else None) or "el"
    return lang if lang in ("el", "en") else "el"
#Translation function
def TT(lang: str):
    if lang not in ("el", "en"):
        lang = "el"
    return TRANSLATIONS.get(lang, TRANSLATIONS["el"])
#Reconnect to DB if connection is lost
@app.before_request
def ensure_db_alive():
    try:
        mysql.connection.ping(True)  # reconnect if dropped
    except Exception:
        pass


# 📁 game's file

BASE_GAME_FOLDER = os.path.join(os.getcwd(), "hand_exercises")

#Route for database text

@app.route("/db_test")
def db_test():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()
    cur.close()
    return f"DB OK – users rows: {count}"
#Route for PWA manifest and service worker
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


# -------------------------------------------------------------------
# 1️⃣ Welcome Page
# -------------------------------------------------------------------
@app.route('/')
def welcome():
    if 'username' in session:
        return redirect(url_for('menu'))
    return render_template('welcome_page/welcome_page.html')




# -------------------------------------------------------------------
# 2️⃣ Index Page
# -------------------------------------------------------------------
@app.route('/index')
def index():
    if 'username' in session:
        return redirect(url_for('menu'))
    return render_template('index.html')


# -------------------------------------------------------------------
# 3️⃣ Προφίλ χρήστη
# -------------------------------------------------------------------
@app.route('/profile/<username>')
def profile(username):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    # ✅ αν δεν υπάρχει χρήστης (π.χ. διαγράφηκε), κάνε redirect
    if not user:
        cursor.close()
        session.clear()
        return redirect(url_for('index'))  # ή url_for('welcome')

    cursor.execute("SELECT * FROM game_statistics WHERE username = %s", (username,))
    stats = cursor.fetchall()
    cursor.close()

    is_owner = ('username' in session and session['username'] == username)

    # ✅ safe
    session['avatar'] = user.get('avatar')

    return render_template('profile.html', user=user, stats=stats, is_owner=is_owner)

def get_lang():
    return session.get("lang", "el")

def get_t_dict():
    lang = get_lang()
    base = TRANSLATIONS.get("el", {})
    current = TRANSLATIONS.get(lang, base)
    merged = {**base, **current}
    return merged, lang
def normalize_result_key(result: str) -> str:
    """Normalize DB result (completed/win/lose/...) into a canonical key."""
    if not result:
        return ""

    r = str(result).strip().lower()

    # accept many variants so old data still works
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
         # ✅ add Greek variants
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
    return mapping.get(r, r)  # fallback to raw normalized value

#Display result translation function
def display_result(db_result: str, lang: str) -> str:
    """Return translated display text for result."""
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
        return db_result  # unknown -> show raw

    return tt.get(label_key) or base.get(label_key) or db_result
#Mapping game names for translation
def normalize_game_key(name: str) -> str:
    """Map DB game_name (Greek/English) -> canonical key."""
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
    return mapping.get(name, name)  # fallback: keep as-is if unknown


def display_game_name(db_game_name: str, lang: str) -> str:
    """Return translated display name for a game based on current language."""
    key = normalize_game_key(db_game_name)

    # use your TRANSLATIONS dict to get label
    # make sure these keys exist in translations.py:
    # exercise_1_title, exercise_2_title, ...
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
        return db_game_name  # unknown -> show raw

    return tt.get(label_key) or base.get(label_key) or db_game_name

@app.context_processor
def inject_translations():
    t_dict, lang = get_t_dict()
    return {"t": t_dict, "lang": lang}
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template("forgot_password.html")

    email = request.form['email'].strip()

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if not user:
        flash("Το email δεν βρέθηκε.")
        return redirect(url_for('forgot_password'))

    # ✅ γλώσσα από DB (αυτό είναι το κλειδί)
    lang = get_user_lang_by_email(email)
    tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

    token = s.dumps(email, salt='password-reset')
    reset_link = url_for('reset_password', token=token, _external=True)

    subject = tt.get("reset_subject", "Password Reset")
    message = f"""{tt.get("email_hi","Hi")},

{tt.get("reset_email_intro","A password reset was requested for your account.")}

{tt.get("reset_email_click","Click the link below to set a new password:")}

{reset_link}

{tt.get("reset_email_expire","The link is valid for 24 hours.")}

TheraHand Team
"""

    # ✅ Send email async (no request blocking)
    send_email_async(
    subject=subject,
    recipients=[email],
    body=message,
    attempts=3,
    delay_sec=2
)


    flash(tt.get("reset_email_sent", "Reset email sent."))
    return redirect(url_for('index'))


@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset', max_age=86400)
    except SignatureExpired:
        flash("Ο σύνδεσμος έληξε. Ζήτησε νέο.")
        return redirect(url_for('forgot_password'))
    except BadSignature:
        flash("Μη έγκυρος σύνδεσμος.")
        return redirect(url_for('forgot_password'))

    # ✅ γλώσσα από DB (με βάση το email)
    lang = get_user_lang_by_email(email)
    tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

    if request.method == 'POST':
        new_pass = request.form['password']
        confirm = request.form.get('confirm_password')

        if confirm is not None and new_pass != confirm:
            flash(tt.get("passwords_mismatch", "Passwords do not match."))
            return redirect(url_for('reset_password', token=token))

        hashed = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode("utf-8")

        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))
        mysql.connection.commit()
        cur.close()

        flash(tt.get("password_reset_success", "Password changed successfully. You can log in."))
        return redirect(url_for('index'))

    return render_template("reset_password.html", email=email)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if "username" not in session:
        return redirect(url_for("index"))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session['username'],))
    user = cursor.fetchone()

    if request.method == "POST":
        new_username = request.form.get("new_username")
        old_username = user['username']   # ⬅️ ΕΔΩ

        # 1️⃣ update στον πίνακα users
        cursor.execute(
            "UPDATE users SET username=%s WHERE id=%s",
            (new_username, user['id'])
        )

        # 2️⃣ update στα στατιστικά
        cursor.execute(
            "UPDATE game_statistics SET username=%s WHERE username=%s",
            (new_username, old_username)
        )

        mysql.connection.commit()
        cursor.close()

        # ενημερώνουμε το session
        session['username'] = new_username

        return redirect(url_for("profile", username=new_username))

    cursor.close()
    return render_template("edit_profile.html", user=user)


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if "username" not in session:
        return redirect(url_for('index'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s", (session['username'],))
    user = cursor.fetchone()

    if request.method == "POST":
        old_pw = request.form.get("old_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")

        # 🌍 Γλώσσα χρήστη από DB
        lang = (user.get("language") or "el")
        if lang not in ("el", "en"):
            lang = "el"
        tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

        # 1️⃣ Έλεγχος παλιού κωδικού
        if not bcrypt.checkpw(old_pw.encode(), user['password'].encode()):
            return f"""
            <script>
                alert("{tt.get('old_password_wrong','Wrong old password!')}");
                window.history.back();
            </script>
            """

        # 2️⃣ Έλεγχος μήκους
        if len(new_pw) < 8:
            return f"""
            <script>
                alert("{tt.get('password_min_length','Password must be at least 8 characters!')}");
                window.history.back();
            </script>
            """

        # 3️⃣ Επιβεβαίωση
        if new_pw != confirm_pw:
            return f"""
            <script>
                alert("{tt.get('passwords_mismatch','Passwords do not match!')}");
                window.history.back();
            </script>
            """

        # 4️⃣ Hash νέου κωδικού
        hashed_pw = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()

        cursor.execute(
            "UPDATE users SET password=%s WHERE id=%s",
            (hashed_pw, user['id'])
        )
        mysql.connection.commit()

        # ✅ Send email async (no request blocking)
        send_email_async(
       subject=tt.get("password_changed_subject", "🔐 Password changed"),
       recipients=[user["email"]],
       body=f"{tt.get('email_hi','Hi')} {user['username']},\n"
         f"{tt.get('password_changed_body','Your password was changed successfully.')}",
        attempts=3,
         delay_sec=2
)


        cursor.close()

        # 6️⃣ Logout + μήνυμα
        return f"""
        <script>
            alert("{tt.get('password_changed_logout_alert','Password changed successfully. You will be logged out.')}");
            window.location.href = '/logout';
        </script>
        """

    cursor.close()
    return render_template('change_password.html')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if "username" not in session:
        return redirect(url_for('index'))

    username = session['username']

    # 🌍 πάρε γλώσσα χρήστη από DB
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT language FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()

    lang = (user.get("language") if user else None) or "el"
    if lang not in ("el", "en"):
        lang = "el"
    tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

    # ❌ διαγραφή λογαριασμού
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


@app.route("/change_theme", methods=["POST"])
def change_theme():
    if "username" not in session:
        return redirect(url_for("index"))

    new_theme = request.form.get("theme")

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET theme=%s WHERE username=%s",
                   (new_theme, session['username']))
    mysql.connection.commit()
    cursor.close()
    session['theme'] = new_theme


    return """
    <script>
        alert('Το θέμα άλλαξε επιτυχώς!');
        window.location.href = '/profile/%s';
    </script>
    """ % session['username']

@app.route("/api/theme", methods=["POST"])
def api_theme():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    new_theme = data.get("theme")  # "Light" ή "Dark"

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

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if "username" not in session:
        return redirect(url_for('index'))

    avatar = request.files.get('avatar')
    if not avatar:
        return redirect(url_for('profile', username=session['username']))

    filename = secure_filename(session['username'] + "_avatar.png")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    avatar.save(filepath)

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET avatar=%s WHERE username=%s", (filename, session['username']))
    session['avatar'] = filename

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('profile', username=session['username']))

# -------------------------------------------------------------------
# 4️⃣ Έλεγχος / Εγγραφή χρήστη
# -------------------------------------------------------------------
@app.route('/check_user', methods=['POST'])
def check_user():
    data = request.get_json() or {}
    username = (data.get('username') or "").strip()
    email = (data.get('email') or "").strip().lower()
    password = data.get('password') or ""

    if not username or not email or not password:
        return "Συμπλήρωσε όλα τα πεδία!", 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 1) Ψάξε πρώτα με email (πιο σωστό για login)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    # ------------------------
    # ✅ LOGIN (υπάρχει user με αυτό το email)
    # ------------------------
    if user:
        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['user_id'] = user['id']
            session['username'] = user['username']

            # Language: session επιλογή > DB > el
            pref_lang = session.get('lang')
            db_lang = user.get('language')
            lang = pref_lang or db_lang or 'el'
            if lang not in ('el', 'en'):
                lang = 'el'
            session['lang'] = lang
            session.permanent = True
            session.modified = True

            # persist language
            if db_lang != lang:
                cursor.execute("UPDATE users SET language=%s WHERE id=%s", (lang, user['id']))
                mysql.connection.commit()

            cursor.close()
            return "menu" if user.get('profile_completed') else "steps"


        cursor.close()
        return "Λάθος κωδικός!", 401

    # ------------------------
    # ✅ REGISTER (δεν υπάρχει user με αυτό το email)
    # ------------------------

    # 2) Μην αφήνεις ίδιο username να ξαναγραφτεί
    cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
    existing_username = cursor.fetchone()
    if existing_username:
        cursor.close()
        return "Το username υπάρχει ήδη!", 409

    # 3) Hash password
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # 4) Γλώσσα από session (από welcome)
    lang = session.get('lang') or 'el'
    if lang not in ('el', 'en'):
        lang = 'el'

    # 5) Δημιουργία χρήστη
    cursor.execute("""
    INSERT INTO users (username, email, password, language, profile_completed, reminder)
    VALUES (%s, %s, %s, %s, FALSE, 'no')
""", (username, email, hashed, lang))

    
    mysql.connection.commit()

    # 📧 Email καλωσορίσματος
    try:
        tt = TRANSLATIONS.get(lang, TRANSLATIONS["el"])

        msg = Message(
            subject=tt.get("welcome_subject", "Welcome to TheraHand 👋"),
            recipients=[email],
            body=f"""{tt.get('email_hi','Hi')} {username},

           {tt.get('welcome_body','Welcome to TheraHand! Your account was created successfully.')}

          TheraHand Team
             """
        )
        mail.send(msg)
        print(f"✅ Welcome email sent to {email}")
    except Exception as e:
        print("⚠️ Welcome email error:", e)

    

    # 6) Πάρε το id και κάνε login
    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    new_user = cursor.fetchone()
    cursor.close()

    session['user_id'] = new_user['id']
    session['username'] = username
    session['lang'] = lang
    session.permanent = True
    session.modified = True

    return "steps"


# 5️⃣ Βήματα εγγραφής (Steps)
# -------------------------------------------------------------------
@app.route('/sign_up/step<int:step_number>')
def sign_up_steps(step_number):
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template(f'sign_up/step{step_number}.html')


@app.route('/save_step1', methods=['POST'])
def save_step1():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    age = request.form.get('age')
    goal = request.form.get('goal')
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET age=%s, goal=%s WHERE id=%s", (age, goal, session['user_id']))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('sign_up_steps', step_number=2))


@app.route('/save_step2', methods=['POST'])
def save_step2():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    exercise_time = request.form.get('exercise_time')
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET exercise_time=%s WHERE id=%s", (exercise_time, session['user_id']))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('sign_up_steps', step_number=3))


@app.route('/save_step3', methods=['POST'])
def save_step3():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    # reminder from dropdown yes/no
    reminder = request.form.get("reminder")

    # time from input
    exercise_time = request.form.get("exercise_time")

    # Αν ο χρήστης επέλεξε "Όχι", καθαρίζουμε την ώρα
    if reminder == "no":
        exercise_time = None

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users 
        SET reminder=%s, exercise_time=%s 
        WHERE id=%s
    """, (reminder, exercise_time, session['user_id']))

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('sign_up_steps', step_number=4))




@app.route('/complete_profile', methods=['POST'])
def complete_profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    stage = request.form.get('stage')
    type_ = request.form.get('type')
    frequency = request.form.get('frequency')
    duration = request.form.get('duration')
    next_exercise = request.form.get('next_exercise')

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
    """, (stage, type_, frequency, duration, next_exercise, session['user_id']))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('menu'))


# -------------------------------------------------------------------
# 6️⃣ Υπενθυμίσεις μέσω email (Scheduler)
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

        now = datetime.now(pytz.timezone('Europe/Athens')).strftime("%H:%M")

        for user in users:
            raw_time = str(user['exercise_time']).strip()

            # Μετατροπή "20:30" ή "20:30:00" σε "20:30"
            if ":" in raw_time:
                parts = raw_time.split(":")
                ex_time_str = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
            else:
                ex_time_str = raw_time

            if ex_time_str == now:
                # ✅ language από DB
                lang = (user.get('language') or 'el')
                if lang not in ('el', 'en'):
                    lang = 'el'
                tt = TRANSLATIONS.get(lang, TRANSLATIONS['el'])

                try:
                    msg = Message(
                        subject=tt['email_reminder_subject'],
                        recipients=[user['email']],
                        body=f"{tt['email_hi']} {user['username']}!\n\n{tt['email_reminder_body']}"
                    )
                    mail.send(msg)
                    print(f"✅ Reminder email sent to {user['username']} ({lang})")
                except Exception as e:
                    print("⚠️ Reminder email error:", e)


# --- Εκκίνηση Scheduler ---
scheduler = BackgroundScheduler(timezone='Europe/Athens')
scheduler.add_job(func=send_daily_reminders, trigger='cron', minute='*')

# ✅ Start scheduler only once (avoid Flask reloader double-start on Windows)
# Start scheduler in production (Render/Gunicorn)
if os.environ.get("RENDER") or os.environ.get("ENV") == "production":
    scheduler.start()



@app.route('/update_reminder', methods=['POST'])
def update_reminder():
    if "username" not in session:
        return redirect(url_for('index'))

    reminder = request.form.get("reminder")
    exercise_time = request.form.get("exercise_time")

    if reminder == "no":
        exercise_time = None

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE users
        SET reminder=%s, exercise_time=%s
        WHERE username=%s
    """, (reminder, exercise_time, session['username']))

    mysql.connection.commit()
    cursor.close()

    return """
    <script>
        alert("Οι ρυθμίσεις υπενθύμισης αποθηκεύτηκαν!");
        window.location.href = '/profile/%s';
    </script>
    """ % session['username']

# -------------------------------------------------------------------
# 7️⃣ Menu Page
# -------------------------------------------------------------------
@app.route('/menu')
def menu():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('menu.html', username=session['username'])


# -------------------------------------------------------------------
# 8️⃣ Dashboard (στατιστικά παιχνιδιών)
# -------------------------------------------------------------------
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))

    username = session['username']
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

    total_plays = sum(row['plays'] for row in stats)
    total_score = sum(row['total_score'] or 0 for row in stats)
    total_time = sum(row['total_time'] or 0 for row in stats)

    return render_template('dashboard.html',
                           username=username,
                           stats=stats,
                           total_plays=total_plays,
                           total_score=total_score,
                           total_time=total_time)




# -------------------------------------------------------------------
# 9️⃣ Αποθήκευση στατιστικών από παιχνίδι
# -------------------------------------------------------------------
@app.route('/add_stat', methods=['POST'])
def add_stat():
    data = request.get_json()

    # ✅ Δέχεται username είτε από το session είτε από το παιχνίδι
    username = data.get('username') or session.get('username')
    if not username:
        return jsonify({"error": "Unauthorized – no username provided"}), 401

    game_name = data.get('game_name')
    score = data.get('score')
    time_seconds = data.get('time_seconds')
    result = data.get('result')
    age = data.get('age')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT age FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    db_age = user['age'] if user else age

    cursor.execute("""
        INSERT INTO game_statistics (username, age, game_name, score, time_seconds, result, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
    """, (username, db_age, game_name, score, time_seconds, result))
    mysql.connection.commit()
    cursor.close()

    print(f"📊 Στατιστικά αποθηκεύτηκαν για τον {username} ({game_name})")

    return jsonify({"message": "✅ Τα στατιστικά αποθηκεύτηκαν επιτυχώς!"}), 200



# -------------------------------------------------------------------
# 🔟 Εκκίνηση παιχνιδιών
# -------------------------------------------------------------------
@app.route('/start/<int:exercise_num>', methods=['POST'])
def start_exercise(exercise_num):
    if 'username' not in session:
        return redirect(url_for('index'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT age, language FROM users WHERE username = %s", (session['username'],))
    user = cursor.fetchone()
    cursor.close()

    username = session['username']
    age = user['age'] if user else 0

    lang = (user.get("language") if user else None) or session.get("lang") or "el"
    if lang not in ("el", "en"):
      lang = "el"
    
    # ✅ In Render/production, do NOT spawn python games on server. Load web (JS) game page instead.
    if os.environ.get("RENDER") or os.environ.get("ENV") == "production":
     session["age"] = age
     session["lang"] = lang
     return redirect(url_for("play_exercise", ex_id=exercise_num))



    # 🧩 Ορισμός φακέλου και αρχείων για κάθε παιχνίδι
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
    except Exception as e:
        print("⚠️ Σφάλμα εκτέλεσης παιχνιδιού:", e)

    return redirect(url_for('dashboard'))



# -------------------------------------------------------------------
# 11️⃣ Εμφάνιση σελίδων ασκήσεων
# -------------------------------------------------------------------
@app.route('/exercise_1')
def exercise_1():
    return render_template('exercises/exercise_1.html')

@app.route('/exercise_2')
def exercise_2():
    return render_template('exercises/exercise_2.html')

@app.route('/exercise_3')
def exercise_3():
    return render_template('exercises/exercise_3.html')

@app.route('/exercise_4')
def exercise_4():
    return render_template('exercises/exercise_4.html')


# -------------------------------------------------------------------
# 12️⃣ API για ζωντανή ενημέρωση στατιστικών
# -------------------------------------------------------------------
@app.route('/api/stats')
def api_stats():
    if 'username' not in session:
        return jsonify([])

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT username, age, game_name, score, time_seconds, result, created_at
        FROM game_statistics
        WHERE username = %s
        ORDER BY created_at DESC
    """, (session['username'],))
    stats = cursor.fetchall()
    cursor.close()

    lang = session.get("lang", "el")

    for row in stats:
        row["game_name"] = display_game_name(row.get("game_name"), lang)
        row["result"] = display_result(row.get("result"), lang)

        dt = row.get("created_at")
        if isinstance(dt, datetime):
            # DB returns naive datetime -> treat as UTC (because we store with UTC_TIMESTAMP())
            if dt.tzinfo is None:
                dt = UTC_TZ.localize(dt)
            row["created_at"] = dt.astimezone(ATHENS_TZ).isoformat()
        else:
            # fallback: keep as-is
            row["created_at"] = str(dt)

    return jsonify(stats)
@app.route('/today')
def today():
    if 'username' not in session:
        return redirect(url_for('index'))

    username = session['username']

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


    total_plays = sum(item['plays'] for item in today_stats)
    total_score = sum(item['total_score'] or 0 for item in today_stats)
    total_time = sum(item['total_time'] or 0 for item in today_stats)

    return render_template('today.html',
                           username=username,
                           today_stats=today_stats,
                           total_plays=total_plays,
                           total_score=total_score,
                           total_time=total_time)

@app.route('/api/today_stats')
def api_today_stats():
    if 'username' not in session:
        return jsonify([])

    username = session['username']
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
      row["game_name"] = display_game_name(row["game_name"], lang)

    return jsonify(data)


@app.route('/api_dashboard_stats')
def api_dashboard_stats():
    if 'username' not in session:
        return jsonify([])

    username = session['username']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # 📊 Ομαδοποιεί όλες τις ασκήσεις με συνολικές φορές & μέσο σκορ
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



@app.route('/change_language', methods=['POST'])
def change_language():
    new_lang = request.form.get('language', 'el')
    if new_lang not in ('el', 'en'):
        new_lang = 'el'

    # κρατάμε προσωρινά πριν login, και μόνιμα μετά login
    session['lang'] = new_lang
    session.permanent = True
    session.modified = True

    # αν είναι logged in, γράψε DB (τελευταία επιλογή)
    if 'username' in session:
        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE users SET language=%s WHERE username=%s",
            (new_lang, session['username'])
        )
        mysql.connection.commit()
        cursor.close()

    return redirect(request.referrer or url_for('welcome'))



@app.before_request
def load_language():
    # ✅ Αν είμαστε σε signup steps, ΜΗΝ πειράζεις session lang από DB
    if request.path.startswith("/sign_up/"):
        if session.get('lang') not in ('el', 'en'):
            session['lang'] = 'el'
        return

    # ✅ Για όλες τις άλλες σελίδες, αν είναι logged in, DB -> session
    if 'username' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT language FROM users WHERE username=%s", (session['username'],))
        user = cursor.fetchone()
        cursor.close()

        db_lang = (user.get('language') if user else None) or 'el'
        if db_lang not in ('el', 'en'):
            db_lang = 'el'

        session['lang'] = db_lang
    else:
        if session.get('lang') not in ('el', 'en'):
            session['lang'] = 'el'


@app.route('/play/<int:ex_id>')
def play_exercise(ex_id):
    if 'username' not in session:
        return redirect(url_for('index'))

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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('welcome'))


   
# -------------------------------------------------------------------
# 14️⃣ Εκκίνηση εφαρμογής
# -------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
    