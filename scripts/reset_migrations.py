import os
import shutil

def clean_migrations():
    # Current directory se start karenge
    root_dir = os.getcwd()
    
    print(f"Scanning for 'migrations' folders in: {root_dir}")
    
    count = 0
    for root, dirs, files in os.walk(root_dir):
        if "migrations" in dirs:
            migrations_path = os.path.join(root, "migrations")
            
            # Migrations folder ke andar ki files check karo
            for filename in os.listdir(migrations_path):
                file_path = os.path.join(migrations_path, filename)
                
                # __init__.py ko ignore karo (ISE MAT DELETE KARNA)
                if filename == "__init__.py":
                    continue
                
                # __pycache__ folder ko uda do
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    print(f"Deleted directory: {file_path}")
                
                # Baaki saari files (.py, .pyc) uda do
                else:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                    count += 1

    print(f"\nSuccessfully deleted {count} migration files.")
    print("All __init__.py files are SAFE. ✅")

if __name__ == "__main__":
    clean_migrations()