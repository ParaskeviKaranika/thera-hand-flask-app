import subprocess
import webbrowser
import time
import os

# start the flask app 
flask_process = subprocess.Popen(['python', 'app.py'], cwd=os.path.dirname(__file__))

# wait for the server to start
time.sleep(2)

# Open the web browser to the flask app
webbrowser.open('http://127.0.0.1:5000')