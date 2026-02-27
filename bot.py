import os, time, glob, logging, subprocess
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# 1. LOGLAMA SİSTEMİ (Operasyon Takibi)
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler()]
)

# ---------------------------------------------------------
# 2. YAPILANDIRMA (Config)
# ---------------------------------------------------------
# Senin verdiğin TR Proxy adresi
FIXED_PROXY = "http://78.188.230.81:3310" 

# GitHub Secrets ve Inputs üzerinden gelen veriler
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

# ---------------------------------------------------------
# 3. HAYALET TARAYICI MODÜLÜ (Deep-Scan Hazır)
# ---------------------------------------------------------
class StealthBrowser:
    @staticmethod
    def initialize():
        logging.info("🕵️ Tarayıcı hazırlanıyor. Proxy ve Sürüm eşitleme aktif...")
        chrome_ver = None
        try:
            # GitHub sunucusundaki Chrome sürümünü (145/146) tespit et
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
            logging.info(f"🌐 Sistem Chrome Sürümü: {chrome_ver}")
        except: pass

        opts = uc.ChromeOptions()
        opts.add_argument('--headless') # Görünmez mod
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        
        # PROXY GİRİŞİ
        logging.info(f"🔗 TR Proxy üzerinden bağlanılıyor: {FIXED_PROXY}")
        opts.add_argument(f'--proxy-server={FIXED_PROXY}')
        
        # Bot korumalarını aşmak için kimlik gizleme
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        driver = uc.Chrome(options=opts, version_main=chrome_ver)
        return driver

# ---------------------------------------------------------
# 4. SİTE ANALİZ MOTORU (Angular & media-player Uyumlu)
# ---------------------------------------------------------
class AnimeAnalyzer:
    def __init__(self, driver):
        self.driver = driver

    def extract_direct_mp4(self, url):
        try:
            logging.info(f"🔍 Sayfaya sızılıyor: {url}")
            self.driver.get(url)
            
            # Angular (SPA) içeriğinin ve Proxy geçişinin oturması için sabırlı bekleme
            time.sleep(20) 
            
            wait = WebDriverWait(self.driver, 45)
            
            # ADIM 1: Fansub Kartını Tespit Et ve Tıkla
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            
            best_card, max_rating = None, -1.0
            for card in cards:
                try:
                    r_val = float(card.find_element(By.CLASS_NAME, "rating-value").text)
                    if r_val > max_rating:
                        max_rating, best_card = r_val, card
                except: continue

            if best_card:
                logging.info(f"🏆 Fansub Seçildi: {max_rating}. Video katmanı açılıyor...")
                self.driver.execute_script("arguments[0].click();", best_card)
                
                # ADIM 2: <media-player> İçindeki <source> Etiketini Bul
                # Senin verdiğin HTML yapısına göre derin analiz yapıyoruz
                time.sleep(15) # İçeriğin enjekte edilmesi için süre
                
                # Önce iframe'leri (kapsülleri) tara
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                logging.info(f"📦 {len(iframes)} adet iframe taramaya alınıyor...")

                for frame in iframes:
                    try:
                        self.driver.switch_to.frame(frame)
                        # Senin paylaştığın <source src="..."> yapısı
                        source_tag = self.driver.find_elements(By.TAG_NAME, "source")
                        if source_tag:
                            video_link = source_tag[0].get_attribute("src")
                            if video_link:
                                logging.info(f"🎯 Mp4 Linki Yakalandı: {video_link[:60]}...")
                                self.driver.switch_to.default_content()
                                return video_link
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue

                # Iframe dışında (ana DOM'da) ara
                source_tag = self.driver.find_elements(By.CSS_SELECTOR, "media-player source")
                if source_tag:
                    return source_tag[0].get_attribute("src")

        except Exception as e:
            logging.error(f"❌ Analiz Hatası: Element bulunamadı veya süre doldu. {e}")
        return None

# ---------------------------------------------------------
# 5. İNDİRME VE BULUT YÖNETİCİSİ (IDM Modu)
# ---------------------------------------------------------
class CloudManager:
    def __init__(self):
        self.api = HfApi()

    def download_and_store(self, mp4_url, anime_name, ep):
        filename = f"{anime_name}_B{ep}.mp4"
        
        # yt-dlp ayarları: Tıpkı IDM gibi çoklu kanaldan ve hızlı çeker
        ydl_opts = {
            'outtmpl': filename,
            'quiet': False,
            'proxy': FIXED_PROXY,
            'nocheckcertificate': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'headers': {
                'Referer': 'https://animecix.tv/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
        }

        try:
            logging.info(f"🌪️ IDM Modu Aktif: {filename} indiriliyor...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([mp4_url])
            
            if os.path.exists(filename):
                # Hugging Face'e fırlat
                hf_path = f"{anime_name}/{filename}"
                logging.info(f"📤 Bulut aktarımı başlatıldı: {hf_path}")
                self.api.upload_file(
                    path_or_fileobj=filename,
                    path_in_repo=hf_path,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
                
                # IPTV M3U Playlist Güncelleme
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{anime_name}_IPTV_List.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {anime_name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename) # Diski temiz tut
                logging.info(f"✅ Bölüm {ep} operasyonu başarıyla bitti!")
        except Exception as e:
            logging.error(f"💀 Medya İşleme Hatası: {e}")

# ---------------------------------------------------------
# 6. ANA DÖNGÜ (Orkestratör)
# ---------------------------------------------------------
def run_all():
    if not ANIME_URL:
        logging.error("❗ URL eksik! GitHub Actions üzerinden link girdiğinden emin ol.")
        return

    # Klasör ismini URL'den otomatik temizleyerek al
    try:
        anime_folder = ANIME_URL.split('/titles/')[1].split('/')[1].replace('-', '_').title()
    except:
        anime_folder = "Genel_Arsiv"

    browser = StealthBrowser.initialize()
    analyzer = AnimeAnalyzer(browser)
    cloud = CloudManager()

    for ep in range(START_EP, END_EP + 1):
        target_page = f"{ANIME_URL}{ep}"
        logging.info(f"\n--- 🎬 OPERASYON: BÖLÜM {ep} ---")
        
        video_link = analyzer.extract_direct_mp4(target_page)
        if video_link:
            cloud.download_and_store(video_link, anime_folder, ep)
        else:
            logging.warning(f"⏩ Bölüm {ep} atlanıyor: Kaynak linki sökülemedi.")

    browser.quit()
    logging.info("🎉 GÖREV TAMAMLANDI: IPTV listen ve arşivin hazır!")

if __name__ == "__main__":
    run_all()
