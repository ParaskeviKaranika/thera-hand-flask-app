import mysql.connector

def save_score(username, score):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",  # Αν έχεις βάλει κωδικό MySQL, βάλε τον εδώ
        database="game_data"
    )
    cursor = conn.cursor()
    query = "INSERT INTO scores (username, score) VALUES (%s, %s)"
    cursor.execute(query, (username, score))
    conn.commit()
    cursor.close()
    conn.close()
