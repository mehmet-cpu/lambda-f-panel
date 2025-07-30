import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

if not firebase_admin._apps:
    secrets_dict = st.secrets["firebase_key"]
    firebase_creds_copy = dict(secrets_dict)
    firebase_creds_copy['private_key'] = firebase_creds_copy['private_key'].replace('\\n', '\n')
    cred = credentials.Certificate(firebase_creds_copy)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Veri Çekme Fonksiyonu (GÜNCELLENDİ) ---
@st.cache_data(ttl=600) # Veriyi 10 dakika cache'le
def fetch_lambdaF_history():
    docs = db.collection("lambdaF").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(30).stream()
    
    data = []
    for doc in docs:
        doc_data = doc.to_dict()
        # source_scores'un varlığını kontrol et, yoksa boş bir dict ata
        scores = doc_data.get("source_scores", {})
        
        data.append({
            "timestamp": doc_data.get("timestamp"),
            "lambda_F": doc_data.get("lambda_F"),
            "fearAndGreed": scores.get("fearAndGreed"),
            "redditHype": scores.get("redditHype"),
            "volumeSpike": scores.get("volumeSpike")
        })
    
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.dropna(subset=['timestamp']) # Timestamp'i olmayanları kaldır
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by="timestamp", ascending=True) # Grafiğin doğru çizilmesi için yeniden sırala
    return df

# --- Dashboard Arayüzü ---
st.set_page_config(layout="wide", page_title="Lambda-F Risk Göstergesi")

st.title("λF Gerçek Zamanlı Piyasa Güvensizlik Göstergesi")
st.markdown("Piyasalardaki kolektif hissiyatı ve 'hype'ı ölçerek kriz veya balon gibi faz geçişlerini öngörmeyi hedefler.")

df_history = fetch_lambdaF_history()

if df_history.empty:
    st.warning("Firestore'dan veri çekilemedi veya henüz veri mevcut değil.")
else:
    # En son veriyi al
    latest_data = df_history.iloc[-1]
    lambda_F = latest_data["lambda_F"]

    # --- 1. ANA GÖSTERGE VE BİLEŞENLERİ (YENİ) ---
    st.markdown("---")
    
    # Ana Lambda-F Değeri
    st.header(f"Güncel λF Değeri: `{lambda_F:.3f}`")
    if lambda_F > 0.7:
        st.error("🚨 KRİTİK BÖLGE: Sosyal ve piyasa çalkantısı çok yüksek. Aşırı ısınma riski.")
    elif lambda_F > 0.5:
        st.warning("⚠️ RİSKLİ BÖLGE: Belirsizlik ve dalgalanma riski artıyor.")
    else:
        st.success("✅ NORMAL SEVİYE: Piyasa sakin görünüyor.")

    st.subheader("λF Bileşen Skorları (0-100)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label=" Genel Piyasa Hissiyatı",
            value=f"{latest_data['fearAndGreed']:.0f}",
            help="Korku ve Açgözlülük Endeksi. Düşük değerler korkuyu, yüksek değerler açgözlülüğü gösterir."
        )
    with col2:
        st.metric(
            label="💬 Sosyal Medya Hype'ı",
            value=f"{latest_data['redditHype']:.0f}",
            help="Reddit'teki anahtar kelime sayısına dayalı sosyal coşku seviyesi."
        )
    with col3:
        st.metric(
            label="📈 Piyasa Aktivitesi",
            value=f"{latest_data['volumeSpike']:.0f}",
            help="İşlem hacmindeki ani artışları ölçen skor."
        )

    # --- 2. ZAMAN SERİSİ GRAFİĞİ (YENİ - KATMANLI ALAN GRAFİĞİ) ---
    st.markdown("---")
    st.subheader("📊 λF'nin Zaman İçindeki Değişimi ve Bileşenlerin Katkısı")

    # Ağırlıklı katkıları hesapla
    df_history['fng_contrib'] = (df_history['fearAndGreed'] / 100) * 0.4
    df_history['reddit_contrib'] = (df_history['redditHype'] / 100) * 0.3
    df_history['volume_contrib'] = (df_history['volumeSpike'] / 100) * 0.3
    
    # Grafiği çiz
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Katmanlı alan grafiği
    ax.stackplot(
        df_history['timestamp'],
        df_history['fng_contrib'],
        df_history['reddit_contrib'],
        df_history['volume_contrib'],
        labels=['Piyasa Hissiyatı (%40)', 'Sosyal Hype (%30)', 'Piyasa Aktivitesi (%30)'],
        alpha=0.7
    )
    
    # Toplam Lambda-F çizgisini de ekleyelim
    ax.plot(df_history['timestamp'], df_history['lambda_F'], color='black', linewidth=2, linestyle='--', label='Toplam λF Değeri')

    # Kritik eşikleri çiz
    ax.axhline(y=0.5, color='darkorange', linestyle='--', label='⚠️ Risk Eşiği (0.5)')
    ax.axhline(y=0.7, color='red', linestyle='--', label='🚨 Kritik Eşik (0.7)')
    
    # Stil ve etiketler
    ax.set_title("λF Bileşenlerinin Zaman Serisi Katkısı", fontsize=16)
    ax.set_xlabel("Tarih")
    ax.set_ylabel("λF Değeri ve Katkısı")
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, max(1.0, df_history['lambda_F'].max() * 1.1)) # Y-eksenini 1'e veya en yüksek değerin biraz üstüne ayarla

    # Streamlit’e çizdir
    st.pyplot(fig)

    # --- 3. HAM VERİ GÖRÜNÜMÜ ---
    st.markdown("---")
    with st.expander("Son 30 Günlük Ham Veriyi Görüntüle"):
        st.dataframe(df_history)
