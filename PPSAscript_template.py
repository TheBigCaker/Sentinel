import os
import json

"""
This is a *template* Python script.
Placeholders like _USERNAME_ and _USER_ID_ will be replaced
by the PowerShell orchestrator before this script is run.
"""

def create_user_data():
    # --- Placeholders to be injected ---
    username = "_USERNAME_"
    user_id = _USER_ID_
    output_filename = "user_data.json"
    # -----------------------------------

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