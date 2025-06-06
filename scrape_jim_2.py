from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import re
import socket

class ArticleScraper:
    def __init__(self):
        self.setup_driver()
        self.results_dir = "scraped_articles"
        os.makedirs(self.results_dir, exist_ok=True)
        self.last_position_file = "last_position.txt"

    def setup_driver(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--log-level=3")  # Supprime les logs verbeux
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.driver.implicitly_wait(10)

    def is_internet_available(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def wait_for_content_load(self, timeout=30):
        """Attend que le contenu se charge selon la page actuelle"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.archive-col-list li.infinite-post, h1.post-title.entry-title"))
            )
            return True
        except TimeoutException:
            print("⚠️ Timeout : Aucun élément trouvé sur cette page")
            return False

    def load_more_posts(self, max_retries=5, delay_between_clicks=3):
        """Clique sur 'More Posts' ET attend qu'un nouvel article apparaisse"""
        print("🔄 Tentative de charger plus d'articles...")

        for attempt in range(1, max_retries + 1):
            try:
                initial_count = len(self.driver.find_elements(By.CSS_SELECTOR, "ul.archive-col-list li.infinite-post"))
                print(f"🔢 Nombre initial d'articles : {initial_count}")

                more_button = self.driver.find_element(By.CSS_SELECTOR, ".inf-more-but")
                if not more_button.is_displayed():
                    print("✅ Plus aucun bouton 'More Posts' visible.")
                    return False

                print(f"🖱️ Clic sur 'More Posts' (tentative {attempt}/{max_retries})...")
                more_button.click()
                time.sleep(delay_between_clicks)

                start_time = time.time()
                timeout = 10

                while True:
                    current_count = len(self.driver.find_elements(By.CSS_SELECTOR, "ul.archive-col-list li.infinite-post"))
                    if current_count > initial_count:
                        print(f"✅ Nouveaux articles chargés ! ({current_count} au total)")
                        return True
                    elif time.time() - start_time > timeout:
                        print("⏳ Timeout : Aucun nouvel article après plusieurs secondes d'attente.")
                        break
                    else:
                        print("🌀 En attente de nouveaux articles...")
                        time.sleep(1)

            except NoSuchElementException:
                print("🏁 Fin : Bouton 'More Posts' introuvable.")
                return False
            except Exception as e:
                print(f"❌ Erreur lors du clic sur 'More Posts' : {e}")
                return False

        print("🔚 Aucun nouvel article trouvé après plusieurs tentatives.")
        return False

    def get_next_article_link(self, search_url, index):
        print(f"🔄 Chargement de la page de recherche : {search_url}")
        self.driver.get(search_url)
        self.wait_for_content_load()

        ul = self.driver.find_element(By.CSS_SELECTOR, "ul.archive-col-list")
        lis = ul.find_elements(By.CSS_SELECTOR, "li.infinite-post")

        if index < len(lis):
            return lis[index].find_element(By.TAG_NAME, "a").get_attribute("href")

        while True:
            if self.load_more_posts():
                ul = self.driver.find_element(By.CSS_SELECTOR, "ul.archive-col-list")
                lis = ul.find_elements(By.CSS_SELECTOR, "li.infinite-post")
                if index < len(lis):
                    return lis[index].find_element(By.TAG_NAME, "a").get_attribute("href")
            else:
                print("❌ Plus aucun article à charger.")
                return None

    def load_last_position(self):
        if os.path.exists(self.last_position_file):
            with open(self.last_position_file, "r") as f:
                try:
                    return int(f.read())
                except:
                    return 0
        return 0

    def save_last_position(self, position):
        with open(self.last_position_file, "w") as f:
            f.write(str(position))

    def scrape_article(self, url):
        print(f"📖 Scraping article : {url}")
        retry_count = 0
        max_retries = 5

        while retry_count < max_retries:
            try:
                self.driver.get(url)
                if self.wait_for_article_content(timeout=30):
                    header = self.driver.find_element(By.CSS_SELECTOR, "h1.post-title.entry-title").text.strip()
                    paragraphs = []
                    for p in self.driver.find_elements(By.CSS_SELECTOR, "#content-main > p"):
                        text = p.text.strip()
                        if text:
                            paragraphs.append(text)
                    return {"header": header, "paragraphs": paragraphs}
                else:
                    raise Exception("Chargement échoué")
            except Exception as e:
                print(f"⚠️ Erreur : {e}")
                if not self.is_internet_available():
                    print("🌐 Connexion perdue. En attente de rétablissement...")
                    self.handle_interruption()
                    self.setup_driver()
                else:
                    print(f"🔄 Réessai {retry_count+1}/{max_retries}...")
                    retry_count += 1
                    time.sleep(5)
        print("❌ Échec final pour cet article.")
        return None

    def handle_interruption(self):
        attempts = 0
        while not self.is_internet_available() and attempts < 10:
            print(f"⏳ Attente... ({attempts * 60 // 60} min)")
            time.sleep(60)
            attempts += 1
        if attempts >= 10:
            print("❌ Trop d'attentes. Arrêt.")
            exit()

    def wait_for_article_content(self, timeout=30):
        """Attends spécifiquement le contenu d'un article"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1.post-title.entry-title"))
            )
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#content-main > p"))
            )
            print("✅ Titre et paragraphe trouvés. Page prête.")
            return True
        except TimeoutException:
            print("⚠️ Impossible de charger le contenu de l'article.")
            return False

    def save_article_to_markdown(self, data, filename):
        path = os.path.join(self.results_dir, f"{filename}.md")
        content = f"# {data['header']}\n\n"
        content += "\n\n".join(data["paragraphs"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"💾 Fichier sauvegardé : {path}")

    def run_scraping(self, search_url):
        print("🚀 Démarrage du scraping...")
        start_index = self.load_last_position()
        print(f"🔁 Reprise à partir de l'article #{start_index}")
        index = start_index

        while True:
            print(f"\n📌 Article #{index + 1}")
            link = self.get_next_article_link(search_url, index)
            if not link:
                print("✅ Fin des articles.")
                break
            data = self.scrape_article(link)
            if data:
                clean_name = re.sub(r"[^a-zA-Z0-9]", "_", data["header"]).strip("_")
                self.save_article_to_markdown(data, clean_name)
                self.save_last_position(index + 1)
            index += 1

        print("🏁 Scraping terminé !")

    def close(self):
        if hasattr(self, "driver"):
            self.driver.quit()
            print("🔧 Navigateur fermé")

def main():
    scraper = None
    try:
        scraper = ArticleScraper()
        search_url = "https://www.jimberemag.org/amayagwa/?s=amayagwa"
        scraper.run_scraping(search_url)
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur générale : {e}")
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()