import streamlit as st
import pandas as pd
import sqlite3
import re

# ─────────────────────────────────────────────
# 1. DATABASE
# ─────────────────────────────────────────────
conn = sqlite3.connect("monitoring_pabrik.db", check_same_thread=False)
cursor = conn.cursor()

def inisialisasi_db():
    cursor.execute("DROP TABLE IF EXISTS master_wh")
    cursor.execute("DROP TABLE IF EXISTS detail_subcon")
    cursor.execute("DROP TABLE IF EXISTS histori_subcon")
    cursor.execute("""CREATE TABLE master_wh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_no TEXT, nama_part TEXT, stok_wh REAL)""")
    cursor.execute("""CREATE TABLE detail_subcon (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_no TEXT, nama_part TEXT, nama_subcon TEXT,
        tipe_stok TEXT, jumlah_stok REAL)""")
    cursor.execute("""CREATE TABLE histori_subcon (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_no TEXT, nama_part TEXT, nama_subcon TEXT,
        jenis_transaksi TEXT, tanggal TEXT, qty REAL)""")
    conn.commit()

def bersihkan(teks):
    """Hapus _x000D_, newline, dan spasi berlebih."""
    if pd.isna(teks): return ""
    return re.sub(r'_x000D_|\r|\n', '', str(teks)).strip()

def to_num(val):
    v = pd.to_numeric(val, errors='coerce')
    return float(v) if pd.notna(v) else 0.0

# ─────────────────────────────────────────────
# 2. UI CONFIG - RESPONSIVE
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Monitoring Gudang & Subcon", 
    layout="wide",
    initial_sidebar_state="auto"
)

# CSS Responsive untuk Mobile & Desktop
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
    }
    
    /* Responsive Container */
    .block-container {
        padding: 1rem 0.8rem !important;
        max-width: 100% !important;
    }
    
    /* Card Styles */
    .card-master {
        background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3a 100%);
        border-left: 5px solid #FFCC00;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    
    .card-master:hover {
        transform: translateY(-2px);
    }
    
    /* Supplier Card */
    .supplier-card {
        background: #0d0d15;
        border: 1px solid #2a2a3a;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        transition: all 0.3s;
    }
    
    .supplier-card:hover {
        border-color: #FFCC00;
        box-shadow: 0 2px 8px rgba(255,204,0,0.1);
    }
    
    /* Responsive Tables - Mobile First */
    .responsive-table {
        width: 100%;
        border-collapse: collapse;
        margin: 0.5rem 0;
        font-size: 13px;
    }
    
    .responsive-table th {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: #FFCC00;
        padding: 10px 8px;
        border: 1px solid #333;
        text-align: center;
        font-weight: 600;
        font-size: 12px;
    }
    
    .responsive-table td {
        padding: 8px 6px;
        border: 1px solid #2a2a2a;
        color: #eee;
        font-size: 12px;
    }
    
    /* Mobile Optimization */
    @media (max-width: 768px) {
        .block-container {
            padding: 0.8rem 0.5rem !important;
        }
        
        .card-master {
            padding: 0.8rem;
            margin-bottom: 0.8rem;
        }
        
        .responsive-table {
            font-size: 11px;
        }
        
        .responsive-table th,
        .responsive-table td {
            padding: 6px 4px;
        }
        
        /* Stack tables on mobile */
        .supplier-card {
            padding: 0.8rem;
        }
        
        /* Reduce font sizes */
        h1 {
            font-size: 1.5rem !important;
        }
        
        h2, h3 {
            font-size: 1.2rem !important;
        }
        
        /* Better touch targets */
        button, .stButton button {
            min-height: 44px !important;
        }
        
        /* Improve input fields */
        input, textarea {
            font-size: 16px !important; /* Prevent zoom on focus */
        }
    }
    
    /* Desktop Optimization */
    @media (min-width: 1200px) {
        .block-container {
            padding: 2rem 2rem !important;
            max-width: 1400px !important;
            margin: 0 auto !important;
        }
        
        .responsive-table {
            font-size: 14px;
        }
        
        .responsive-table th,
        .responsive-table td {
            padding: 12px 16px;
        }
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: bold;
        margin: 2px;
    }
    
    .badge-success {
        background: rgba(0,210,106,0.2);
        color: #00D26A;
        border: 1px solid #00D26A;
    }
    
    .badge-warning {
        background: rgba(255,75,75,0.2);
        color: #FF6B6B;
        border: 1px solid #FF6B6B;
    }
    
    .badge-info {
        background: rgba(255,204,0,0.2);
        color: #FFCC00;
        border: 1px solid #FFCC00;
    }
    
    /* Search Box */
    .search-box {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1.5rem;
        border: 1px solid #2a2a3a;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1a1a1a;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #FFCC00;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #ffdb4d;
    }
    
    /* Loading Spinner */
    .stSpinner > div {
        border-top-color: #FFCC00 !important;
    }
    
    /* Success/Warning/Info Messages */
    .stAlert {
        border-radius: 10px !important;
        border-left: 4px solid #FFCC00 !important;
    }
</style>
""", unsafe_allow_html=True)

# Title dengan responsive design
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #FFCC00; margin-bottom: 0.5rem;">🏭 MONITORING GUDANG</h1>
            <h1 style="color: #FFCC00; margin-top: 0;">& SUBCON LOGISTIK</h1>
            <p style="color: #aaa; font-size: 14px;">Real-time Inventory Tracking System</p>
        </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. SIDEBAR — UPLOAD & SYNC (Enhanced)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem;">
            <h3 style="color: #FFCC00;">🔄 SISTEM SYNC</h3>
            <hr style="border-color: #2a2a3a;">
        </div>
    """, unsafe_allow_html=True)
    
    file_excel = st.file_uploader(
        "📂 Upload File Excel (.xlsx):", 
        type=["xlsx"],
        help="Upload file Excel dengan format yang sudah ditentukan"
    )
    
    if file_excel and st.button("⚡ SINKRONKAN DATA", use_container_width=True):
        with st.spinner("🔄 Memproses data..."):
            try:
                xls = pd.ExcelFile(file_excel)

                # ── Baca semua sheet ──
                df_wh     = pd.read_excel(xls, sheet_name="WH Inv",        header=5)
                df_subcon = pd.read_excel(xls, sheet_name="Subcon INV",    header=5)
                df_masuk  = pd.read_excel(xls, sheet_name="masuk subcon",  header=4)
                df_keluar = pd.read_excel(xls, sheet_name="keluar subcon", header=3)

                for df in [df_wh, df_subcon, df_masuk, df_keluar]:
                    df.columns = [str(c).strip() for c in df.columns]

                inisialisasi_db()

                # ══ A. WH INV ═══════════════════════════════════════════════
                wh_count = 0
                for _, r in df_wh.iterrows():
                    p_no  = bersihkan(r.get('Part No.', ''))
                    nama  = bersihkan(r.get('NAMA PART', ''))
                    if not p_no: continue
                    stok  = to_num(r.get('Stock Akhir', 0))
                    cursor.execute(
                        "INSERT INTO master_wh (part_no,nama_part,stok_wh) VALUES(?,?,?)",
                        (p_no.upper(), nama, stok))
                    wh_count += 1
                st.sidebar.success(f"✅ WH: {wh_count} items")

                # ══ B. SUBCON INV ════════════════════════════════════════════
                sub_count = 0
                for _, r in df_subcon.iterrows():
                    p_no_sub  = bersihkan(r.get('Part No. SubCon', ''))
                    if not p_no_sub: continue

                    nama_part = bersihkan(r.get('Part Name Subcon', ''))
                    sup_name  = bersihkan(r.get('Subcon Name', 'UNKNOWN'))
                    tipe      = bersihkan(r.get('Type', 'Regular'))
                    stok_akhir= to_num(r.get('Stock Akhir', 0))

                    cursor.execute("""
                        INSERT INTO detail_subcon
                            (part_no, nama_part, nama_subcon, tipe_stok, jumlah_stok)
                        VALUES (?,?,?,?,?)""",
                        (p_no_sub.upper(), nama_part, sup_name, tipe, stok_akhir))
                    sub_count += 1

                    for i in range(1, 32):
                        val_t = to_num(r.get(f'Terima{i}', 0))
                        val_k = to_num(r.get(f'Keluar{i}', 0))
                        if val_t > 0:
                            cursor.execute(
                                "INSERT INTO histori_subcon VALUES(NULL,?,?,?,?,?,?)",
                                (p_no_sub.upper(), nama_part, sup_name,
                                 "Terima dari Pabrik", f"Hari ke-{i}", val_t))
                        if val_k > 0:
                            cursor.execute(
                                "INSERT INTO histori_subcon VALUES(NULL,?,?,?,?,?,?)",
                                (p_no_sub.upper(), nama_part, sup_name,
                                 "Kirim ke Subcon", f"Hari ke-{i}", val_k))

                st.sidebar.success(f"✅ Subcon: {sub_count} items")

                # ══ C. MASUK SUBCON ══════════════════════════════════════════
                masuk_count = 0
                for _, r in df_masuk.iterrows():
                    p_no = bersihkan(r.get('Part No.', ''))
                    if not p_no: continue
                    sup  = bersihkan(r.get('Nama Supplier', 'UNKNOWN'))
                    nama = bersihkan(r.get('Nama Barang', ''))
                    tgl  = bersihkan(r.get('Tgl SJ', '-'))
                    qty  = to_num(r.get('Qty Masuk', 0))
                    if qty > 0:
                        cursor.execute(
                            "INSERT INTO histori_subcon VALUES(NULL,?,?,?,?,?,?)",
                            (p_no.upper(), nama, sup,
                             "Barang MASUK dari Subcon", str(tgl), qty))
                        masuk_count += 1
                st.sidebar.success(f"✅ Masuk: {masuk_count} transaksi")

                # ══ D. KELUAR SUBCON ═════════════════════════════════════════
                keluar_count = 0
                for _, r in df_keluar.iterrows():
                    p_no = bersihkan(r.get('Part No.', ''))
                    if not p_no: continue
                    sup  = bersihkan(r.get('Nama Supplier', 'UNKNOWN'))
                    nama = bersihkan(r.get('Nama Barang', ''))
                    tgl  = bersihkan(r.get('Tgl', '-'))
                    qty  = to_num(r.get('Qty', 0))
                    if qty > 0:
                        cursor.execute(
                            "INSERT INTO histori_subcon VALUES(NULL,?,?,?,?,?,?)",
                            (p_no.upper(), nama, sup,
                             "Barang KELUAR ke Subcon", str(tgl), qty))
                        keluar_count += 1
                st.sidebar.success(f"✅ Keluar: {keluar_count} transaksi")

                conn.commit()
                
                # Success Animation
                st.balloons()
                st.sidebar.success("🎉 Sinkronisasi Selesai!", icon="✅")

            except Exception as e:
                import traceback
                st.sidebar.error(f"❌ Error: {str(e)}", icon="🚨")
                with st.sidebar.expander("📋 Detail Error"):
                    st.code(traceback.format_exc())

    # Sidebar Info
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
        <div style="text-align: center; font-size: 12px; color: #666;">
            <p>📊 Real-time Monitoring System</p>
            <p>🔄 Last Sync: {}</p>
        </div>
    """.format(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")), unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 4. PENCARIAN (Enhanced)
# ─────────────────────────────────────────────
st.markdown('<div class="search-box">', unsafe_allow_html=True)
keyword = st.text_input(
    "🔍 CARI PART",
    placeholder="Contoh: STAY MIRROR atau 28STA",
    help="Masukkan nomor part atau nama part"
).upper().strip()
st.markdown('</div>', unsafe_allow_html=True)

if keyword:
    with st.spinner("🔍 Mencari data..."):
        df_hasil = pd.read_sql_query("""
            SELECT DISTINCT part_no, nama_part FROM master_wh
            WHERE (UPPER(part_no) LIKE ? OR UPPER(nama_part) LIKE ?)
              AND UPPER(nama_part) NOT LIKE '%BENDING%'
            UNION
            SELECT DISTINCT part_no, nama_part FROM detail_subcon
            WHERE (UPPER(part_no) LIKE ? OR UPPER(nama_part) LIKE ?)
              AND UPPER(nama_part) NOT LIKE '%BENDING%'
            ORDER BY part_no ASC
        """, conn, params=(f"%{keyword}%",)*4)

        if df_hasil.empty:
            st.warning(f"⚠️ '{keyword}' tidak ditemukan", icon="🔍")
        else:
            st.success(f"✅ Ditemukan {len(df_hasil)} item", icon="📦")
            
            for idx, row in df_hasil.iterrows():
                part_no   = row['part_no']
                nama_part = row['nama_part']

                # Custom expander dengan styling
                with st.expander(f"📦 {part_no} - {nama_part[:50]}", expanded=(idx==0)):
                    
                    # ── Stok WH ─────────────────────────────────────────
                    res_wh = pd.read_sql_query(
                        "SELECT SUM(stok_wh) as total FROM master_wh WHERE part_no=?",
                        conn, params=(part_no,))
                    stok_wh = res_wh.iloc[0]['total'] or 0

                    st.markdown(f"""
                    <div class="card-master">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <div>
                                <span style="color:#FFCC00; font-weight:bold; font-size:16px;">
                                    🏭 GUDANG UTAMA
                                </span><br>
                                <span style="color:#AAA; font-size:12px;">Part: <b>{part_no}</b></span>
                            </div>
                            <div style="text-align: right;">
                                <span class="badge badge-info">Stock WH</span>
                                <div style="font-size: 20px; font-weight: bold; color: #00D26A;">
                                    {stok_wh:,.0f} Pcs
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # ── Data Subcon ──────────────────────────────────────
                    df_sub = pd.read_sql_query("""
                        SELECT nama_subcon, tipe_stok, SUM(jumlah_stok) as stok,
                               part_no, nama_part
                        FROM detail_subcon
                        WHERE UPPER(part_no) = ?
                        GROUP BY nama_subcon, tipe_stok
                        ORDER BY nama_subcon, tipe_stok
                    """, conn, params=(part_no,))

                    if df_sub.empty:
                        kata2 = ' '.join(nama_part.split()[:2])
                        df_sub = pd.read_sql_query("""
                            SELECT nama_subcon, tipe_stok, SUM(jumlah_stok) as stok,
                                   part_no, nama_part
                            FROM detail_subcon
                            WHERE UPPER(nama_part) LIKE ?
                            GROUP BY nama_subcon, tipe_stok
                            ORDER BY nama_subcon, tipe_stok
                        """, conn, params=(f"%{kata2}%",))

                    if not df_sub.empty:
                        st.markdown("""
                            <div style="margin-top: 1rem;">
                                <span style="color:#FFCC00; font-weight:bold; font-size:15px;">
                                    🏢 DISTRIBUSI STOK SUBCON
                                </span>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        suppliers = df_sub['nama_subcon'].unique()
                        
                        # Responsive Table
                        rows_html = ""
                        for sup in suppliers:
                            df_s = df_sub[df_sub['nama_subcon'] == sup]
                            reg   = df_s[df_s['tipe_stok'].str.lower().str.contains('regular', na=False)]['stok'].sum()
                            klaim = df_s[df_s['tipe_stok'].str.lower().str.contains('klaim|claim', na=False)]['stok'].sum()
                            total = reg + klaim
                            
                            rows_html += f"""
                            <tr>
                                <td style="text-align:left; font-weight:bold;">📍 {sup}</td>
                                <td style="color:#00D26A; font-weight:bold;">{reg:,.0f}</td>
                                <td style="color:#FF6B6B; font-weight:bold;">{klaim:,.0f}</td>
                                <td style="color:#FFCC00; font-weight:bold;">{total:,.0f}</td>
                            </tr>
                            """
                        
                        st.markdown(f"""
                        <div style="overflow-x: auto;">
                            <table class="responsive-table">
                                <thead>
                                    <tr>
                                        <th style="text-align:left;">Supplier / Subcon</th>
                                        <th>Regular</th>
                                        <th>Klaim</th>
                                        <th>Total</th>
                                    </tr>
                                </thead>
                                <tbody>{rows_html}</tbody>
                            </table>
                        </div>
                        """, unsafe_allow_html=True)

                        # ── Detail per supplier ──────────────────────────────
                        st.markdown("<br><b style='color:#AAA;'>📋 Detail & Histori Supplier:</b>", unsafe_allow_html=True)
                        
                        for sup in suppliers:
                            df_s  = df_sub[df_sub['nama_subcon'] == sup]
                            reg   = df_s[df_s['tipe_stok'].str.lower().str.contains('regular', na=False)]['stok'].sum()
                            klaim = df_s[df_s['tipe_stok'].str.lower().str.contains('klaim|claim', na=False)]['stok'].sum()
                            total = reg + klaim
                            
                            # Card collapsible untuk setiap supplier
                            with st.expander(f"🏭 {sup}"):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("📦 Stok Regular", f"{reg:,.0f} Pcs", delta=None)
                                with col2:
                                    st.metric("⚠️ Stok Klaim", f"{klaim:,.0f} Pcs", delta=None)
                                with col3:
                                    st.metric("📊 Total Stok", f"{total:,.0f} Pcs", delta=None)
                                
                                # Histori
                                df_hist = pd.read_sql_query("""
                                    SELECT jenis_transaksi, tanggal, qty
                                    FROM histori_subcon
                                    WHERE UPPER(part_no)=? AND nama_subcon=?
                                    ORDER BY tanggal ASC
                                """, conn, params=(part_no, sup))
                                
                                if not df_hist.empty:
                                    st.markdown("**📜 Riwayat Transaksi:**")
                                    for _, h in df_hist.iterrows():
                                        jenis = str(h['jenis_transaksi'])
                                        if 'MASUK' in jenis.upper() or 'TERIMA' in jenis.upper():
                                            st.success(f"⬇️ {jenis} - {h['tanggal']}: {h['qty']:,.0f} Pcs")
                                        else:
                                            st.error(f"⬆️ {jenis} - {h['tanggal']}: {h['qty']:,.0f} Pcs")
                                else:
                                    st.info("Tidak ada histori mutasi")
                    else:
                        st.info("ℹ️ Item ini hanya tersedia di WH internal")
                        
else:
    # Welcome Screen
    st.markdown("""
        <div style="text-align: center; padding: 3rem 1rem;">
            <div style="font-size: 64px;">🔍</div>
            <h3 style="color: #FFCC00;">Mulai Monitoring</h3>
            <p style="color: #aaa;">Masukkan nomor part atau nama part di atas untuk melihat data stok</p>
            <div class="badge badge-info">💡 Tips: Gunakan kata kunci seperti "28STA" atau "STAY MIRROR"</div>
        </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 11px; padding: 1rem;">
        <p>🏭 Monitoring Gudang & Subcon Logistics System v2.0</p>
        <p>© 2024 - Real-time Inventory Tracking</p>
    </div>
""", unsafe_allow_html=True)
