import sqlite3
import chromadb
import json
import os
from peewee import (Model, SqliteDatabase, CharField, IntegerField, 
                    TextField, ForeignKeyField, DoesNotExist)

# This will hold our ChromaDB and SQLite DB
db = None
client = None

# --- 1. SQL DATABASE (The "Facts" / "Where") ---
# Defines the structure for our Factual (SQL) memory.

class BaseModel(Model):
    class Meta:
        database = None

class AppContext(BaseModel):
    """e.g., 'chrome.exe', 'Google Chrome'"""
    app_name = CharField(unique=True)
    window_title = CharField() # Can be a regex later

class VisualFact(BaseModel):
    """
    A fact linking a visual object to its context.
    'This 'copy_button' (a vector in ChromaDB) was last
    seen in the 'chrome.exe' app at (x, y).'
    """
    app_context = ForeignKeyField(AppContext, backref='facts')
    label = CharField() # e.g., 'gemini_copy_button'
    chroma_id = CharField() # The ID of the vector in ChromaDB
    last_known_x = IntegerField()
    last_known_y = IntegerField()
    notes = TextField(null=True)

# --- 2. VECTOR DATABASE (The "Looks" / "What") ---
# Manages the ChromaDB connection for visual memory.

class Memory:
    def __init__(self, db_path):
        self.db_path = db_path
        self.sqlite_file = os.path.join(db_path, 'sentinel_facts.db')
        self.chroma_path = os.path.join(db_path, 'sentinel_visuals')
        
        global db, client
        db = SqliteDatabase(self.sqlite_file)
        BaseModel._meta.database = db
        
        # We use a persistent client that saves to disk
        client = chromadb.PersistentClient(path=self.chroma_path)
        
        self.visual_collection = None

    def init_db(self):
        """Initializes both databases and creates tables/collections."""
        try:
            db.connect()
            db.create_tables([AppContext, VisualFact])
            print("[Memory] SQLite tables initialized.")
        except Exception as e:
            print(f"[Memory] Error initializing SQLite: {e}")
            
        try:
            # Get or create the collection for visual embeddings
            self.visual_collection = client.get_or_create_collection(
                name="visual_elements",
                metadata={"hnsw:space": "cosine"} # Use cosine distance for search
            )
            print(f"[Memory] ChromaDB collection 'visual_elements' initialized.")
        except Exception as e:
            print(f"[Memory] Error initializing ChromaDB: {e}")

    def store_visual_memory(self, label, embedding, app_name, window_title, x, y, notes=""):
        """
        Stores a new memory, linking both databases.
        This is the main "learning" function.
        """
        if self.visual_collection is None:
            self.init_db()
            
        try:
            # 1. Store the "Fact" in
            app, _ = AppContext.get_or_create(app_name=app_name, defaults={'window_title': window_title})
            
            # Use the label as the ID for simplicity
            chroma_id = f"{app_name}_{label}"
            
            fact, created = VisualFact.get_or_create(
                app_context=app,
                label=label,
                defaults={
                    'chroma_id': chroma_id,
                    'last_known_x': x,
                    'last_known_y': y,
                    'notes': notes
                }
            )
            
            if not created:
                # If it already exists, update its position
                fact.last_known_x = x
                fact.last_known_y = y
                fact.save()
                
            # 2. Store the "Look" in ChromaDB
            self.visual_collection.upsert(
                ids=[chroma_id],
                embeddings=[embedding],
                metadatas=[{"app": app_name, "label": label, "sql_id": fact.id}]
            )
            
            print(f"[Memory] Stored/Updated memory for '{label}' in '{app_name}'.")
            
        except Exception as e:
            print(f"[Memory] Error storing memory: {e}")

    def retrieve_fact_memory(self, label, app_name):
        """
        Retrieves the "Fact" (where) for a given element.
        "Where was the 'copy_button' in 'chrome.exe'?"
        """
        try:
            app = AppContext.get(AppContext.app_name == app_name)
            fact = VisualFact.get(VisualFact.app_context == app, VisualFact.label == label)
            return fact
        except DoesNotExist:
            print(f"[Memory] No fact memory found for '{label}' in '{app_name}'.")
            return None
        except Exception as e:
            print(f"[Memory] Error retrieving fact: {e}")
            return None

    def find_visual_match(self, query_embedding, num_results=1):
        """
        Finds the closest "Look" (what) in the vector database.
        "What element on screen is closest to this embedding?"
        """
        if self.visual_collection is None:
            self.init_db()
            
        try:
            results = self.visual_collection.query(
                query_embeddings=[query_embedding],
                n_results=num_results
            )
            return results
        except Exception as e:
            print(f"[Memory] Error querying ChromaDB: {e}")
            return None