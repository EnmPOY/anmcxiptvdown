import os, time, logging, subprocess
import yt_dlp
# BURASI KRİTİK: Her iki kütüphaneyi birleştiren modülü çağırıyoruz
import seleniumwire.undetected_chromedriver as uc 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# 1. LOGLAMA VE YAPILANDIRMA
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.StreamHandler()]
)

# Senin verdiğin Türk Proxy ve Token bilgileri
PROXY_ADDR = "78.188.230.81:3310" 
HF_TOKEN = os.getenv("HF_TOKEN")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

class SnifferMaster:
    def __init__(self):
        logging.info("🕵️ IDM Modu Yayında: Trafik koklama ve UC-Bypass modülü yüklendi...")
        self.api = HfApi()
        self.driver = self._init_driver()

    def _init_driver(self):
        # Selenium-wire için ağ dinleme ve proxy ayarları
        sw_options = {
            'proxy': {
                'http': f'http://{PROXY_ADDR}',
                'https': f'http://{PROXY_ADDR}',
                'no_proxy': 'localhost,127.0.0.1'
            },
            'verify_ssl': False
        }
        
        chrome_ver = None
        try:
            # GitHub sunucusundaki Chrome sürümünü tespit et
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
            logging.info(f"🌐 Sunucu Chrome Sürümü: {chrome_ver}")
        except: pass

        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        # Hata veren kısım buradaydı; artık UC tabanlı driver başlatıyoruz
        driver = uc.Chrome(
            options=options,
            seleniumwire_options=sw_options,
            version_main=chrome_ver
        )
        return driver

    def sniff_video(self, url):
        try:
            logging.info(f"🌐 Sayfa taranıyor: {url}")
            del self.driver.requests # Önceki tüm ağ isteklerini temizle
            self.driver.get(url)
            
            # Cloudflare ve sayfa yüklemesi için sabırlı bekleme
            time.sleep(20)
            
            # Fansub kartına basarak video trafiğini tetikleyelim (IDM gibi)
            wait = WebDriverWait(self.driver, 45)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            
            if cards:
                logging.info("🖱️ Fansub kartına basıldı, arka plan trafiği inceleniyor...")
                self.driver.execute_script("arguments[0].click();", cards[0])
                time.sleep(20) # Videonun yüklenip akması için süre

            # AĞ TRAFİĞİNİ KOKLA (IDM MANTIĞI)
            
            logging.info("📡 Yakalanan paketler deşifre ediliyor...")
            for request in self.driver.requests:
                if request.response:
                    req_url = request.url.lower()
                    c_type = request.response.headers.get('Content-Type', '').lower()
                    
                    # Video stream veya dosya linklerini yakala
                    if ('.mp4' in req_url or '.m3u8' in req_url or 'video/mp4' in c_type):
                        # Reklam ve istatistik servislerini ele
                        if not any(x in req_url for x in ["google", "analytics", "doubleclick", "facebook"]):
                            logging.info(f"🎯 Hedef Link Yakalandı: {request.url[:60]}...")
                            return request.url
        except Exception as e:
            logging.error(f"❌ Sniffing sırasında hata: {e}")
        return None

    def process_mission(self, video_url, name, ep):
        filename = f"{name}_B{ep}.mp4"
        ydl_opts = {
            'outtmpl': filename,
            'quiet': False,
            'proxy': f'http://{PROXY_ADDR}',
            'format': 'best',
            'nocheckcertificate': True,
            'headers': {
                'Referer': 'https://animecix.tv/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
        }
        
        try:
            logging.info(f"🌪️ Video sökülüyor: {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            if os.path.exists(filename):
                # Hugging Face Aktarımı
                hf_path = f"{name}/{filename}"
                logging.info(f"📤 Bulut Aktarımı: {hf_path}")
                self.api.upload_file(
                    path_or_fileobj=filename, 
                    path_in_repo=hf_path, 
                    repo_id=REPO_ID, 
                    repo_type="dataset", 
                    token=HF_TOKEN
                )
                
                # IPTV M3U Güncelleme (Resolve linki ile)
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{name}_Playlist.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename)
                logging.info(f"✅ Bölüm {ep} operasyonu tamam!")
        except Exception as e:
            logging.error(f"💀 Medya İşleme Patladı: {e}")

    def run(self):
        if not ANIME_URL: return
        # Anime ismini temizle
        anime_title = ANIME_URL.split('/')[-5].replace('-', '_').title()
        
        for ep in range(START_EP, END_EP + 1):
            logging.info(f"\n--- 🚀 OPERASYON: {anime_title} - BÖLÜM {ep} ---")
            found_link = self.sniff_video(f"{ANIME_URL}{ep}")
            
            if found_link:
                self.process_mission(found_link, anime_title, ep)
                time.sleep(5) # Sunucuyu dinlendir
            else:
                logging.warning(f"⏩ Bölüm {ep} trafiği koklanamadı.")
        
        self.driver.quit()

if __name__ == "__main__":
    bot = SnifferMaster()
    bot.run()
