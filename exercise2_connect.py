from flask import Flask, render_template, request, redirect, url_for
import subprocess
import os
import os

base_path = os.path.dirname(__file__)
print("Το script βρίσκεται στον φάκελο:", base_path)


app = Flask(__name__)

@app.route('/')
def menu():
    return render_template('exercises/exercise_2.html')

@app.route('/start/<exercise_id>', methods=['POST'])

def start_exercise(exercise_id):
    try:
        script_path = os.path.join('hand_exercises', 'second_game', 'second_game_shape_moving.py')

        subprocess.Popen(['python3', script_path])
        return redirect(url_for('menu'))  
    except Exception as e:
        return f"Σφάλμα: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)


