import pyautogui
import time

print("--- Mouse Position Finder ---")
print("Move your mouse to the desired location.")
print("The coordinates will be printed every second.")
print("Press CTRL+C to quit.")

try:
    while True:
        # Get the current mouse coordinates
        x, y = pyautogui.position()
        
        # Format the output
        positionStr = f'X: {str(x).rjust(4)} Y: {str(y).rjust(4)}'
        
        # Print the coordinates (and overwrite the same line)
        print(positionStr, end='\r')
        
        # Wait for one second
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\nDone.")