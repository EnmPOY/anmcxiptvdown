import os, time, glob, logging, subprocess
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# 1. LOGLAMA SİSTEMİ
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.FileHandler("arsiv_sistemi.log", encoding="utf-8"), logging.StreamHandler()]
)

# ---------------------------------------------------------
# 2. YAPILANDIRMA (Config)
# ---------------------------------------------------------
class Config:
    # GitHub Secrets'tan gelmezse buradakini kullanır (Güvenlik için Secrets önerilir)
    HF_TOKEN = os.getenv("HF_TOKEN", "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")
    REPO_ID = "Enmpoy/allmoviesornimetr"
    
    # 🎯 HEDEF LİSTESİ (Buraya istediğin kadar ekleme yapabilirsin)
    TARGETS = [
        {"name": "Jujutsu_Kaisen", "base_url": "https://animecix.tv/titles/7352/jujutsu-kaisen/season/1/episode/", "start": 1, "end": 24},
        {"name": "Naruto", "base_url": "https://animecix.tv/titles/80/naruto/season/1/episode/", "start": 1, "end": 220},
        {"name": "Naruto-Shippuden", "base_url": "https://animecix.tv/titles/7490/naruto-shippuuden/season/1/episode/", "start": 1, "end": 500}
    ]

# ---------------------------------------------------------
# 3. HAYALET TARAYICI (Versiyon Hataları Çözülmüş)
# ---------------------------------------------------------
class StealthBrowser:
    @staticmethod
    def initialize():
        logging.info("🕵️ Hayalet tarayıcı sürüm kontrolü yapılıyor...")
        
        # --- KRİTİK DÜZELTME: Chrome Versiyonunu Tespit Et ---
        chrome_main_version = None
        try:
            version_output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_main_version = int(version_output.split()[2].split('.')[0])
            logging.info(f"🌐 GitHub Sunucusundaki Chrome Sürümü: {chrome_main_version}")
        except Exception as e:
            logging.warning(f"⚠️ Sürüm tespit edilemedi, otomatik denenecek: {e}")

        opts = uc.ChromeOptions()
        opts.add_argument('--headless') # Sunucuda ekran olmadığı için şart
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--mute-audio')
        
        # Sürüm çakışmasını önlemek için version_main parametresini veriyoruz
        return uc.Chrome(options=opts, version_main=chrome_main_version)

# ---------------------------------------------------------
# 4. SİTE PARÇALAYICI (Zeki Seçim Sistemi)
# ---------------------------------------------------------
class SiteAnalyzer:
    def __init__(self, driver):
        self.driver = driver

    def extract_premium_iframe(self, target_url):
        try:
            logging.info(f"🔍 Sayfa analiz ediliyor: {target_url}")
            self.driver.get(target_url)
            
            # Sayfanın ve fansub kartlarının gelmesini bekle
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_rating = None, -1.0
            
            # En yüksek puanlı olanı bulma döngüsü
            for card in cards:
                try:
                    r_text = card.find_element(By.CLASS_NAME, "rating-value").text
                    r_val = float(r_text)
                    if r_val > max_rating:
                        max_rating, best_card = r_val, card
                except: continue

            if best_card:
                logging.info(f"🏆 Seçilen Fansub Puanı: {max_rating}")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_card)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(7) # Player'ın yüklenmesi için geniş zaman
                
                # Player iframe'ini bulma
                for frame in self.driver.find_elements(By.TAG_NAME, "iframe"):
                    src = frame.get_attribute("src")
                    if src and any(d in src for d in ["vidmoly", "sibnet", "ok.ru", "player", "odnoklassniki"]):
                        return src
        except Exception as e:
            logging.error(f"❌ Analiz Hatası: {str(e)[:100]}")
        return None

# ---------------------------------------------------------
# 5. İNDİRME MOTORU (yt-dlp Gücü)
# ---------------------------------------------------------
class Downloader:
    @staticmethod
    def pull_video(iframe_url, anime_name, ep_num):
        filename = f"{anime_name}_B{ep_num}.mp4"
        ydl_opts = {
            'outtmpl': filename, 
            'quiet': True, 
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        }
        try:
            logging.info(f"🌪️ Video sökülüyor: {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([iframe_url])
            return filename
        except Exception as e:
            logging.error(f"💀 İndirme Patladı: {e}")
            return None

# ---------------------------------------------------------
# 6. BULUT VE LİSTE YÖNETİCİSİ
# ---------------------------------------------------------
class CloudAndPlaylistManager:
    def __init__(self):
        self.api = HfApi()

    def process_and_upload(self, local_file, anime_name, ep_num):
        hf_path = f"{anime_name}/{local_file}"
        try:
            logging.info(f"📤 Hugging Face'e fırlatılıyor: {hf_path}")
            self.api.upload_file(
                path_or_fileobj=local_file,
                path_in_repo=hf_path,
                repo_id=Config.REPO_ID,
                repo_type="dataset",
                token=Config.HF_TOKEN
            )
            
            # Linki hazırla ve M3U dosyasına bas
            raw_url = f"https://huggingface.co/datasets/{Config.REPO_ID}/resolve/main/{hf_path}"
            m3u_file = f"{anime_name}_IPTV.m3u"
            
            with open(m3u_file, "a", encoding="utf-8") as f:
                if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                f.write(f"#EXTINF:-1, {anime_name} - Bölüm {ep_num}\n{raw_url}\n")
            
            os.remove(local_file) # İşlem bitince sil ki yer kaplamasın
            logging.info(f"✅ Başarıyla tamamlandı: {ep_num}")
            
        except Exception as e:
            logging.error(f"☁️ HF Yükleme Hatası: {e}")

# ---------------------------------------------------------
# 7. ORKESTRATÖR (Sistemin Kalbi)
# ---------------------------------------------------------
class Orchestrator:
    def run_forever(self):
        cloud_mgr = CloudAndPlaylistManager()
        
        while True:
            driver = None
            try:
                driver = StealthBrowser.initialize()
                analyzer = SiteAnalyzer(driver)
                
                for target in Config.TARGETS:
                    name = target["name"]
                    logging.info(f"📺 {name} Serisi Başlatılıyor...")
                    
                    for ep in range(target["start"], target["end"] + 1):
                        url = f"{target['base_url']}{ep}"
                        
                        iframe = analyzer.extract_premium_iframe(url)
                        if not iframe: continue
                        
                        video_file = Downloader.pull_video(iframe, name, ep)
                        
                        # Dosya inmiş mi kontrol et (bazen yt-dlp uzantıyı değiştirebilir)
                        files = glob.glob(f"{name}_B{ep}.*")
                        if files:
                            cloud_mgr.process_and_upload(files[0], name, ep)
                            
                logging.info("💤 Liste bitti. 2 saat sonra tekrar kontrol edilecek.")
                if driver: driver.quit()
                time.sleep(7200)
                
            except Exception as e:
                logging.critical(f"💥 KRİTİK ÇÖKME: {e}")
                if driver: 
                    try: driver.quit()
                    except: pass
                time.sleep(180) # 3 dakika bekle ve yeniden dene

if __name__ == "__main__":
    bot = Orchestrator()
    bot.run_forever()
