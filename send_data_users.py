from flask import Flask, request, jsonify, render_template
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from dotenv import load_dotenv
import os
import datetime

# 🔐 Φόρτωση μεταβλητών από custom αρχείο .env
load_dotenv(dotenv_path='data.env')

app = Flask(__name__)

# 📧 Ρυθμίσεις email (SMTP)
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=('Hand Exercises', os.getenv('MAIL_USERNAME'))
)

mail = Mail(app)

# 🗄️ Σύνδεση με SQLite βάση Hand.db
def get_db():
    try:
        conn = sqlite3.connect('Hand.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Σφάλμα σύνδεσης στη βάση: {e}")
        return None

# 🌐 Αρχική σελίδα
@app.route('/')
def index():
    return render_template('index.html')

# 🔐 Έλεγχος χρήστη και εγγραφή
@app.route('/check_user', methods=['POST'])
def check_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    conn = get_db()
    if conn is None:
        return jsonify({"status": "error", "message": "Σφάλμα σύνδεσης στη βάση."})

    cursor = conn.cursor()

    # Έλεγχος αν υπάρχει ήδη ο χρήστης
    cursor.execute("SELECT * FROM check_users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if user:
        return jsonify({"status": "login"})

    # Εισαγωγή νέου χρήστη με created_at και is_verified
    hashed_pw = generate_password_hash(password)
    created_at = datetime.datetime.now().isoformat()
    is_verified = 1  # ή 0 αν θέλεις να προσθέσεις μηχανισμό επιβεβαίωσης

    cursor.execute(
        "INSERT INTO check_users (username, email, password, created_at, is_verified) VALUES (?, ?, ?, ?, ?)",
        (username, email, hashed_pw, created_at, is_verified)
    )
    conn.commit()
    conn.close()

    # ✉️ Αποστολή email επιβεβαίωσης
    try:
        send_signup_email(email, username)
    except Exception as e:
        print(f"❌ Σφάλμα αποστολής email: {e}")
        return jsonify({"status": "signup_success", "message": "Εγγραφή επιτυχής, αλλά απέτυχε η αποστολή email."})

    return jsonify({"status": "signup_success", "message": "Η εγγραφή ολοκληρώθηκε! Δες το email σου."})

# 📤 Συνάρτηση αποστολής email
def send_signup_email(email, username):
    msg = Message(
        subject="Επιτυχής Εγγραφή στο Hand Exercises!",
        recipients=[email],
        html=f"""
        <div style="font-family: Arial, sans-serif; color: #333;">
            <h2>Καλώς ήρθες, {username}! 👋</h2>
            <p>Η εγγραφή σου στην εφαρμογή <strong>Hand Exercises</strong> ολοκληρώθηκε επιτυχώς 🎉</p>
            <p>Μπορείς τώρα να συνδεθείς και να ξεκινήσεις!</p>
            <hr>
            <p style="font-size: 12px; color: #777;">Αυτό το μήνυμα στάλθηκε αυτόματα από την εφαρμογή Hand Exercises.</p>
        </div>
        """
    )
    mail.send(msg)

# 🚀 Εκκίνηση εφαρμογής
if __name__ == '__main__':
    app.run(debug=True)
