# Gerekli kütüphaneleri içe aktaralım
import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# Sayfa Yapılandırması (En başta ve sadece bir kez çağrılır)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="λF Risk Gösterge Paneli",
    page_icon="🔺",
    layout="centered",  # 'centered' daha odaklı bir görünüm sunar, 'wide' da tercih edilebilir.
    initial_sidebar_state="auto"
)

# -----------------------------------------------------------------------------
# Firebase Bağlantısı (Streamlit'in cache mekanizması ile)
# -----------------------------------------------------------------------------

if not firebase_admin._apps:
    secrets_dict = st.secrets["firebase_key"]
    firebase_creds_copy = dict(secrets_dict)
    firebase_creds_copy['private_key'] = firebase_creds_copy['private_key'].replace('\\n', '\n')
    cred = credentials.Certificate(firebase_creds_copy)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -----------------------------------------------------------------------------
# Veri Çekme Fonksiyonu
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)  # Veriyi 10 dakika (600 saniye) boyunca cache'le
def fetch_lambda_f_data(_db_client):
    """
    Firestore'dan Lambda-F verilerini çeker, DataFrame'e dönüştürür ve sıralar.
    _db_client parametresi, cache'in ne zaman yenileneceğini bilmesine yardımcı olur.
    """
    if _db_client is None:
        return pd.DataFrame() # Boş DataFrame döndür
        
    try:
        docs = _db_client.collection("lambdaF").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(30).stream()
        
        data = []
        for doc in docs:
            doc_data = doc.to_dict()
            data.append({
                "timestamp": doc_data.get("timestamp"),
                "lambda_F": doc_data.get("lambda_F"),
                "status": doc_data.get("status", "N/A")
            })
        
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.dropna(subset=['timestamp', 'lambda_F'])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)
        return df

    except Exception as e:
        st.error(f"Veri çekilirken bir hata oluştu: {e}")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# Görselleştirme Fonksiyonları
# -----------------------------------------------------------------------------
def create_time_series_chart(df):
    """
    Verilen DataFrame ile interaktif bir zaman serisi grafiği oluşturur.
    """
    if df.empty:
        return None

    fig = px.line(
        df,
        x='timestamp',
        y='lambda_F',
        title="Lambda-F Skorunun Zaman İçindeki Değişimi",
        labels={'timestamp': 'Tarih', 'lambda_F': 'λF Skoru'},
        markers=True
    )

    # Grafik stili ve eşik çizgileri
    fig.update_layout(
        xaxis_title="Zaman",
        yaxis_title="λF Skoru",
        yaxis_range=[0, 1],
        template="plotly_white", # Daha temiz bir görünüm için
        title_x=0.5 # Başlığı ortala
    )
    
    # Eşik çizgileri
    fig.add_hline(y=0.7, line_dash="dot", line_color="red", annotation_text="🚨 Kritik Seviye (0.7)", annotation_position="bottom right")
    fig.add_hline(y=0.5, line_dash="dot", line_color="orange", annotation_text="⚠️ Risk Seviyesi (0.5)", annotation_position="bottom right")

    return fig

# -----------------------------------------------------------------------------
# Ana Dashboard Arayüzü
# -----------------------------------------------------------------------------

# --- Başlık ---
st.title("🔺 λF Risk Gösterge Paneli")
st.caption(f"Flux Finance | Veriler en son {datetime.now().strftime('%Y-%m-%d %H:%M')} tarihinde güncellendi.")

# --- Veri Çekme ---
df_history = fetch_lambda_f_data(db)

# --- Ana Metrikler ---
if not df_history.empty:
    # En son veriyi al
    latest_data = df_history.iloc[-1]
    lambda_f_current = latest_data['lambda_F']
    status_current = latest_data['status']

    # Bir önceki veriyi al (varsa)
    lambda_f_previous = df_history.iloc[-2]['lambda_F'] if len(df_history) > 1 else 0
    delta = lambda_f_current - lambda_f_previous

    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            label="Mevcut λF Skoru",
            value=f"{lambda_f_current:.3f}",
            delta=f"{delta:.3f} (önceki güne göre)",
            delta_color="inverse" # Pozitif değişim kırmızı (kötü), negatif değişim yeşil (iyi)
        )
    
    with col2:
        # Duruma göre renkli ve ikonlu bir metin gösterimi
        if status_current == "Kritik":
            st.error(f"**Durum: {status_current}** 🚨")
        elif status_current == "Riskli":
            st.warning(f"**Durum: {status_current}** ⚠️")
        else:
            st.success(f"**Durum: {status_current}** ✅")
    st.markdown("---")

else:
    st.warning("Henüz görüntülenecek geçmiş veri bulunmamaktadır. Lütfen simülasyonun veri ürettiğinden emin olun.")


# --- Sekmeli İçerik Alanı ---
tab1, tab2 = st.tabs(["📈 Zaman Serisi Grafiği", "📄 Veri Tablosu"])

with tab1:
    st.subheader("λF Skorlarının İnteraktif Grafiği")
    
    # Grafik oluşturma ve gösterme
    time_series_chart = create_time_series_chart(df_history)
    if time_series_chart:
        st.plotly_chart(time_series_chart, use_container_width=True)
    else:
        st.info("Grafiği çizmek için yeterli veri bulunamadı.")

with tab2:
    st.subheader("Geçmiş λF Verileri (En son 30 kayıt)")
    
    if not df_history.empty:
        # DataFrame'i daha okunaklı gösterme
        st.dataframe(
            df_history.sort_values(by="timestamp", ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Görüntülenecek veri tablosu bulunamadı.")


# --- Kenar Çubuğu (Sidebar) ---
st.sidebar.header("λF Modeli Hakkında")
st.sidebar.info(
    """
    **Lambda-F (λF)**, sosyal medyadaki kolektif duygu değişimlerini analiz ederek 
    finansal piyasalardaki potansiyel istikrarsızlıkları ve 'faz geçişlerini' 
    (ani çöküşler veya aşırı ısınmalar) öngörmeyi amaçlayan bir risk göstergesidir.
    
    - **0.0 - 0.5 (Normal ✅):** Piyasa sakin.
    - **0.5 - 0.7 (Riskli ⚠️):** Belirsizlik ve volatilite artıyor.
    - **0.7 - 1.0 (Kritik 🚨):** Sosyal gerilim yüksek, ani ve büyük fiyat hareketleri riski artmış durumda.
    """
)
st.sidebar.markdown("---")
if st.sidebar.button('Veriyi Yenile 🔄'):
    st.cache_data.clear()
    st.rerun()
