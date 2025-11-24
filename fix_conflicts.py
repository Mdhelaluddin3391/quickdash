import os

def clean_conflicts(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    keep = True

    for line in lines:
        if line.startswith("<<<<<<<"):
            keep = True  # Hum HEAD wala rakhna chahte hain
            continue
        if line.startswith("======="):
            keep = False  # Baaki delete
            continue
        if line.startswith(">>>>>>>"):
            keep = True
            continue

        if keep:
            new_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(new_lines)


for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith((".py", ".html", ".js", ".json", ".txt")):
            clean_conflicts(os.path.join(root, file))

print("✔ All merge conflicts cleaned. Only your latest code kept.")

