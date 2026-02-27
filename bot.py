import os
import time
import glob
import urllib.parse
from playwright.sync_api import sync_playwright
import yt_dlp
from huggingface_hub import HfApi

# Terminal ekranını hacker filmine çevirecek renk kodları
class Renk:
    YESIL = '\033[92m'
    SARI = '\033[93m'
    KIRMIZI = '\033[91m'
    MAVI = '\033[94m'
    SIFIRLA = '\033[0m'

# Masaya vurduğun token ve devasa hedefin
HF_TOKEN = "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"
REPO_ID = "Enmpoy/allmoviesornimetr"

def hf_yukle_ve_link_al(dosya_yolu, anime_adi):
    api = HfApi()
    dosya_adi = os.path.basename(dosya_yolu)
    hedef_yol = f"{anime_adi}/{dosya_adi}"
    
    print(f"{Renk.MAVI}[*] Buluta, Enmpoy krallığına ateşleniyor: {dosya_adi}...{Renk.SIFIRLA}")
    try:
        api.upload_file(
            path_or_fileobj=dosya_yolu,
            path_in_repo=hedef_yol,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"{Renk.YESIL}[+] Yükleme kusursuz! Video bulutta güvende.{Renk.SIFIRLA}")
        
        hedef_yol_kodlu = urllib.parse.quote(hedef_yol)
        hf_raw_link = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hedef_yol_kodlu}"
        return hf_raw_link
    except Exception as e:
        print(f"{Renk.KIRMIZI}[-] Hasiktir, yükleme sırasında sistem patladı: {e}{Renk.SIFIRLA}")
        return None

def m3u_txt_kaydet_ve_yukle(anime_adi, sezon, bolum, raw_link):
    dosya_adi = "enmpoy_iptv_listesi.txt"
    ilk_mi = not os.path.exists(dosya_adi)
    
    with open(dosya_adi, "a", encoding="utf-8") as f:
        if ilk_mi:
            f.write("#EXTM3U\n") 
        f.write(f"#EXTINF:-1, {anime_adi} - S{sezon:02d} E{bolum:02d}\n")
        f.write(f"{raw_link}\n")
    
    print(f"{Renk.YESIL}[+] {anime_adi} S{sezon} E{bolum} M3U listesine çakıldı!{Renk.SIFIRLA}")
    
    api = HfApi()
    try:
        api.upload_file(
            path_or_fileobj=dosya_adi,
            path_in_repo=dosya_adi,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"{Renk.SARI}[*] Güncel IPTV listesi buluta senkronize edildi.{Renk.SIFIRLA}")
    except Exception as e:
        print(f"{Renk.KIRMIZI}[-] Liste senkronize edilirken bokluk çıktı: {e}{Renk.SIFIRLA}")

def anigexis_olum_makinesi(url_sablonu, anime_adi, sezon, baslangic, bitis):
    print(f"\n{Renk.YESIL}===================================================={Renk.SIFIRLA}")
    print(f"{Renk.YESIL}[*] G63'ÜN 7/24 ANİME SÖMÜRÜCÜSÜ AKTİF! (SAF JAVASCRIPT STEALTH + PROXY){Renk.SIFIRLA}")
    print(f"{Renk.YESIL}===================================================={Renk.SIFIRLA}\n")

    with sync_playwright() as p:
        tarayici = p.chromium.launch(
            headless=True, 
            args=[
                '--disable-gpu', 
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox', 
                '--disable-dev-shm-usage'
            ]
        )
        
        for bolum_no in range(baslangic, bitis + 1):
            hedef_url = url_sablonu.format(sezon=sezon, bolum=bolum_no)
            print(f"\n{Renk.MAVI}[>>>] İŞLENİYOR: {anime_adi} | Sezon: {sezon} | Bölüm: {bolum_no}{Renk.SIFIRLA}")
            gercek_video_linki = None
            
            try:
                baglam = tarayici.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    proxy={
                        "server": "http://176.88.166.211:8080"
                    }
                )
            except Exception as e:
                print(f"{Renk.KIRMIZI}[-] Proxy bağlanırken patladı: {e}{Renk.SIFIRLA}")
                continue

            sayfa = baglam.new_page()
            
            # --- YENİ STEALTH ENJEKSİYONU ---
            # O dış kütüphaneyi attık, yerine doğrudan tarayıcının webdriver kimliğini silen bu scripti koyduk!
            sayfa.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            def ag_dinleyici(response):
                nonlocal gercek_video_linki
                url = response.url
                if (".m3u8" in url or ".mp4" in url) and "master" not in url.lower():
                    if not gercek_video_linki:
                        gercek_video_linki = url
                        print(f"{Renk.YESIL}    [+] Ajanlar ham video linkini havada kaptı!{Renk.SIFIRLA}")

            try:
                print(f"{Renk.SARI}    [*] Proxy üzerinden hedefe sızılıyor...{Renk.SIFIRLA}")
                sayfa.goto(hedef_url, timeout=90000)
                sayfa.wait_for_selector('.translator-card', timeout=30000)
                
                fansub_kartlari = sayfa.query_selector_all('.translator-card')
                if not fansub_kartlari:
                    print(f"{Renk.KIRMIZI}    [-] Fansub bulunamadı, bu bölüm boş veya sayfa yüklenemedi.{Renk.SIFIRLA}")
                    continue
                
                secilen_kart = fansub_kartlari[0]
                secilen_kart.click()
                print(f"{Renk.SARI}    [*] İlk fansuba acımadan tıklandı, player açılıyor...{Renk.SIFIRLA}")
                
                sayfa.wait_for_selector('iframe', timeout=20000)
                
                for cerceve in sayfa.query_selector_all('iframe'):
                    src = cerceve.get_attribute('src')
                    if src and "http" in src:
                        player_sayfasi = baglam.new_page()
                        # Yeni sekmeye de aynı hayalet kodu enjekte ediyoruz
                        player_sayfasi.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                        player_sayfasi.on("response", ag_dinleyici)
                        player_sayfasi.goto(src, timeout=90000)
                        player_sayfasi.wait_for_timeout(10000)
                        player_sayfasi.close()
                        break
                        
            except Exception as hata:
                print(f"{Renk.KIRMIZI}    [-] Proxy bağlantısında veya siteyi sömürürken yara aldık: {hata}{Renk.SIFIRLA}")
            finally:
                baglam.close()

            if gercek_video_linki:
                dosya_formati = f"{anime_adi}-{sezon}-{bolum_no}.%(ext)s"
                ydl_ayarlari = {'format': 'best', 'outtmpl': dosya_formati, 'noplaylist': True, 'quiet': True}
                
                try:
                    print(f"{Renk.YESIL}    [*] yt-dlp ölüm kusuyor! Video diske iniyor...{Renk.SIFIRLA}")
                    with yt_dlp.YoutubeDL(ydl_ayarlari) as ydl:
                        ydl.download([gercek_video_linki])
                    
                    inen_dosyalar = glob.glob(f"{anime_adi}-{sezon}-{bolum_no}.*")
                    if inen_dosyalar:
                        tam_dosya_yolu = inen_dosyalar[0]
                        
                        hf_direkt_link = hf_yukle_ve_link_al(tam_dosya_yolu, anime_adi)
                        
                        if hf_direkt_link:
                            m3u_txt_kaydet_ve_yukle(anime_adi, sezon, bolum_no, hf_direkt_link)
                            os.remove(tam_dosya_yolu)
                            print(f"{Renk.SARI}    [*] İndirme başarılı, yerel kalıntılar acımasızca silindi.{Renk.SIFIRLA}")
                except Exception as e:
                    print(f"{Renk.KIRMIZI}    [-] yt-dlp patladı amk: {e}{Renk.SIFIRLA}")
            else:
                 print(f"{Renk.KIRMIZI}    [-] Ağ trafiğinde link bulunamadı.{Renk.SIFIRLA}")
            
            time.sleep(3) 

if __name__ == "__main__":
    sablon = "https://animecix.tv/titles/80/naruto/season/{sezon}/episode/{bolum}"
    anigexis_olum_makinesi(url_sablonu=sablon, anime_adi="Naruto", sezon=1, baslangic=1, bitis=220)
