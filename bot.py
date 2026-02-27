import os, time, glob, logging, subprocess
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# 1. LOGLAMA SİSTEMİ (Sistemin Gözü Kulağı)
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler()]
)

# ---------------------------------------------------------
# 2. YAPILANDIRMA (Config)
# ---------------------------------------------------------
# Senin verdiğin özel bilgiler buraya işlendi
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
FIXED_PROXY = "http://78.188.230.81:3310" # Senin verdiğin Türk Proxy'si

# GitHub Actions'tan gelen komutlar
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

# ---------------------------------------------------------
# 3. HAYALET TARAYICI MODÜLÜ (Proxy ve Sürüm Uyumlu)
# ---------------------------------------------------------
class StealthBrowser:
    @staticmethod
    def initialize():
        logging.info("🕵️ Tarayıcı hazırlanıyor. Proxy ve Sürüm kontrolü aktif...")
        chrome_ver = None
        try:
            # Sistemdeki Chrome sürümünü tespit et (145/146 hatasını çözer)
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
            logging.info(f"🌐 Sunucu Chrome Sürümü: {chrome_ver}")
        except: pass

        opts = uc.ChromeOptions()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        
        # PROXY ENJEKSİYONU
        logging.info(f"🔗 Bağlantı Türk Proxy üzerinden geçiyor: {FIXED_PROXY}")
        opts.add_argument(f'--proxy-server={FIXED_PROXY}')
        
        # İnsan taklidi ayarları
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        driver = uc.Chrome(options=opts, version_main=chrome_ver)
        return driver

# ---------------------------------------------------------
# 4. SİTE ANALİZ MOTORU (Angular & SPA Uyumlu)
# ---------------------------------------------------------
class AnimeAnalyzer:
    def __init__(self, driver):
        self.driver = driver

    def extract_source(self, url):
        try:
            logging.info(f"🔍 Analiz Ediliyor: {url}")
            self.driver.get(url)
            
            # Proxy ve Angular (SPA) yapısı için geniş bekleme süresi 
            time.sleep(20) 
            
            # Sayfayı kaydırarak elementlerin tetiklenmesini sağla
            self.driver.execute_script("window.scrollTo(0, 600);")
            
            wait = WebDriverWait(self.driver, 45)
            logging.info("⏳ Çevirmen kartları bekleniyor...")
            
            # Elementin DOM'a düşmesini bekle
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_rating = None, -1.0
            
            # En yüksek puanlı çevirmeni bul
            for card in cards:
                try:
                    r_text = card.find_element(By.CLASS_NAME, "rating-value").text
                    r_val = float(r_text)
                    if r_val > max_rating:
                        max_rating, best_card = r_val, card
                except: continue

            if best_card:
                logging.info(f"🏆 En İyi Fansub Seçildi: {max_rating} Puan")
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(10) # Player'ın enjekte olması için bekle
                
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    if src and any(d in src for d in ["vidmoly", "sibnet", "ok.ru", "player", "odnoklassniki"]):
                        return src
        except Exception as e:
            logging.error(f"❌ Analiz Hatası: {str(e)[:100]}")
        return None

# ---------------------------------------------------------
# 5. MEDYA İŞLEME VE BULUT AKTARIMI
# ---------------------------------------------------------
class MediaManager:
    def __init__(self):
        self.api = HfApi()

    def handle_episode(self, video_link, anime_name, ep):
        filename = f"{anime_name}_Bolum_{ep}.mp4"
        ydl_opts = {
            'outtmpl': filename,
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'proxy': FIXED_PROXY # İndirme de proxy üzerinden geçsin
        }
        
        try:
            logging.info(f"🌪️ Bölüm {ep} indiriliyor...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_link])
            
            if os.path.exists(filename):
                hf_path = f"{anime_name}/{filename}"
                logging.info(f"📤 Hugging Face Aktarımı: {hf_path}")
                self.api.upload_file(
                    path_or_fileobj=filename,
                    path_in_repo=hf_path,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
                
                # IPTV M3U Kaydı
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{anime_name}_IPTV_Playlist.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {anime_name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename) # Diski temizle
                logging.info(f"✅ Görev Başarıyla Tamamlandı!")
        except Exception as e:
            logging.error(f"💀 Medya Hatası: {e}")

# ---------------------------------------------------------
# 6. ANA OPERASYON (Döngü)
# ---------------------------------------------------------
def start_bot():
    if not ANIME_URL:
        logging.error("❗ URL Bulunamadı! GitHub üzerinden link girdiğinden emin ol.")
        return

    # Klasör adını temizle
    try:
        folder_name = ANIME_URL.split('/titles/')[1].split('/')[1].replace('-', '_').title()
    except:
        folder_name = "Anime_Arsiv"

    browser = StealthBrowser.initialize()
    analyzer = AnimeAnalyzer(browser)
    manager = MediaManager()

    for ep in range(START_EP, END_EP + 1):
        target_page = f"{ANIME_URL}{ep}"
        logging.info(f"\n--- BÖLÜM {ep} İŞLENİYOR ---")
        
        video_src = analyzer.extract_source(target_page)
        if video_src:
            manager.handle_episode(video_src, folder_name, ep)
        else:
            logging.warning(f"⏩ Bölüm {ep} atlanıyor: Kaynak bulunamadı.")

    browser.quit()
    logging.info("🎉 OPERASYON BİTTİ: Tüm bölümler Hugging Face'e taşındı.")

if __name__ == "__main__":
    start_bot()
