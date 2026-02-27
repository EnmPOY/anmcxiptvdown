import os, time, glob, logging, subprocess
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# SİSTEM YAPILANDIRMASI
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s | [%(levelname)s] | %(message)s')

# Senin paylaştığın özel veriler
FIXED_PROXY = "http://78.188.230.81:3310" 
HF_TOKEN = os.getenv("HF_TOKEN", "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")
REPO_ID = "Enmpoy/allmoviesornimetr"
ANIME_URL = os.getenv("ANIME_URL")
START_EP = int(os.getenv("START_EP", 1))
END_EP = int(os.getenv("END_EP", 1))



class EnmxyBot:
    def __init__(self):
        logging.info("🕵️ Bot hazırlanıyor. Proxy ve Sürüm Kontrolü aktif...")
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
        
        # Otomasyon izlerini gizle (Cloudflare bariyeri için)
        opts.add_argument('--disable-blink-features=AutomationControlled')
        
        return uc.Chrome(options=opts, version_main=chrome_ver)

    def extract_idm_link(self, url):
        try:
            logging.info(f"🔍 Hedefe sızılıyor: {url}")
            self.driver.get(url)
            
            # Angular (SPA) ve Proxy yükleme süresi için sabırlı bekleme
            time.sleep(20) 
            
            wait = WebDriverWait(self.driver, 45)
            
            # 1. ADIM: En yüksek puanlı fansub'ı bul ve tıkla
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
                logging.info(f"🏆 Fansub Seçildi: {max_rating}. Player deşifre ediliyor...")
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(15) # Player'ın ve source tag'inin gelmesi için bekle

                # 2. ADIM: <source src="..."> etiketini "Sniff" et (Iframe içi tarama dahil)
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    try:
                        self.driver.switch_to.frame(frame)
                        source_tag = self.driver.find_elements(By.TAG_NAME, "source")
                        if source_tag:
                            video_url = source_tag[0].get_attribute("src")
                            self.driver.switch_to.default_content()
                            return video_url
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue

                # Iframe dışında ara
                source_tag = self.driver.find_elements(By.TAG_NAME, "source")
                if source_tag:
                    return source_tag[0].get_attribute("src")

        except Exception as e:
            logging.error(f"❌ Analiz Hatası: {e}")
        return None

    def fast_download_and_upload(self, video_link, name, ep):
        filename = f"{name}_B{ep}.mp4"
        # yt-dlp'yi IDM gibi hızlı indirmesi için yapılandırıyoruz
        ydl_opts = {
            'outtmpl': filename,
            'quiet': False,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'proxy': FIXED_PROXY,
            'nocheckcertificate': True,
            'headers': {'Referer': 'https://animecix.tv/'}
        }

        try:
            logging.info(f"🌪️ IDM Modu: Video hortumlanıyor -> {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_link])
            
            if os.path.exists(filename):
                # Hugging Face Aktarımı
                hf_path = f"{name}/{filename}"
                self.api.upload_file(
                    path_or_fileobj=filename,
                    path_in_repo=hf_path,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
                
                # M3U Playlist Güncelleme (Resolve linki ile)
                raw_url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hf_path}"
                m3u_file = f"{name}_Playlist.m3u"
                with open(m3u_file, "a", encoding="utf-8") as f:
                    if os.path.getsize(m3u_file) == 0: f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, {name} - Bolum {ep}\n{raw_url}\n")
                
                os.remove(filename)
                logging.info(f"✅ Bölüm {ep} operasyonu başarıyla tamamlandı.")
        except Exception as e:
            logging.error(f"💀 Operasyon Patladı: {e}")

    def run(self):
        if not ANIME_URL: return
        anime_folder = ANIME_URL.split('/')[-5].replace('-', '_').title()
        
        for ep in range(START_EP, END_EP + 1):
            logging.info(f"\n--- 🎬 OPERASYON: BÖLÜM {ep} ---")
            video_url = self.extract_idm_link(f"{ANIME_URL}{ep}")
            
            if video_url:
                self.fast_download_and_upload(video_url, anime_folder, ep)
            else:
                logging.warning(f"⏩ Bölüm {ep} pas geçildi (Kaynak sökülemedi).")
        
        self.driver.quit()

if __name__ == "__main__":
    bot = EnmxyBot()
    bot.run()
