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
# Değerler GitHub Actions "env" kısmından veya manuel olarak çekilir.
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

# ---------------------------------------------------------
# 3. HAYALET TARAYICI MODÜLÜ (Sürüm Çakışması Engelli)
# ---------------------------------------------------------
class StealthBrowser:
    @staticmethod
    def initialize():
        logging.info("🕵️ Tarayıcı hazırlanıyor. Sürüm kontrolü yapılıyor...")
        chrome_ver = None
        try:
            # Sistemdeki Chrome versiyonunu tespit et (145/146 hatasını çözer)
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
            logging.info(f"🌐 Sunucu Chrome Sürümü: {chrome_ver}")
        except Exception as e:
            logging.warning(f"⚠️ Sürüm tespit edilemedi, otomatik modda denenecek: {e}")

        opts = uc.ChromeOptions()
        opts.add_argument('--headless') # Sunucuda ekran olmadığı için şart
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080') # Sayfayı HD boyutta aç (SPA için kritik)
        opts.add_argument('--disable-blink-features=AutomationControlled') # Bot olduğumuzu gizle
        
        # Gerçek kullanıcı kimliği (User-Agent)
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        driver = uc.Chrome(options=opts, version_main=chrome_ver)
        driver.set_page_load_timeout(60)
        return driver

# ---------------------------------------------------------
# 4. SİTE ANALİZ MOTORU (Angular & SPA Uyumlu)
# ---------------------------------------------------------
class AnimeAnalyzer:
    def __init__(self, driver):
        self.driver = driver

    def extract_video_source(self, url):
        try:
            logging.info(f"🔍 Analiz Hedefi: {url}")
            self.driver.get(url)
            
            # 1. BEKLEME: Cloudflare ve sayfa iskeletinin (app-root) oturması için
            time.sleep(15) 
            
            # 2. BEKLEME: Dinamik içeriğin (Angular) yüklenmesi
            # Sayfayı hafifçe kaydırarak lazy-load içerikleri tetikle
            self.driver.execute_script("window.scrollTo(0, 500);")
            
            wait = WebDriverWait(self.driver, 40)
            logging.info("⏳ Çevirmen kartları bekleniyor...")
            
            # Sitenin Angular yapısına göre 'translator-card' elementini bekle
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_rating = None, -1.0
            
            # En yüksek puanlı çevirmeni matematiksel olarak bul
            for card in cards:
                try:
                    r_text = card.find_element(By.CLASS_NAME, "rating-value").text
                    r_val = float(r_text)
                    if r_val > max_rating:
                        max_rating, best_card = r_val, card
                except: continue

            if best_card:
                logging.info(f"🏆 En iyi çeviri seçildi: {max_rating} Puan")
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(10) # Player iframe'inin DOM'a düşmesi için bekle
                
                # Iframe içinde video kaynağını tara
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    if src and any(d in src for d in ["vidmoly", "sibnet", "ok.ru", "player", "odnoklassniki"]):
                        logging.info(f"🔗 Kaynak URL yakalandı: {src[:50]}...")
                        return src
        except Exception as e:
            logging.error(f"❌ Analiz Başarısız: {str(e)[:100]}")
        return None

# ---------------------------------------------------------
# 5. İNDİRME, YÜKLEME VE LİSTELEME MOTORU
# ---------------------------------------------------------
class MediaManager:
    def __init__(self):
        self.api = HfApi()

    def process_episode(self, iframe_link, anime_name, ep):
        filename = f"{anime_name}_Bolum_{ep}.mp4"
        ydl_opts = {
            'outtmpl': filename,
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        }
        
        try:
            # 1. ADIM: İndirme (yt-dlp)
            logging.info(f"🌪️ Bölüm {ep} indiriliyor...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([iframe_link])
            
            if os.path.exists(filename):
                # 2. ADIM: Hugging Face Yükleme
                hf_path = f"{anime_name}/{filename}"
                logging.info(f"📤 Hugging Face aktarımı: {hf_path}")
                self.api.upload_file(
                    path_or_fileobj=filename,
                    path_in_repo=hf_path,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
                
                # 3. ADIM: IPTV M3U Kaydı
                # Hugging Face resolve linki üzerinden doğrudan izleme linki oluştur
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{anime_name}_IPTV.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {anime_name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename) # Diski temiz tut
                logging.info(f"✅ Bölüm {ep} operasyonu başarıyla bitti.")
        except Exception as e:
            logging.error(f"💀 Medya İşleme Hatası: {e}")

# ---------------------------------------------------------
# 6. ANA ORKESTRATÖR (Döngü Yönetimi)
# ---------------------------------------------------------
def run_mission():
    if not ANIME_URL:
        logging.error("❗ HATA: Anime URL bulunamadı! Lütfen link girdiğinizden emin olun.")
        return

    # Anime adını URL'den otomatik temizle (Örn: jujutsu-kaisen)
    try:
        anime_folder = ANIME_URL.split('/titles/')[1].split('/')[1].replace('-', '_').title()
    except:
        anime_folder = "Bilinmeyen_Anime"

    browser = StealthBrowser.initialize()
    analyzer = AnimeAnalyzer(browser)
    manager = MediaManager()

    for ep in range(START_EP, END_EP + 1):
        logging.info(f"\n{'='*40}\n🎬 BÖLÜM {ep} BAŞLATILDI\n{'='*40}")
        
        target_page = f"{ANIME_URL}{ep}"
        iframe_src = analyzer.extract_video_source(target_page)
        
        if iframe_src:
            manager.process_episode(iframe_src, anime_folder, ep)
        else:
            logging.warning(f"⏩ Bölüm {ep} atlanıyor: Kaynak bulunamadı.")

    browser.quit()
    logging.info("🎉 GÖREV TAMAMLANDI: Bütün bölümler arşivlendi ve IPTV listesi güncellendi!")

if __name__ == "__main__":
    run_mission()
