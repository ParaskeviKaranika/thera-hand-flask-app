import cv2  # OpenCV: used to access the webcam and process frames (hand tracking input)
import pygame  # Pygame: used for window creation, drawing graphics, handling events
import numpy as np  # NumPy: used for array operations (converting camera image to pygame surface)
import random  # Random: used to shuffle the puzzle and choose random targets
import time  # Time: used to measure elapsed time for gameplay and timing stats
from settings import *  # Import constants like WIDTH, HEIGHT, TILESIZE, GAME_SIZE, FPS, colors, etc.
from hand_tracker import HandTracker  # Custom class that detects hands and returns landmarks
import os  # OS: used to get current file path
import requests  # Requests: used to POST stats to the Flask server endpoint
import sys  # Sys: used to read command-line arguments (username, age, language)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# προσθέτουμε το Front-pwa στο PYTHONPATH
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from translations import t  # ✅ i18n: function t(lang, key, **kwargs) returns translated UI strings

# Read username from command-line arguments passed by Flask:
# argv[1] = username, otherwise "Guest"
username = sys.argv[1] if len(sys.argv) > 1 else "Guest"

# Read age from argv[2], otherwise 0
age = int(sys.argv[2]) if len(sys.argv) > 2 else 0

# Read language from argv[3], otherwise default "el"
# Flask will pass "el" or "en"
lang_arg = sys.argv[3] if len(sys.argv) > 3 else "el"

# Validate language input (fallback to "el" if unexpected value)
if lang_arg not in ("el", "en"):
    lang_arg = "el"


def send_stats(username, age, score, time_seconds, result):
    """Send gameplay stats to Flask backend (/add_stat) via HTTP POST."""

    # Create JSON payload expected by the Flask endpoint
    data = {
        "username": username,
        "age": age,
        "game_name": "Άσκηση 3",  # Game name stored in DB (you can also i18n this if you want)
        "score": score,
        "time_seconds": time_seconds,
        "result": result
    }

    try:
        # Send stats to Flask server on localhost
        response = requests.post("http://127.0.0.1:5000/add_stat", json=data)

        # Check response
        if response.status_code == 200:
            print("✅ Stats sent to Flask")
        else:
            print(f"⚠️ Stats send error ({response.status_code}):", response.text)
    except Exception as e:
        # Any network/connection errors end up here
        print("⚠️ Stats send error:", e)


# Absolute directory of this file (useful if you want to load assets relative to this file)
base_path = os.path.dirname(__file__)

# Initialize pygame modules (required before using display, fonts, etc.)
pygame.init()
pygame.font.init()


class Tile(pygame.sprite.Sprite):
    """Represents a single tile in the puzzle grid (including the empty tile)."""

    def __init__(self, game, x, y, text):
        # Put this sprite in the group's list for drawing
        self.groups = game.all_sprites

        # Initialize the Sprite base class, and attach to sprite groups
        pygame.sprite.Sprite.__init__(self, self.groups)

        # Keep reference to main Game object (for grid params, etc.)
        self.game = game

        # Grid coordinates (column=x, row=y)
        self.x, self.y = x, y

        # Text shown on the tile ("1".."8" or "empty")
        self.text = text

        # Create a surface (the tile image) with TILESIZE x TILESIZE pixels
        self.image = pygame.Surface((TILESIZE, TILESIZE))

        # Rect is used for positioning + collisions; we update it based on grid coords
        self.rect = self.image.get_rect()

        # Place tile on screen based on its grid coordinates
        self.update_position()

        # Whether this tile is highlighted (yellow background)
        self.highlighted = False

        # If this is a numbered tile, draw the number
        if self.text != "empty":
            # Create font object for drawing tile label
            font = pygame.font.Font("freesansbold.ttf", 20)

            # Render tile number as black text
            font_surface = font.render(self.text, True, BLACK)

            # Fill tile with white (or yellow if highlighted)
            self.image.fill(WHITE if not self.highlighted else (255, 255, 0))

            # Compute text size for centering
            font_size = font.size(self.text)

            # Center text inside tile
            draw_x = (TILESIZE / 2) - font_size[0] / 2
            draw_y = (TILESIZE / 2) - font_size[1] / 2

            # Draw text onto tile surface
            self.image.blit(font_surface, (draw_x, draw_y))
        else:
            # If this is the empty tile, make it transparent / invisible
            self.image.fill((0, 0, 0, 0))

    def update_position(self):
        """Convert grid coordinates (x,y) into pixel coordinates for rendering."""
        grid_width = GAME_SIZE * TILESIZE  # total grid width in pixels
        grid_height = GAME_SIZE * TILESIZE  # total grid height in pixels

        # Center grid horizontally on screen
        offset_x = (WIDTH - grid_width) // 2

        # Place grid near top (quarter of the screen offset) like your original code
        offset_y = (HEIGHT - grid_height) // 4+60

        # Convert grid coordinates into screen coordinates
        self.rect.x = offset_x + self.x * TILESIZE
        self.rect.y = offset_y + self.y * TILESIZE

    def highlight(self, state):
        """Toggle highlight state and redraw tile background."""
        self.highlighted = state  # store highlight state

        # Only redraw if this is not the empty tile
        if self.text != "empty":
            font = pygame.font.Font("freesansbold.ttf", 20)
            font_surface = font.render(self.text, True, BLACK)

            # Fill background based on highlight flag
            self.image.fill(WHITE if not self.highlighted else (255, 255, 0))

            # Center text again
            font_size = font.size(self.text)
            draw_x = (TILESIZE / 2) - font_size[0] / 2
            draw_y = (TILESIZE / 2) - font_size[1] / 2

            self.image.blit(font_surface, (draw_x, draw_y))


class Game:
    """Main game controller: handles state, events, rendering, scoring, etc."""

    def __init__(self):
        # Create pygame window
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        # Set window title
        pygame.display.set_caption(TITLE)

        # Clock controls frame rate
        self.clock = pygame.time.Clock()

        # Initialize hand tracker (your custom detector)
        self.hand_tracker = HandTracker()

        # Open webcam capture (camera index 0)
        self.cap = cv2.VideoCapture(0)

        # Set camera resolution to match game window (best-effort)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

        # Main loop flags
        self.running = True  # game window is alive
        self.playing = False  # puzzle session is active or not

        # Debug mode prints hand/tile info and draws hand landmarks
        self.debug = True

        # Gameplay counters
        self.moves = 0  # number of tile moves
        self.start_time = None  # timestamp when level started
        self.target_tile = None  # current highlighted target tile
        self.score = 0  # total score (across levels)
        self.level_score = 0  # per-level score
        self.level = 1  # current level number
        self.can_move = True  # (not used in this code path, kept from your original idea)

        # ✅ Language set automatically from Flask argv (no keyboard press needed)
        self.lang = lang_arg

        # Load success sound if exists
        try:
            self.success_sound = pygame.mixer.Sound("success.wav")
        except FileNotFoundError:
            print("Warning: success.wav not found. Sound will be disabled.")
            self.success_sound = None

    def tr(self, key, **kwargs):
        """Translate a UI string using current language."""
        return t(self.lang, key, **kwargs)

    def show_instructions(self):
        """Show a static instructions screen until user clicks start button."""
        font = pygame.font.Font("freesansbold.ttf", 16)  # font for instruction text
        button_font = pygame.font.Font("freesansbold.ttf", 16)  # font for button label

        # Instruction lines are taken from translations
        instructions = [
            self.tr("welcome"),
            "",
            self.tr("instructions_title"),
            self.tr("inst_1"),
            self.tr("inst_2"),
            "",
            self.tr("goal_title"),
            self.tr("goal_desc"),
            "",
            self.tr("press_start")
        ]

        # Clear screen background
        self.screen.fill((0, 0, 0))

        # Compute total height of all lines for centering
        total_height = len(instructions) * 30
        start_y = (HEIGHT - total_height) // 2 - 40

        # Draw each line centered
        for i, line in enumerate(instructions):
            text = font.render(line, True, (255, 255, 255))
            text_rect = text.get_rect(center=(WIDTH // 2, start_y + i * 30))
            self.screen.blit(text, text_rect)

        # Draw start button
        button_text = button_font.render(self.tr("start_btn"), True, (0, 0, 0))
        button_width, button_height = 250, 50
        button_x = (WIDTH - button_width) // 2
        button_y = start_y + len(instructions) * 30 + 20
        button_rect = pygame.Rect(button_x, button_y, button_width, button_height)

        pygame.draw.rect(self.screen, (169, 169, 169), button_rect)
        text_rect = button_text.get_rect(center=button_rect.center)
        self.screen.blit(button_text, text_rect)

        # Present the instructions screen
        pygame.display.flip()

        # Wait here until user clicks start or closes window
        waiting = True
        while waiting:
            for event in pygame.event.get():
                # Close window
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    return

                # Click start button
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if button_rect.collidepoint(event.pos):
                        waiting = False

    def show_level_complete(self):
        """Called when player reaches level goal; shows next-level or completion screen."""
        if self.level == 3:
            # If last level completed: send stats to Flask
            total_time = int(time.time() - self.start_time)
            send_stats(username, age, self.score, total_time, "completed")

            # Show completion message
            self.show_message(self.tr("exercise_done"), self.tr("restart"), show_exit=True)

            # Reset progress for next run
            self.level = 1
            self.score = 0
        else:
            # Otherwise move to next level and show a message
            self.level += 1
            self.show_message(
                self.tr("level_passed", level=self.level - 1),
                self.tr("next_level"),
                show_exit=True
            )

    def show_message(self, message, button_label, show_exit=False, restart_option=False):
        """Generic full-screen message box with one main button and optional exit/restart buttons."""
        font = pygame.font.Font(None, 20)
        button_font = pygame.font.Font(None, 20)

        # Clear screen
        self.screen.fill((0, 0, 0))

        # Render main message
        text = font.render(message, True, (255, 255, 255))
        text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60))
        self.screen.blit(text, text_rect)

        # Main action button (Next level / Restart, etc.)
        button_width, button_height = 250, 50
        button_x = (WIDTH - button_width) // 2
        button_y = HEIGHT // 2
        button_rect = pygame.Rect(button_x, button_y, button_width, button_height)

        pygame.draw.rect(self.screen, (169, 169, 169), button_rect)
        button_text = button_font.render(button_label, True, (0, 0, 0))
        button_text_rect = button_text.get_rect(center=button_rect.center)
        self.screen.blit(button_text, button_text_rect)

        exit_rect = None
        restart_rect = None

        # Optional Exit button
        if show_exit:
            exit_y = button_y + 70
            exit_rect = pygame.Rect(button_x, exit_y, button_width, button_height)
            pygame.draw.rect(self.screen, (100, 100, 100), exit_rect)

            # Exit text is translated
            exit_text = button_font.render(self.tr("exit"), True, (255, 255, 255))
            exit_text_rect = exit_text.get_rect(center=exit_rect.center)
            self.screen.blit(exit_text, exit_text_rect)

        # Optional Restart button
        if restart_option:
            restart_y = button_y + 140
            restart_rect = pygame.Rect(button_x, restart_y, button_width, button_height)
            pygame.draw.rect(self.screen, (150, 150, 150), restart_rect)

            # Restart text is translated
            restart_text = button_font.render(self.tr("restart"), True, (0, 0, 0))
            restart_text_rect = restart_text.get_rect(center=restart_rect.center)
            self.screen.blit(restart_text, restart_text_rect)

        # Present message screen
        pygame.display.flip()

        # Wait for clicks
        waiting = True
        while waiting:
            for event in pygame.event.get():
                # Close window
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    return

                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Click main button -> continue
                    if button_rect.collidepoint(event.pos):
                        waiting = False

                    # Click Exit -> quit
                    elif show_exit and exit_rect and exit_rect.collidepoint(event.pos):
                        self.running = False
                        pygame.quit()
                        return

                    # Click Restart -> reset counters and continue
                    elif restart_option and restart_rect and restart_rect.collidepoint(event.pos):
                        self.level = 1
                        self.score = 0
                        waiting = False

    def handle_successful_move(self):
        """Called when the empty tile becomes adjacent to the highlighted target tile."""
        # Play success sound if available
        if self.success_sound:
            self.success_sound.play()

        # Unhighlight the old target tile
        self.target_tile.highlight(False)

        # Pick a new target tile adjacent to the empty space
        self.set_new_target()

        # Update scores
        self.score += 1
        self.level_score += 1

        # Define goals for each level
        level_goals = {1: 5, 2: 10, 3: 15}

        # If score hits current level goal, stop and show level complete screen
        if self.score == level_goals.get(self.level, 999):
            self.playing = False
            self.show_level_complete()
            self.new()  # create new puzzle board

        # Debug output
        print(f"Level: {self.level} | Score: {self.level_score}")

    def new(self):
        """Start a new puzzle board and reset session counters."""
        # Sprite group containing all tiles (for easy drawing)
        self.all_sprites = pygame.sprite.Group()

        # Create shuffled numeric grid
        self.tiles_grid = self.create_game()

        # Build Tile objects for each grid cell
        self.tiles = []
        for row in range(GAME_SIZE):
            self.tiles.append([])
            for col in range(GAME_SIZE):
                value = self.tiles_grid[row][col]
                tile_text = "empty" if value == 0 else str(value)
                self.tiles[row].append(Tile(self, col, row, tile_text))

        # Mark session active
        self.playing = True

        # Reset move counter and timing
        self.moves = 0
        self.start_time = time.time()

        # Choose initial target tile
        self.set_new_target()

    def create_game(self):
        """Create a solved grid then shuffle it by performing valid empty-tile moves."""
        grid = [[x + y * GAME_SIZE for x in range(1, GAME_SIZE + 1)] for y in range(GAME_SIZE)]
        grid[-1][-1] = 0  # last cell is empty

        # Shuffle by performing 20 random valid moves (keeps puzzle solvable)
        for _ in range(20):
            self.shuffle_grid(grid)

        return grid

    def shuffle_grid(self, grid):
        """Shuffle grid by moving the empty tile one random step (up/down/left/right)."""
        empty_pos = None

        # Find empty tile position
        for i in range(GAME_SIZE):
            for j in range(GAME_SIZE):
                if grid[i][j] == 0:
                    empty_pos = (i, j)
                    break

        if empty_pos:
            moves = []
            row, col = empty_pos

            # Determine possible directions (only within bounds)
            if col > 0: moves.append((-1, 0))            # left
            if col < GAME_SIZE - 1: moves.append((1, 0)) # right
            if row > 0: moves.append((0, -1))            # up
            if row < GAME_SIZE - 1: moves.append((0, 1)) # down

            if moves:
                # Choose one valid move randomly
                move = random.choice(moves)

                # Apply move to empty position
                new_row, new_col = row + move[1], col + move[0]

                # Swap values in grid (move empty)
                grid[row][col], grid[new_row][new_col] = grid[new_row][new_col], grid[row][col]

    def set_new_target(self):
        """Select a random tile adjacent to the empty cell and highlight it."""
        empty_pos = None

        # Find empty cell in current grid
        for i in range(GAME_SIZE):
            for j in range(GAME_SIZE):
                if self.tiles_grid[i][j] == 0:
                    empty_pos = (i, j)
                    break

        if empty_pos:
            row, col = empty_pos
            possible_targets = []

            # Adjacent tiles around empty cell
            if col > 0: possible_targets.append((row, col - 1))
            if col < GAME_SIZE - 1: possible_targets.append((row, col + 1))
            if row > 0: possible_targets.append((row - 1, col))
            if row < GAME_SIZE - 1: possible_targets.append((row + 1, col))

            if possible_targets:
                # Pick one adjacent tile randomly
                target_row, target_col = random.choice(possible_targets)

                # Store that tile object as target
                self.target_tile = self.tiles[target_row][target_col]

                # Highlight target tile on screen
                if self.target_tile:
                    self.target_tile.highlight(True)

    def run(self):
        """Main loop: handle events + draw each frame."""
        while self.running:
            # Limit to FPS frames per second
            self.clock.tick(FPS)

            # Handle input + hand tracking logic
            self.events()

            # Draw frame
            if self.running:
                self.draw()

            # If playing flag turned off, restart a new board
            if not self.playing:
                self.new()

    def events(self):
        """Handle window events and then process webcam hand tracking moves."""
        # Handle pygame window events first (close button)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.cap.release()
                pygame.quit()
                return

        if not self.running:
            return

        # Read a webcam frame
        success, img = self.cap.read()
        if success:
            # Mirror the frame (feels more natural)
            img = cv2.flip(img, 1)

            # Detect hands (draw landmarks if debug is True)
            img, results = self.hand_tracker.find_hands(img, draw=self.debug)

            # Extract landmark positions from detection results
            lmList = self.hand_tracker.findPosition(img, results)

            # If hand found and game is active
            if lmList and self.playing:
                # Index finger tip is landmark 8: (id, x, y)
                index_finger = lmList[8]
                x, y = index_finger[1], index_finger[2]

                # Compute grid placement for mapping camera coordinates -> tile coordinates
                grid_width = GAME_SIZE * TILESIZE
                grid_height = GAME_SIZE * TILESIZE
                offset_x = (WIDTH - grid_width) // 2
                offset_y = (HEIGHT - grid_height) // 4+60

                # Convert pixel coords to grid coords
                tile_x = (x - offset_x) // TILESIZE
                tile_y = (y - offset_y) // TILESIZE

                if self.debug:
                    print(f"Hand at ({x}, {y}) -> Tile ({tile_x}, {tile_y})")

                # Check if within grid bounds
                if 0 <= tile_y < GAME_SIZE and 0 <= tile_x < GAME_SIZE:
                    tile = self.tiles[tile_y][tile_x]

                    # If we are pointing at a numbered tile and pinch gesture is detected
                    if tile.text != "empty" and self.hand_tracker.fingersClosed(lmList):
                        if self.debug:
                            print(f"Grabbing tile {tile.text} at ({tile_x}, {tile_y})")

                        # Check adjacent cells: down, up, right, left
                        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            new_x, new_y = tile_x + dx, tile_y + dy

                            # Make sure adjacent cell is valid
                            if 0 <= new_y < GAME_SIZE and 0 <= new_x < GAME_SIZE:
                                # If adjacent cell is empty -> perform swap
                                if self.tiles_grid[new_y][new_x] == 0:
                                    # Swap values in the numeric grid
                                    self.tiles_grid[tile_y][tile_x], self.tiles_grid[new_y][new_x] = 0, self.tiles_grid[tile_y][tile_x]

                                    # Update tile object's grid coordinates
                                    tile.x, tile.y = new_x, new_y

                                    # Update coordinates for tile objects being swapped
                                    self.tiles[tile_y][tile_x].x, self.tiles[tile_y][tile_x].y = new_x, new_y
                                    self.tiles[new_y][new_x].x, self.tiles[new_y][new_x].y = tile_x, tile_y

                                    # Swap tile objects in self.tiles 2D list
                                    self.tiles[tile_y][tile_x], self.tiles[new_y][new_x] = self.tiles[new_y][new_x], self.tiles[tile_y][tile_x]

                                    # Recompute pixel positions after move
                                    tile.update_position()
                                    self.tiles[new_y][new_x].update_position()

                                    # Increment move counter
                                    self.moves += 1

                                    # Find empty position and target position to check adjacency success
                                    empty_pos = None
                                    target_pos = None
                                    for i in range(GAME_SIZE):
                                        for j in range(GAME_SIZE):
                                            if self.tiles_grid[i][j] == 0:
                                                empty_pos = (i, j)
                                            if self.tiles[i][j] == self.target_tile:
                                                target_pos = (i, j)

                                    # If empty is adjacent to target -> successful objective move
                                    if empty_pos and target_pos:
                                        ddx = abs(empty_pos[0] - target_pos[0])
                                        ddy = abs(empty_pos[1] - target_pos[1])
                                        if (ddx == 1 and ddy == 0) or (ddx == 0 and ddy == 1):
                                            self.handle_successful_move()
                                            print(f"Target success! Score: {self.score}")

                                    if self.debug:
                                        print(f"Moved to ({new_x}, {new_y})")

                                    # If the moved tile was the target tile, also handle highlight change
                                    if tile == self.target_tile:
                                        if self.success_sound:
                                            self.success_sound.play()
                                        self.target_tile.highlight(False)
                                        self.set_new_target()

                                    # Stop checking directions after one successful move
                                    break

    def draw(self):
        """Draw the webcam background, overlay, tiles, grid lines, and HUD text."""
        if not self.running:
            return

        # Read webcam frame for background
        success, img = self.cap.read()
        if success:
            img = cv2.flip(img, 1)
            img = cv2.resize(img, (WIDTH, HEIGHT))

            # If debug, draw landmarks on frame (visual feedback)
            if self.debug:
                img, _ = self.hand_tracker.find_hands(img)

            # Convert OpenCV BGR to RGB for pygame
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Convert numpy array to pygame surface (rotate because surfarray axes differ)
            background = pygame.surfarray.make_surface(np.rot90(img_rgb))

            # Draw webcam background on window
            self.screen.blit(background, (0, 0))

        # Grid overlay sizes and offsets
        grid_width = GAME_SIZE * TILESIZE
        grid_height = GAME_SIZE * TILESIZE
        offset_x = (WIDTH - grid_width) // 2
        offset_y = (HEIGHT - grid_height) // 4+60

        # Semi-transparent overlay behind the tiles
        overlay = pygame.Surface((grid_width, grid_height))
        overlay.fill(DARKGREY)
        overlay.set_alpha(100)
        self.screen.blit(overlay, (offset_x, offset_y))

        # Draw all sprites (tiles)
        self.all_sprites.draw(self.screen)

        # Draw grid lines on top
        self.draw_grid()

        # If game is active, draw HUD text (moves/time/target instruction)
        if self.playing and self.start_time:
            elapsed_time = time.time() - self.start_time
            font = pygame.font.Font(None, 30)

            # Get label of current target tile (number)
            tile_label = self.target_tile.text if self.target_tile else ""

            # Translate UI strings based on current language
            moves_text = font.render(f"{self.tr('moves')}: {self.moves}", True, (255, 255, 255))
            time_text = font.render(f"{self.tr('time')}: {elapsed_time:.1f}s", True, (255, 255, 255))
            target_text = font.render(self.tr("move_tile_to_yellow", tile=tile_label), True, (255, 255, 255))

            # Render black outlines for readability
            moves_text_outline = font.render(f"{self.tr('moves')}: {self.moves}", True, BLACK)
            time_text_outline = font.render(f"{self.tr('time')}: {elapsed_time:.1f}s", True, BLACK)
            target_text_outline = font.render(self.tr("move_tile_to_yellow", tile=tile_label), True, BLACK)

            # Where to place text (below the grid)
            text_y = offset_y -80

            # Draw outline then main text to create a shadow effect
            self.screen.blit(moves_text_outline, (offset_x - 2, text_y - 2))
            self.screen.blit(moves_text_outline, (offset_x + 2, text_y + 2))
            self.screen.blit(moves_text, (offset_x, text_y))

            self.screen.blit(time_text_outline, (offset_x + grid_width // 2 - 50 - 2, text_y - 2))
            self.screen.blit(time_text_outline, (offset_x + grid_width // 2 - 50 + 2, text_y + 2))
            self.screen.blit(time_text, (offset_x + grid_width // 2 - 50, text_y))

            self.screen.blit(target_text_outline, (offset_x - 2, text_y + 40 - 2))
            self.screen.blit(target_text_outline, (offset_x + 2, text_y + 40 + 2))
            self.screen.blit(target_text, (offset_x, text_y + 40))

        # Present the final frame
        pygame.display.flip()

    def draw_grid(self):
        """Draw grid lines over the puzzle area."""
        grid_width = GAME_SIZE * TILESIZE
        grid_height = GAME_SIZE * TILESIZE
        offset_x = (WIDTH - grid_width) // 2
        offset_y = (HEIGHT - grid_height) // 4+60

        # Vertical lines
        for row in range(0, GAME_SIZE * TILESIZE + 1, TILESIZE):
            pygame.draw.line(
                self.screen,
                LIGHTGREY,
                (offset_x + row, offset_y),
                (offset_x + row, offset_y + grid_height)
            )

        # Horizontal lines
        for col in range(0, GAME_SIZE * TILESIZE + 1, TILESIZE):
            pygame.draw.line(
                self.screen,
                LIGHTGREY,
                (offset_x, offset_y + col),
                (offset_x + grid_width, offset_y + col)
            )


# Run the game when this file is executed directly (not imported as a module)
if __name__ == "__main__":
    game = Game()              # Create Game object (window, camera, state, etc.)
    game.show_instructions()   # Show intro/instructions screen
    game.new()                 # Create a new puzzle board
    game.run()                 # Start main loop (events + draw)
