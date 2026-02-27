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
# 2. AYARLAR (Config)
# ---------------------------------------------------------
FIXED_PROXY = "http://78.188.230.81:3310" 
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

class NarutoArsivBot:
    def __init__(self):
        logging.info("🕵️ Bot başlatılıyor. 'Deep-Scan' ve Proxy aktif...")
        self.driver = self._init_driver()
        self.api = HfApi()

    def _init_driver(self):
        chrome_ver = None
        try:
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
        opts.add_argument('--disable-blink-features=AutomationControlled')
        
        return uc.Chrome(options=opts, version_main=chrome_ver)

    def extract_link_v4(self, url):
        try:
            logging.info(f"🔍 Bölüm Analiz Ediliyor: {url}")
            self.driver.get(url)
            time.sleep(15) 

            wait = WebDriverWait(self.driver, 45)
            # Fansub Kartını Bekle
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "translator-card")))
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_r = None, -1.0
            for card in cards:
                try:
                    val = float(card.find_element(By.CLASS_NAME, "rating-value").text)
                    if val > max_r: max_r, best_card = val, card
                except: continue

            if best_card:
                logging.info(f"🏆 Fansub Seçildi ({max_r}). Player katmanı sökülüyor...")
                self.driver.execute_script("arguments[0].click();", best_card)
                
                # Player'ın ve media-player bileşenlerinin gelmesi için bekle
                time.sleep(18) 
                
                # Tüm iframeleri tek tek ve derinlemesine tara
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                logging.info(f"📦 {len(iframes)} adet iframe (kapsül) bulundu, taranıyor...")

                for frame in iframes:
                    try:
                        self.driver.switch_to.frame(frame)
                        # Senin paylaştığın o meşhur <source> etiketini ara
                        # Birden fazla yol deniyoruz
                        sources = self.driver.find_elements(By.CSS_SELECTOR, "source[src*='.mp4'], video source, media-player source")
                        if sources:
                            video_url = sources[0].get_attribute("src")
                            if video_url:
                                logging.info(f"🎯 Mp4 Linki Yakalandı: {video_url[:60]}...")
                                self.driver.switch_to.default_content()
                                return video_url
                        
                        # Alternatif: Video tag'i içinde ara
                        videos = self.driver.find_elements(By.TAG_NAME, "video")
                        if videos and videos[0].get_attribute("src"):
                            v_url = videos[0].get_attribute("src")
                            self.driver.switch_to.default_content()
                            return v_url
                            
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue

                # Iframe dışında (ana DOM'da) doğrudan media-player kontrolü
                logging.info("🔎 Iframe dışında derin arama yapılıyor...")
                direct = self.driver.find_elements(By.CSS_SELECTOR, "media-player source, app-embed2 source")
                if direct:
                    return direct[0].get_attribute("src")

        except Exception as e:
            logging.error(f"❌ Analiz Hatası: {e}")
        return None

    def secure_download(self, link, name, ep):
        filename = f"{name}_B{ep}.mp4"
        ydl_opts = {
            'outtmpl': filename,
            'quiet': False,
            'proxy': FIXED_PROXY,
            'format': 'best',
            'headers': {
                'User-Agent': USER_AGENT,
                'Referer': 'https://animecix.tv/',
                'Accept': '*/*',
            },
            'retries': 10,
            'fragment_retries': 10,
        }

        try:
            logging.info(f"🌪️ İndirme Başladı: {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            
            if os.path.exists(filename):
                hf_path = f"{name}/{filename}"
                self.api.upload_file(
                    path_or_fileobj=filename,
                    path_in_repo=hf_path,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
                
                # M3U Playlist Kaydı
                raw = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                with open(f"{name}_IPTV.m3u", "a", encoding="utf-8") as f:
                    if os.path.getsize(f"{name}_IPTV.m3u") == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {name} - Bolum {ep}\n{raw}\n")
                
                os.remove(filename)
                logging.info(f"✅ Başarılı: {ep}")
        except Exception as e:
            logging.error(f"💀 İndirme Hatası: {e}")

    def run(self):
        if not ANIME_URL: return
        anime_folder = ANIME_URL.split('/titles/')[1].split('/')[1].replace('-', '_').title()
        
        for ep in range(START_EP, END_EP + 1):
            logging.info(f"\n--- 🎬 OPERASYON: {anime_folder} - BÖLÜM {ep} ---")
            mp4_link = self.extract_link_v4(f"{ANIME_URL}{ep}")
            if mp4_link:
                self.secure_download(mp4_link, anime_folder, ep)
            else:
                logging.warning(f"⏩ Bölüm {ep} atlanıyor (Kaynak sökülemedi).")
        
        self.driver.quit()

if __name__ == "__main__":
    bot = NarutoArsivBot()
    bot.run()
