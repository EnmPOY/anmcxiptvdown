import os, time, glob, logging, subprocess
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# 1. AYARLAR VE LOGLAMA
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler()]
)

HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

class StealthBot:
    def __init__(self):
        logging.info("🕵️ Bot hazırlanıyor. Sürüm kontrolü yapılıyor...")
        chrome_ver = None
        try:
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
            logging.info(f"🌐 Sunucu Chrome Sürümü: {chrome_ver}")
        except: pass

        opts = uc.ChromeOptions()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument('--disable-blink-features=AutomationControlled')
        
        self.driver = uc.Chrome(options=opts, version_main=chrome_ver)
        self.api = HfApi()

    def analyzer(self, url):
        try:
            logging.info(f"🔍 Analiz Ediliyor: {url}")
            self.driver.get(url)
            
            # Sitenin Angular/SPA yapısını ve Cloudflare'i bekliyoruz
            time.sleep(12) 
            wait = WebDriverWait(self.driver, 35)
            
            # Fansub kartlarını bekle
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_rating = None, -1.0
            
            for card in cards:
                try:
                    puan = float(card.find_element(By.CLASS_NAME, "rating-value").text)
                    if puan > max_rating:
                        max_rating, best_card = puan, card
                except: continue

            if best_card:
                logging.info(f"🏆 Puanı En Yüksek Seçildi: {max_rating}")
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(8) # Player'ın enjekte olması için bekle
                
                for frame in self.driver.find_elements(By.TAG_NAME, "iframe"):
                    src = frame.get_attribute("src")
                    if src and any(d in src for d in ["vidmoly", "sibnet", "ok.ru", "player"]):
                        return src
        except Exception as e:
            logging.error(f"❌ Sayfa Analiz Hatası: {e}")
        return None

    def downloader(self, link, name, ep):
        fname = f"{name}_B{ep}.mp4"
        opts = {'outtmpl': fname, 'quiet': True, 'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'}
        try:
            logging.info(f"🌪️ İndirme Başladı: {fname}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([link])
            return fname
        except: return None

    def upload_and_m3u(self, file, name, ep):
        target_path = f"{name}/{file}"
        try:
            logging.info(f"📤 Hugging Face Aktarımı: {target_path}")
            self.api.upload_file(
                path_or_fileobj=file,
                path_in_repo=target_path,
                repo_id=REPO_ID,
                repo_type="dataset",
                token=HF_TOKEN
            )
            
            # M3U Linkini Oluştur
            raw = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{target_path}"
            m3u_name = f"{name}_IPTV_Listesi.m3u"
            with open(m3u_name, "a", encoding="utf-8") as f:
                if os.path.getsize(m3u_name) == 0: f.write("#EXTM3U\n")
                f.write(f"#EXTINF:-1, {name} - Bolum {ep}\n{raw}\n")
            
            os.remove(file)
            logging.info(f"✅ Bölüm {ep} Tamamlandı!")
        except Exception as e:
            logging.error(f"☁️ HF/M3U Hatası: {e}")

    def run(self):
        if not ANIME_URL: return
        # Anime adını URL'den çek (Örn: jujutsu-kaisen)
        anime_name = ANIME_URL.split('/')[-5].replace('-', '_').title()
        
        for ep in range(START_EP, END_EP + 1):
            target = f"{ANIME_URL}{ep}"
            iframe = self.analyzer(target)
            if iframe:
                file = self.downloader(iframe, anime_name, ep)
                if file and os.path.exists(file):
                    self.upload_and_m3u(file, anime_name, ep)
        
        self.driver.quit()

if __name__ == "__main__":
    bot = StealthBot()
    bot.run()
