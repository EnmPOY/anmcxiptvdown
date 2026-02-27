import os
import time
import glob
import urllib.parse
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
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
    """
    İndirilen videoyu acımasızca Hugging Face'e şutlar ve M3U için saf (raw) linki kopartır alır.
    """
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
        
        # Linkin bozulmaması için boşlukları vs. encode ediyoruz
        hedef_yol_kodlu = urllib.parse.quote(hedef_yol)
        hf_raw_link = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{hedef_yol_kodlu}"
        return hf_raw_link
    except Exception as e:
        print(f"{Renk.KIRMIZI}[-] Hasiktir, yükleme sırasında sistem patladı: {e}{Renk.SIFIRLA}")
        return None

def m3u_txt_kaydet_ve_yukle(anime_adi, sezon, bolum, raw_link):
    """
    Videoyu buluta attıktan sonra linkini oynatma listesine zımbalar ve listeyi de buluta yedekler.
    """
    dosya_adi = "enmpoy_iptv_listesi.txt"
    ilk_mi = not os.path.exists(dosya_adi)
    
    with open(dosya_adi, "a", encoding="utf-8") as f:
        if ilk_mi:
            f.write("#EXTM3U\n") # Oynatma listesinin kalbi
        f.write(f"#EXTINF:-1, {anime_adi} - S{sezon:02d} E{bolum:02d}\n")
        f.write(f"{raw_link}\n")
    
    print(f"{Renk.YESIL}[+] {anime_adi} S{sezon} E{bolum} M3U listesine çakıldı!{Renk.SIFIRLA}")
    
    # Listeyi de buluta fırlatıyoruz ki sunucu reset atarsa uçup gitmesin
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
    print(f"{Renk.YESIL}[*] G63'ÜN 7/24 ANİME SÖMÜRÜCÜSÜ AKTİF! (STEALTH + PROXY ZIRHI){Renk.SIFIRLA}")
    print(f"{Renk.YESIL}===================================================={Renk.SIFIRLA}\n")

    with sync_playwright() as p:
        # Anti-bot argümanları (Sistemi hızlandırmak ve iz bırakmamak için tasarlandı)
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
            
            # --- PROXY VE STEALTH ENJEKSİYONU ---
            # Site seni GitHub botu değil, o proxy'yi kullanan sıradan bir Türk sanacak!
            try:
                baglam = tarayici.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    proxy={
                        "server": "http://176.88.166.211:8080" # Hedefi şaşırtan o zehirli TR IP'si
                    }
                )
            except Exception as e:
                print(f"{Renk.KIRMIZI}[-] Proxy bağlanırken patladı, sonraki bölüme geçiliyor: {e}{Renk.SIFIRLA}")
                continue

            sayfa = baglam.new_page()
            stealth_sync(sayfa) # Tarayıcıya hayalet modunu yükle

            # Ağ trafiğini koklayıp saf video linkini enseleyen ajan fonksiyon
            def ag_dinleyici(response):
                nonlocal gercek_video_linki
                url = response.url
                if (".m3u8" in url or ".mp4" in url) and "master" not in url.lower():
                    if not gercek_video_linki:
                        gercek_video_linki = url
                        print(f"{Renk.YESIL}    [+] Ajanlar ham video linkini havada kaptı!{Renk.SIFIRLA}")

            try:
                # Proxy'ler bazen kanser edercesine yavaş olur, o yüzden timeout süresi 90 saniye! Direnecek!
                print(f"{Renk.SARI}    [*] Proxy üzerinden hedefe sızılıyor (Bekle amk, proxy yavaş olabilir)...{Renk.SIFIRLA}")
                sayfa.goto(hedef_url, timeout=90000)
                sayfa.wait_for_selector('.translator-card', timeout=30000)
                
                fansub_kartlari = sayfa.query_selector_all('.translator-card')
                if not fansub_kartlari:
                    print(f"{Renk.KIRMIZI}    [-] Fansub bulunamadı, bu bölüm boş veya sayfa yüklenemedi.{Renk.SIFIRLA}")
                    continue
                
                # FARK ETMEZ MODU: Kim çevirmiş umrumuzda değil, ilkine çöküyoruz!
                secilen_kart = fansub_kartlari[0]
                secilen_kart.click()
                print(f"{Renk.SARI}    [*] İlk fansuba acımadan tıklandı, player açılıyor...{Renk.SIFIRLA}")
                
                sayfa.wait_for_selector('iframe', timeout=20000)
                
                # Player iframe'ini bulup izole ve stealth bir sekmede açıyoruz ki asıl videoyu kussun
                for cerceve in sayfa.query_selector_all('iframe'):
                    src = cerceve.get_attribute('src')
                    if src and "http" in src:
                        player_sayfasi = baglam.new_page()
                        stealth_sync(player_sayfasi)
                        player_sayfasi.on("response", ag_dinleyici)
                        player_sayfasi.goto(src, timeout=90000)
                        player_sayfasi.wait_for_timeout(10000) # Videonun patlaması için yeterli süre
                        player_sayfasi.close()
                        break
                        
            except Exception as hata:
                print(f"{Renk.KIRMIZI}    [-] Proxy bağlantısında veya siteyi sömürürken yara aldık: {hata}{Renk.SIFIRLA}")
            finally:
                baglam.close() # Her bölümde sekme hafızasını tertemiz yapıp RAM'i rahatlatıyoruz

            # --- İNDİRME VE YÜKLEME AŞAMASI ---
            if gercek_video_linki:
                # İstediğin o kusursuz isimlendirme: {anime adı}-{sezon}-{bölüm}.mp4
                dosya_formati = f"{anime_adi}-{sezon}-{bolum_no}.%(ext)s"
                ydl_ayarlari = {'format': 'best', 'outtmpl': dosya_formati, 'noplaylist': True, 'quiet': True}
                
                try:
                    print(f"{Renk.YESIL}    [*] yt-dlp ölüm kusuyor! Video diske iniyor...{Renk.SIFIRLA}")
                    with yt_dlp.YoutubeDL(ydl_ayarlari) as ydl:
                        ydl.download([gercek_video_linki])
                    
                    inen_dosyalar = glob.glob(f"{anime_adi}-{sezon}-{bolum_no}.*")
                    if inen_dosyalar:
                        tam_dosya_yolu = inen_dosyalar[0]
                        
                        # Önce buluta at, sonra linkini al
                        hf_direkt_link = hf_yukle_ve_link_al(tam_dosya_yolu, anime_adi)
                        
                        if hf_direkt_link:
                            # M3U formatına yaz ve txt'yi yedekle
                            m3u_txt_kaydet_ve_yukle(anime_adi, sezon, bolum_no, hf_direkt_link)
                            
                            # İşimizi bitirdik, GitHub sunucusunda yer kaplamasın diye kalıntıları yok et!
                            os.remove(tam_dosya_yolu)
                            print(f"{Renk.SARI}    [*] İndirme başarılı, yerel kalıntılar acımasızca silindi.{Renk.SIFIRLA}")
                except Exception as e:
                    print(f"{Renk.KIRMIZI}    [-] yt-dlp patladı amk: {e}{Renk.SIFIRLA}")
            else:
                 print(f"{Renk.KIRMIZI}    [-] Ağ trafiğinde link bulunamadı.{Renk.SIFIRLA}")
            
            # Anti-ban esnemesi, site nefes alsın diye bekle
            time.sleep(3) 

if __name__ == "__main__":
    # URL şablonu (süslü parantezleri elleme, kod oraları dolduracak)
    sablon = "https://animecix.tv/titles/80/naruto/season/{sezon}/episode/{bolum}"
    
    # Hangi animeyi, hangi sezonu ve hangi bölümleri sömürmek istiyorsan buraya yaz!
    anigexis_olum_makinesi(
        url_sablonu=sablon, 
        anime_adi="Naruto", 
        sezon=1, 
        baslangic=1, 
        bitis=220
    )
