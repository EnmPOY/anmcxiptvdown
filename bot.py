import os, time, glob, logging
import yt_dlp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from huggingface_hub import HfApi

# ---------------------------------------------------------
# 1. LOGLAMA SİSTEMİ (Sistemin Gözü Kulağı)
# ---------------------------------------------------------
# Terminale ve 'arsiv_sistemi.log' dosyasına her adımı yazar.
# Böylece gece uyurken bot ne yapmış, sabah kalkıp okuyabilirsin.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s] | %(message)s',
    handlers=[logging.FileHandler("arsiv_sistemi.log", encoding="utf-8"), logging.StreamHandler()]
)

# ---------------------------------------------------------
# 2. YAPILANDIRMA MODÜLÜ (Kontrol Paneli)
# ---------------------------------------------------------
class Config:
    HF_TOKEN = "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" # Hugging Face Anahtarın
    REPO_ID = "Enmpoy/allmoviesornimetr" # Hedef Veritabanı
    
    # 🎯 VURULACAK HEDEFLER
    # Buraya 50 tane anime ekle, sen okula git, o hepsini IPTV'ne çeksin.
    TARGETS = [
        {
            "name": "Jujutsu_Kaisen", 
            "base_url": "https://animecix.tv/titles/7352/jujutsu-kaisen/season/1/episode/", 
            "start": 1, 
            "end": 24
        },
        {
            "name": "Naruto", 
            "base_url": "https://animecix.tv/titles/80/naruto/season/1/episode/", 
            "start": 1, 
            "end": 220
        },
         {
            "name": "Naruto-Shippuden", 
            "base_url": "https://animecix.tv/titles/7490/naruto-shippuuden/season/1/episode/", 
            "start": 1, 
            "end": 500
        },
        # {"name": "Demon_Slayer", "base_url": "...", "start": 1, "end": 26}
    ]

# ---------------------------------------------------------
# 3. HAYALET TARAYICI MODÜLÜ
# ---------------------------------------------------------
class StealthBrowser:
    @staticmethod
    def initialize():
        logging.info("🕵️ Hayalet tarayıcı başlatılıyor (Cloudflare Kalkanı Devrede)...")
        opts = uc.ChromeOptions()
        opts.add_argument('--headless') # Sunucuda görünmez çalışır
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage') # RAM şişmesini engeller
        opts.add_argument('--mute-audio')
        return uc.Chrome(options=opts)

# ---------------------------------------------------------
# 4. SİTE PARÇALAYICI MODÜL (Kazıma Motoru)
# ---------------------------------------------------------
class SiteAnalyzer:
    def __init__(self, driver):
        self.driver = driver

    def extract_premium_iframe(self, target_url):
        try:
            self.driver.get(target_url)
            # Sayfanın tam yüklenmesini akıllıca bekle (15 saniyeye kadar)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "translator-card"))
            )
            
            cards = self.driver.find_elements(By.CLASS_NAME, "translator-card")
            best_card, max_rating = None, -1.0
            
            # Kalite Taraması
            for card in cards:
                try:
                    r_val = float(card.find_element(By.CLASS_NAME, "rating-value").text)
                    if r_val > max_rating:
                        max_rating = r_val
                        best_card = card
                except: continue

            if best_card:
                logging.info(f"🏆 En yüksek puanlı çeviri seçiliyor: {max_rating}")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_card)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", best_card)
                time.sleep(5) # Player iframe'inin DOM'a düşmesini bekle
                
                # Iframe Avı
                for frame in self.driver.find_elements(By.TAG_NAME, "iframe"):
                    src = frame.get_attribute("src")
                    if src and any(domain in src for domain in ["vidmoly", "sibnet", "ok.ru"]):
                        logging.info(f"🔗 Kaynak başarıyla deşifre edildi: {src.split('/')[2]}")
                        return src
        except Exception as e:
            logging.error(f"❌ Analiz sırasında hata: {str(e)[:50]}...")
        return None

# ---------------------------------------------------------
# 5. İNDİRME MOTORU
# ---------------------------------------------------------
class Downloader:
    @staticmethod
    def pull_video(iframe_url, anime_name, ep_num):
        filename = f"{anime_name}_Bolum_{ep_num}.mp4"
        ydl_opts = {
            'outtmpl': filename, 
            'quiet': True, 
            'no_warnings': True, 
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' # Kesinlikle en iyi kaliteyi zorla
        }
        try:
            logging.info(f"🌪️ yt-dlp ile indirme başlatıldı: {filename}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([iframe_url])
            return filename
        except Exception as e:
            logging.error(f"💀 İndirme motoru çöktü: {e}")
            return None

# ---------------------------------------------------------
# 6. HUGGING FACE & IPTV (M3U) YÖNETİCİSİ
# ---------------------------------------------------------
class CloudAndPlaylistManager:
    def __init__(self):
        self.api = HfApi()

    def process_and_upload(self, local_file, anime_name, ep_num):
        hf_path = f"{anime_name}/{local_file}" # Klasörleme sistemi
        
        try:
            logging.info(f"📤 Hugging Face Veritabanına aktarılıyor: {hf_path}")
            self.api.upload_file(
                path_or_fileobj=local_file,
                path_in_repo=hf_path,
                repo_id=Config.REPO_ID,
                repo_type="dataset",
                token=Config.HF_TOKEN
            )
            os.remove(local_file) # Diski temiz tut
            
            # Raw Link Oluşturma Formülü
            raw_url = f"https://huggingface.co/datasets/{Config.REPO_ID}/resolve/main/{hf_path}"
            m3u_file = f"{anime_name}_IPTV_Listesi.m3u"
            
            # M3U Formatında Yazma
            with open(m3u_file, "a", encoding="utf-8") as f:
                if os.path.getsize(m3u_file) == 0:
                    f.write("#EXTM3U\n")
                f.write(f"#EXTINF:-1, {anime_name} - Bölüm {ep_num}\n")
                f.write(f"{raw_url}\n")
                
            logging.info(f"✅ İşlem Tamam! {m3u_file} güncellendi.")
            
        except Exception as e:
            logging.error(f"☁️ Bulut aktarımında hata: {e}")

# ---------------------------------------------------------
# 7. ANA ORKESTRATÖR (Ölümsüz Döngü)
# ---------------------------------------------------------
class Orchestrator:
    def run_forever(self):
        cloud_mgr = CloudAndPlaylistManager()
        
        while True:
            driver = None
            try:
                logging.info("🚀 YENİ TARAMA DÖNGÜSÜ BAŞLIYOR...")
                driver = StealthBrowser.initialize()
                analyzer = SiteAnalyzer(driver)
                
                for target in Config.TARGETS:
                    name = target["name"]
                    for ep in range(target["start"], target["end"] + 1):
                        url = f"{target['base_url']}{ep}"
                        logging.info(f"\n[{name} | BÖLÜM {ep}]")
                        
                        iframe = analyzer.extract_premium_iframe(url)
                        if not iframe: 
                            logging.warning("⚠️ Kaynak yok, diğer bölüme geçiliyor.")
                            continue
                            
                        Downloader.pull_video(iframe, name, ep)
                        
                        # Esnek dosya bulucu (Uzun indirmelerde bazen .mkv inebilir)
                        files = glob.glob(f"{name}_Bolum_{ep}.*")
                        if files:
                            cloud_mgr.process_and_upload(files[0], name, ep)
                            
                logging.info("💤 Görev listesi temizlendi. Kod 2 saat uyku moduna geçiyor.")
                if driver: driver.quit()
                time.sleep(7200) # 2 Saat bekle, yeni bölüm gelmiş mi diye tekrar bak
                
            except Exception as e:
                logging.critical(f"💥 SİSTEMSEL ÇÖKME TESPİT EDİLDİ: {e}")
                logging.critical("🔄 Panik yok, bellek temizlenip 3 dakika içinde yeniden başlatılacak...")
                if driver: 
                    try: driver.quit()
                    except: pass
                time.sleep(180)

# ---------------------------------------------------------
# ATEŞLEME
# ---------------------------------------------------------
if __name__ == "__main__":
    bot = Orchestrator()
    bot.run_forever()