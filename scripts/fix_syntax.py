import os

# Templates folder ka path
TEMPLATES_DIR = os.path.join(os.getcwd(), 'templates')

def fix_syntax_error():
    print(f"Scanning directory: {TEMPLATES_DIR} for syntax errors...")
    count = 0
    
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith(".html"):
                file_path = os.path.join(root, file)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Galti: {% static \'assets/...  --> Sahi: {% static 'assets/...
                # Hum backslash (\) ko hata rahe hain
                new_content = content.replace(r"{% static \'assets", r"{% static 'assets")
                new_content = new_content.replace(r"\' %}", r"' %}")
                
                if new_content != content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Fixed Syntax in: {file_path}")
                    count += 1
    
    print(f"\n✅ Successfully fixed {count} files!")

if __name__ == "__main__":
    fix_syntax_error()