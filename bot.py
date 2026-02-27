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
    handlers=[logging.StreamHandler()]
)

# ---------------------------------------------------------
# 2. YAPILANDIRMA (Config)
# ---------------------------------------------------------
# Paylaşılan Türk Proxy'si ve Tokenlar
FIXED_PROXY = "http://78.188.230.81:3310" 
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

# İnsansı Kimlik Bilgisi (Bağlantı kopmalarını önler)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# ---------------------------------------------------------
# 3. ANALİZ MOTORU (Deep-Scan & Proxy Ready)
# ---------------------------------------------------------
class AnimeBot:
    def __init__(self):
        logging.info("🕵️ Bot hazırlanıyor. Proxy ve Bağlantı Koruma Modülü aktif...")
        self.driver = self._init_driver()
        self.api = HfApi()

    def _init_driver(self):
        chrome_ver = None
        try:
            # Sürüm hatasını (145/146) engellemek için sistem kontrolü
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
        except: pass

        opts = uc.ChromeOptions()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument(f'--proxy-server={FIXED_PROXY}')
        opts.add_argument(f'--user-agent={USER_AGENT}')
        
        # Cloudflare ve bot tespiti için ek kalkan
        opts.add_argument('--disable-blink-features=AutomationControlled')
        
        return uc.Chrome(options=opts, version_main=chrome_ver)

    def extract_source_url(self, url):
        try:
            logging.info(f"🔍 Bölüme giriliyor: {url}")
            self.driver.get(url)
            
            # Proxy hızı ve Angular yükleme süresi için sabırlı bekleme
            time.sleep(20) 
            
            wait = WebDriverWait(self.driver, 45)
            
            # ADIM 1: Fansub Kartını Tespit Et ve Tıkla
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            
            best_card, max_rating = None, -1.0
            for card in cards:
                try:
                    r_val = float(card.find_element(By.CLASS_NAME, "rating-value").text)
                    if r_val > max_rating: max_rating, best_card = r_val, card
                except: continue

            if best_card:
                logging.info(f"🏆 Fansub Seçildi: {max_rating}. Player (Deep-Scan) taranıyor...")
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(15) # Video tag'inin enjekte edilmesi için süre

                # ADIM 2: Derin Iframe ve Shadow DOM Taraması
                
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    try:
                        self.driver.switch_to.frame(frame)
                        # <source src="..."> etiketini ara
                        source_tag = self.driver.find_elements(By.TAG_NAME, "source")
                        if source_tag:
                            v_url = source_tag[0].get_attribute("src")
                            self.driver.switch_to.default_content()
                            return v_url
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue

                # Iframe dışında (ana sayfada) kontrol
                direct_src = self.driver.find_elements(By.CSS_SELECTOR, "video source, media-player source")
                if direct_src:
                    return direct_src[0].get_attribute("src")

        except Exception as e:
            logging.error(f"❌ Analiz Hatası: {e}")
        return None

    def secure_download(self, video_url, name, ep):
        filename = f"{name}_B{ep}.mp4"
        
        # KRİTİK: Sunucu bağlantısının kopmasını engelleyen headers ve proxy ayarları
        ydl_opts = {
            'outtmpl': filename,
            'quiet': False,
            'proxy': FIXED_PROXY,
            'nocheckcertificate': True,
            'format': 'best', # Daha stabil indirme için 'best' formatı
            'headers': {
                'User-Agent': USER_AGENT,
                'Referer': 'https://animecix.tv/', # Sunucu kimlik doğrulaması için şart
                'Accept': '*/*',
                'Connection': 'keep-alive',
            },
            'retries': 15, # Bağlantı koparsa 15 kez tekrar dene
            'fragment_retries': 15,
        }

        try:
            logging.info(f"🌪️ IDM Modu: Video sökülüyor -> {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            if os.path.exists(filename):
                # Hugging Face Aktarımı
                hf_path = f"{name}/{filename}"
                logging.info(f"📤 Bulut aktarımı başlatıldı: {hf_path}")
                self.api.upload_file(
                    path_or_fileobj=filename,
                    path_in_repo=hf_path,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
                
                # IPTV M3U Kaydı
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{name}_IPTV_Listen.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename) # Alan kazanmak için yereli temizle
                logging.info(f"✅ Bölüm {ep} başarıyla arşive eklendi!")
        except Exception as e:
            logging.error(f"💀 Sunucu bağlantıyı reddetti veya kesti: {e}")

    def run(self):
        if not ANIME_URL: return
        # Klasör ismini URL'den temizle
        try:
            folder_name = ANIME_URL.split('/titles/')[1].split('/')[1].replace('-', '_').title()
        except:
            folder_name = "Arsiv"

        for ep in range(START_EP, END_EP + 1):
            logging.info(f"\n--- 🚀 OPERASYON: {folder_name} - BÖLÜM {ep} ---")
            target_page = f"{ANIME_URL}{ep}"
            video_link = self.extract_source_url(target_page)
            
            if video_link:
                self.secure_download(video_link, folder_name, ep)
                time.sleep(5) # Sunucuyu uyandırmamak için kısa bir mola
            else:
                logging.warning(f"⏩ Bölüm {ep} pas geçildi (Link sökülemedi).")

        self.driver.quit()

if __name__ == "__main__":
    bot = AnimeBot()
    bot.run()
