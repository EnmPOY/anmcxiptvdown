import os, time, logging, subprocess
import yt_dlp
from seleniumwire import webdriver # Ağ trafiğini dinlemek için
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# SİSTEM YAPILANDIRMASI
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s | [%(levelname)s] | %(message)s')

# Sabitlenen Türk Proxy'si
PROXY_ADDR = "78.188.230.81:3310" 
HF_TOKEN = os.getenv("HF_TOKEN")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))

class IDMSnifferBot:
    def __init__(self):
        logging.info("🕵️ IDM Modu Hazır: Trafik dinleme başlatılıyor...")
        self.driver = self._init_driver()
        self.api = HfApi()

    def _init_driver(self):
        # Selenium-wire proxy ayarları
        sw_options = {
            'proxy': {
                'http': f'http://{PROXY_ADDR}',
                'https': f'http://{PROXY_ADDR}',
                'no_proxy': 'localhost,127.0.0.1'
            }
        }
        
        chrome_ver = None
        try:
            out = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_ver = int(out.split()[2].split('.')[0])
        except: pass

        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Tarayıcıyı Selenium-Wire ile başlat
        driver = webdriver.Chrome(
            seleniumwire_options=sw_options, 
            options=options,
            version_main=chrome_ver
        )
        return driver

    def sniff_video(self, url):
        try:
            logging.info(f"🌐 Sayfa taranıyor: {url}")
            del self.driver.requests # Önceki istekleri temizle
            self.driver.get(url)
            
            # Sayfanın ve Cloudflare engellerinin aşılması için bekleme
            time.sleep(15)
            
            # Fansub kartına basarak trafiği tetikle
            wait = WebDriverWait(self.driver, 40)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            
            if cards:
                logging.info("🖱️ Fansub kartına tıklandı, ağ trafiği koklanıyor...")
                self.driver.execute_script("arguments[0].click();", cards[0])
                time.sleep(15) # Video stream'inin başlaması için süre

            # AĞ TRAFİĞİNİ KONTROL ET (IDM Mantığı)
            for request in self.driver.requests:
                if request.response:
                    r_url = request.url.lower()
                    c_type = request.response.headers.get('Content-Type', '').lower()
                    
                    # Video dosyası içeren linkleri yakala
                    if '.mp4' in r_url or '.m3u8' in r_url or 'video/mp4' in c_type:
                        if "google" not in r_url and "analytics" not in r_url:
                            logging.info(f"🎯 Link Yakalandı: {request.url[:60]}...")
                            return request.url
        except Exception as e:
            logging.error(f"❌ Sniffing Hatası: {e}")
        return None

    def download_and_upload(self, link, name, ep):
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
            logging.info(f"🌪️ İndirme Başladı: {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            
            if os.path.exists(filename):
                # Hugging Face Aktarımı
                hf_path = f"{name}/{filename}"
                logging.info(f"📤 HF Aktarımı: {hf_path}")
                self.api.upload_file(
                    path_or_fileobj=filename, 
                    path_in_repo=hf_path, 
                    repo_id=REPO_ID, 
                    repo_type="dataset", 
                    token=HF_TOKEN
                )
                
                # M3U Playlist Güncelleme
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{name}_IPTV.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename)
                logging.info(f"✅ Görev Tamamlandı: {ep}")
        except Exception as e:
            logging.error(f"💀 İşleme Hatası: {e}")

    def start(self):
        if not ANIME_URL: return
        anime_name = ANIME_URL.split('/')[-5].replace('-', '_').title()
        
        for ep in range(START_EP, END_EP + 1):
            logging.info(f"\n--- 🎬 BÖLÜM {ep} OPERASYONU ---")
            video_url = self.sniff_video(f"{ANIME_URL}{ep}")
            
            if video_url:
                self.download_and_upload(video_url, anime_name, ep)
            else:
                logging.warning(f"⏩ Bölüm {ep} trafiği yakalanamadı.")
        
        self.driver.quit()

if __name__ == "__main__":
    bot = IDMSnifferBot()
    bot.start()
