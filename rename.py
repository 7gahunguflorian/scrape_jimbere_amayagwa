import os


folder = "scraped_articles"


prefix = "jimbere_amayagwa_"


for filename in os.listdir(folder):
    if filename.endswith(".md") and not filename.startswith(prefix):
        old_path = os.path.join(folder, filename)
        new_filename = prefix + filename
        new_path = os.path.join(folder, new_filename)
        os.rename(old_path, new_path)
        print(f"✅ Renommé : {filename} → {new_filename}")

print("Tous les fichiers ont été renommés avec succès.")