from flask import Flask, render_template, request, redirect, url_for
import subprocess
import os
import webbrowser
import time
import requests
import  sys 

# Παίρνει username και ηλικία από τα arguments
username = sys.argv[1] if len(sys.argv) > 1 else "Guest"
age = sys.argv[2] if len(sys.argv) > 2 else "0"

# ✅ Σωστό path προς το παιχνίδι (first_game.py)
game_path = os.path.join(os.path.dirname(__file__), "first_game.py")

print("🎮 Εκκίνηση παιχνιδιού...")
subprocess.run(["python", game_path, username, str(age)])



base_path = os.path.dirname(__file__)
print("Το script βρίσκεται στον φάκελο:", base_path)


app = Flask(__name__)

FLASK_URL = "http://127.0.0.1:5000"  # adjust if your Flask runs elsewhere

def send_stat(payload):
    resp = requests.post(f"{FLASK_URL}/add_stat", json=payload, timeout=5)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    # example payload - replace with real game data
    payload = {
        "username": "user1",
        "age": 8,
        "game_name": "exercise1",
        "score": 42,
        "time_seconds": 30,
        "result": "pass"
    }

    try:
        print("Sending stat...")
        r = send_stat(payload)
        print("Server response:", r)
        # short delay to let DB commit and dashboard query see the new row
        time.sleep(0.5)
        # open dashboard filtered by game
        url = f"{FLASK_URL}/dashboard?game={payload['game_name']}"
        webbrowser.open(url)
        print("Opened dashboard:", url)
    except Exception as e:
        print("Error:", e)
@app.route('/')
def menu():
    return render_template('exercises/exercise_1.html')

@app.route('/start/<exercise_id>', methods=['POST'])

def start_exercise(exercise_id):
    try:
        script_path = os.path.join('hand_exercises', 'first_game', 'first_game.py')

        subprocess.Popen(['python3', script_path])
        return redirect(url_for('menu'))  # ή μπορείς να δείξεις μήνυμα επιτυχίας
    except Exception as e:
        return f"Σφάλμα: {str(e)}"

#if __name__ == '__main__':
   # app.run(debug=True)


