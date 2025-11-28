import os
import re

# Project ki templates directory ka path
TEMPLATES_DIR = os.path.join(os.getcwd(), 'templates')

def fix_static_files():
    print(f"Scanning directory: {TEMPLATES_DIR} ...")
    
    count = 0
    
    # Saare folders aur files traverse karein
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith(".html"):
                file_path = os.path.join(root, file)
                update_file(file_path)
                count += 1
    
    print(f"\n Successfully updated {count} HTML files!")

def update_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # 1. Add {% load static %} if missing
    if "{% load static %}" not in content:
        # <!DOCTYPE html> se pehle ya file ke start mein lagayein
        if "<!DOCTYPE html>" in content:
            content = content.replace("<!DOCTYPE html>", "{% load static %}\n<!DOCTYPE html>")
        else:
            content = "{% load static %}\n" + content

    # 2. Replace href="assets/..." -> href="{% static 'assets/...' %}"
    # Regex samjhata hai: href=" ya href=' phir assets/ phir kuch text phir quote band
    content = re.sub(
        r'href=["\']assets/([^"\']+)["\']', 
        r'href="{% static \'assets/\1\' %}"', 
        content
    )

    # 3. Replace src="assets/..." -> src="{% static 'assets/...' %}"
    content = re.sub(
        r'src=["\']assets/([^"\']+)["\']', 
        r'src="{% static \'assets/\1\' %}"', 
        content
    )

    # Sirf tab save karein agar kuch change hua ho
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
    else:
        print(f"Skipped (No changes needed): {file_path}")

if __name__ == "__main__":
    fix_static_files()