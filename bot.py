import os, time, glob, logging, subprocess
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# 1. LOGLAMA SİSTEMİ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler()]
)

# 2. AYARLAR (GitHub Actions'tan Sinyalleri Alır)
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

class UltimateScraper:
    def __init__(self):
        logging.info("🕵️ Tarayıcı hazırlanıyor. Sürüm kontrolü aktif...")
        self.driver = self._init_driver()
        self.api = HfApi()

    def _init_driver(self):
        chrome_ver = None
        try:
            # Sistemdeki Chrome versiyonunu tespit et (Hataları önlemek için)
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
        except: pass

        options = uc.ChromeOptions()
        options.add_argument('--headless') # Sunucuda ekran olmadığı için şart
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080') # Angular elementlerinin görünmesi için HD boyut
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Gerçek kullanıcı kimliği
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        return uc.Chrome(options=options, version_main=chrome_ver)

    def solve_dynamic_page(self, url):
        try:
            logging.info(f"🔍 Analiz Ediliyor: {url}")
            self.driver.get(url)
            
            # Sayfa bir Angular SPA olduğu için JS'nin çalışmasını bekliyoruz
            time.sleep(15) 
            
            # Kaydırma yaparak lazy-load bileşenlerini tetikle
            self.driver.execute_script("window.scrollTo(0, 600);")
            
            # Çevirmen kartları gelene kadar maksimum 40 saniye sabret
            wait = WebDriverWait(self.driver, 40)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_rating = None, -1.0
            
            for card in cards:
                try:
                    rating_text = card.find_element(By.CLASS_NAME, "rating-value").text
                    rating = float(rating_text)
                    if rating > max_rating:
                        max_rating, best_card = rating, card
                except: continue

            if best_card:
                logging.info(f"🏆 En yüksek puanlı çeviri seçildi: {max_rating}")
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(10) # Player iframe'inin gelmesi için bekle
                
                # Iframe içinde video kaynağını tara
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    if src and any(d in src for d in ["vidmoly", "sibnet", "ok.ru", "player", "odnoklassniki"]):
                        return src
        except Exception as e:
            logging.error(f"❌ Sayfa Analiz Hatası (Angular yüklenemedi): {e}")
        return None

    def process_episode(self, video_link, anime_name, ep):
        filename = f"{anime_name}_Bolum_{ep}.mp4"
        ydl_opts = {
            'outtmpl': filename,
            'quiet': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        }
        
        try:
            logging.info(f"🌪️ İndirme Başladı: {filename}")
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
                logging.info(f"✅ Bölüm {ep} başarıyla tamamlandı.")
        except Exception as e:
            logging.error(f"💀 Medya İşleme Hatası: {e}")

    def start(self):
        if not ANIME_URL: return
        # Anime adını URL'den çek (Örn: naruto)
        try:
            anime_folder = ANIME_URL.split('/')[-5].replace('-', '_').title()
        except:
            anime_folder = "Genel_Arsiv"

        for ep in range(START_EP, END_EP + 1):
            target = f"{ANIME_URL}{ep}"
            video_src = self.solve_dynamic_page(target)
            
            if video_src:
                self.process_episode(video_src, anime_folder, ep)
            else:
                logging.warning(f"⏩ Bölüm {ep} atlanıyor: Kaynak bulunamadı.")
        
        self.driver.quit()

if __name__ == "__main__":
    bot = UltimateScraper()
    bot.start()
