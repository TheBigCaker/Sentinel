import os
import json

"""
This is a generated Python script.
It creates a JSON file with some user data.
"""

def create_user_data():
    # --- Python Placeholders: Modify these values ---
    username = "david_baker"
    user_id = 1001
    output_filename = "user_data.json"
    # ------------------------------------------------

    print(f"[AutoScript] Starting: Will create {output_filename}...")
    
    data = {
        "user": username,
        "id": user_id,
        "status": "generated"
    }
    
    try:
        with open(output_filename, 'w') as f:
            json.dump(data, f, indent=4)
        
        print(f"[AutoScript] SUCCESS: Created {output_filename} at {os.getcwd()}")

    except Exception as e:
        print(f"[AutoScript] FAILED: An unexpected error occurred: {e}")
        
# --- Script Entry Point ---
if __name__ == "__main__":
    create_user_data()