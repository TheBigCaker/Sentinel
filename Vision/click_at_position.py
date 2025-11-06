import pyautogui
import time
import sys

# --- CONFIGURATION ---
# MANUALLY UPDATE THESE COORDINATES
# Run get_mouse_position.py to find the (X, Y) of your target
TARGET_X = 100
TARGET_Y = 100
# ---------------------

def main(x, y):
    print(f"--- Automated Clicker ---")
    
    if x == 100 and y == 100:
        print("ERROR: Please edit this script and update")
        print("       the TARGET_X and TARGET_Y variables.")
        sys.exit(1)
        
    try:
        print("Giving you 3 seconds to switch windows...")
        print("3...")
        time.sleep(1)
        print("2...")
        time.sleep(1)
        print("1...")
        time.sleep(1)
        
        print(f"Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.25)
        
        print("Clicking...")
        pyautogui.click()
        
        print("--- Click Complete ---")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main(TARGET_X, TARGET_Y)