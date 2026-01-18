import pygame
import random
import mediapipe as mp
import cv2
import time
import os
import requests
import webbrowser
import sys


username = sys.argv[1] if len(sys.argv) > 1 else "Guest"
age = int(sys.argv[2]) if len(sys.argv) > 2 else 0
def send_stats(username, age, score, time_seconds, result):
    data = {
        "username": username,
        "age": age,
        "game_name": "Άσκηση 1",
        "score": score,
        "time_seconds": time_seconds,
        "result": result
    }
    try:
        response = requests.post("http://127.0.0.1:5000/add_stat", json=data)
        if response.status_code == 200:
            print("✅ Τα στατιστικά στάλθηκαν με επιτυχία στο Flask!")
        else:
            print(f"⚠️ Σφάλμα αποστολής ({response.status_code}):", response.text)
    except Exception as e:
        print("⚠️ Σφάλμα αποστολής στατιστικών:", e)



# Βρες το path του τρέχοντος αρχείου
base_path = os.path.dirname(__file__)


# Set window title
pygame.display.set_caption("Game")

pygame.init()
# Screen dimensions
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 600
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
# Load and scale background image
# Load and scale background image
background = pygame.image.load(os.path.join(base_path, "sky.jpg"))
background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT))
#background = pygame.image.load("sky.jpg")
#background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT))
# Load and scale star image
small_image = pygame.image.load(os.path.join(base_path, "star.png")).convert()
small_image.set_colorkey((255, 255, 255))
small_image = pygame.transform.scale(small_image, (40, 40))
#small_image = pygame.image.load("star.png").convert()
#small_image.set_colorkey((255, 255, 255))
#small_image = pygame.transform.scale(small_image, (40, 40))
# Load and scale hand image (used as cursor/hand representation)
# Load and scale hand image
hand_image = pygame.image.load(os.path.join(base_path, "hand.png"))
hand_image = pygame.transform.scale(hand_image, (80, 80))
#hand_image = pygame.image.load("hand.png")
#hand_image = pygame.transform.scale(hand_image, (80, 80))
# Game variables
score = 0
time_left = 30
game_over = False
game_won = False
win_score = 10  # Score needed to win
# Initial random positions for collectible stars
image_positions = [(random.randint(0, SCREEN_WIDTH - 50), random.randint(0, SCREEN_HEIGHT - 50)) for _ in range(5)]
# Buttons for restart and exit (appear on game over/win screens)
restart_button = pygame.Rect(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 100, 100, 50)
exit_button = pygame.Rect(SCREEN_WIDTH // 2 + 20, SCREEN_HEIGHT // 2 + 100, 100, 50)
# Mediapipe setup
mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

cap = cv2.VideoCapture(0)
# -----------------------------------------------------
# Function: display_score_time
# Draw current score and remaining time on the screen
# -----------------------------------------------------
def display_score_time():
    font = pygame.font.SysFont('Arial', 30)
    score_text = font.render(f"Score: {score}", True, (255, 255, 255))
    time_text = font.render(f"Time: {time_left}s", True, (255, 255, 255))
    SCREEN.blit(score_text, (10, 10))
    SCREEN.blit(time_text, (10, 40))
# -----------------------------------------------------
# Function: draw_buttons
# Draw Restart and Exit buttons on the screen
# -----------------------------------------------------
def draw_buttons():
    small_font = pygame.font.SysFont('Arial', 25)
    pygame.draw.rect(SCREEN, (0, 0, 139), restart_button)
    restart_text = small_font.render("Restart", True, (255, 255, 255))
    SCREEN.blit(restart_text, (restart_button.x + 10, restart_button.y + 10))

    pygame.draw.rect(SCREEN, (0, 0, 139), exit_button)
    exit_text = small_font.render("Exit", True, (255, 255, 255))
    SCREEN.blit(exit_text, (exit_button.x + 25, exit_button.y + 10))
# -----------------------------------------------------
# Function: game_over_screen
# Display the "Game Over" screen with score and buttons
# -----------------------------------------------------
def game_over_screen():
    font = pygame.font.SysFont('Arial', 50)
    score_text = font.render("Game Over!", True, (255, 0, 0))
    final_score_text = font.render(f"Final Score: {score}", True, (255, 255, 255))
    SCREEN.blit(score_text, (SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 100))
    SCREEN.blit(final_score_text, (SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2))
    draw_buttons()
# -----------------------------------------------------
# Function: win_screen
# Display the "You Win!" screen with score and buttons
# -----------------------------------------------------
def win_screen():
    font = pygame.font.SysFont('Arial', 50)
    win_text = font.render("You Win!", True, (0, 255, 0))
    final_score_text = font.render(f"Score: {score}", True, (255, 255, 255))
    SCREEN.blit(win_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 100))
    SCREEN.blit(final_score_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 40))
    draw_buttons()
# -----------------------------------------------------
# Function: check_win
# Check if player reached the target score and won the game
# -----------------------------------------------------
def check_win():
    global game_won
    if score >= win_score:
        game_won = True
# -----------------------------------------------------
# Main Game Loop
# -----------------------------------------------------
with mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
    running = True
    start_time = time.time()

    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif (game_over or game_won) and event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                # Restart button clicked
                if restart_button.collidepoint(mouse_pos):
                    score = 0
                    time_left = 30
                    start_time = time.time()
                    game_over = False
                    game_won = False
                    image_positions = [(random.randint(0, SCREEN_WIDTH - 50), random.randint(0, SCREEN_HEIGHT - 50)) for _ in range(5)]
                elif exit_button.collidepoint(mouse_pos):
                    running = False
# --- If Game Over, show screen ---
        if game_over:
            SCREEN.blit(background, (0, 0))
            game_over_screen()
            pygame.display.update()
            continue
# --- If Game Won, show screen ---
        if game_won:
            SCREEN.blit(background, (0, 0))
            win_screen()
            pygame.display.update()
            continue
 # Capture frame from webcam
        success, image = cap.read()
        if not success:
            continue

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        h, w, _ = image.shape
# If a hand is detected
        hand_rect = None
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Landmark 12 = middle finger tip, Landmark 9 = base of middle finger
                point_12 = hand_landmarks.landmark[12]
                point_9 = hand_landmarks.landmark[9]
                x12, y12 = int(point_12.x * w), int(point_12.y * h)
                x9, y9 = int(point_9.x * w), int(point_9.y * h)
                # Draw landmarks on the OpenCV frame (for debugging)
                mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                hand_rect = pygame.Rect(x9 - 40, y9 - 40, 80, 80)

        SCREEN.blit(background, (0, 0))
        for pos in image_positions:
            SCREEN.blit(small_image, pos)
            # Collision detection: check if hand touches a star

        if hand_rect:
            for pos in image_positions:
                star_rect = pygame.Rect(pos[0], pos[1], 40, 40)
                if hand_rect.colliderect(star_rect) and y12 > y9:
                    # If hand rectangle overlaps with star rectangle and finger tip is below base (gesture condition)
                    image_positions.remove(pos)
                    image_positions.append((random.randint(0, SCREEN_WIDTH - 50), random.randint(0, SCREEN_HEIGHT - 50)))
                    score += 1
                    check_win()

        display_score_time()
# Update timer
        time_left = 30 - int(time.time() - start_time)
        if time_left <= 0:
            game_over = True
            time_left = 0
            send_stats(username, age, score, int(time.time() - start_time), "Ήττα")
        if game_won:
           SCREEN.blit(background, (0, 0))
           win_screen()
           pygame.display.update()
           send_stats(username, age, score, int(time.time() - start_time), "Νίκη")
           continue


        if hand_rect:
            SCREEN.blit(hand_image, hand_rect)

        pygame.display.update()


cap.release()
pygame.quit()
