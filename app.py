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
# 2. UI CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Monitoring Gudang & Subcon", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.2rem!important}
.card-master{background:#1A1A1A;border-left:5px solid #FFCC00;padding:15px;border-radius:6px;margin-bottom:12px}
.supplier-table{width:100%;border-collapse:collapse;margin-top:10px}
.supplier-table th{background:#1a1a2e;color:#FFCC00;padding:10px 14px;border:1px solid #333;text-align:center}
.supplier-table td{padding:9px 14px;border:1px solid #2a2a2a;color:#eee}
.supplier-table tr:hover td{background:#1e1e1e}
.hist-table{width:100%;border-collapse:collapse;margin-top:8px}
.hist-table th{background:#222;color:#FFCC00;padding:8px;border:1px solid #333;text-align:center;font-size:12px}
.hist-table td{padding:8px;border:1px solid #333;text-align:center;color:white;font-size:12px}
</style>
""", unsafe_allow_html=True)

st.title("🏭 MONITORING GUDANG & SUBCON LOGISTIK")

# ─────────────────────────────────────────────
# 3. SIDEBAR — UPLOAD & SYNC
# ─────────────────────────────────────────────
st.sidebar.header("🔄 Sinkronisasi Sistem")
file_excel = st.sidebar.file_uploader("Upload File Excel (.xlsx):", type=["xlsx"])

if file_excel and st.sidebar.button("⚡ SINKRONKAN DATA SEKARANG"):
    with st.spinner("Memproses data..."):
        try:
            xls = pd.ExcelFile(file_excel)

            # ── Baca semua sheet dengan header yang sudah terkonfirmasi ──
            df_wh     = pd.read_excel(xls, sheet_name="WH Inv",        header=5)
            df_subcon = pd.read_excel(xls, sheet_name="Subcon INV",    header=5)
            df_masuk  = pd.read_excel(xls, sheet_name="masuk subcon",  header=4)
            df_keluar = pd.read_excel(xls, sheet_name="keluar subcon", header=3)

            # strip nama kolom
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
            st.sidebar.success(f"✅ WH Inv: {wh_count} baris")

            # ══ B. SUBCON INV ════════════════════════════════════════════
            # Kolom pasti: Subcon Name | Part No. SubCon | Part Name Subcon
            #              Type | Stock Akhir | Terima1..Terima31 | Keluar1..Keluar31
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

                # mutasi harian
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

            st.sidebar.success(f"✅ Subcon INV: {sub_count} baris")

            # ══ C. MASUK SUBCON ══════════════════════════════════════════
            # Kolom: Tgl SJ | Nama Supplier | Kategori | Nama Barang | Part No. | Qty Masuk
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
            st.sidebar.success(f"✅ Masuk Subcon: {masuk_count} transaksi")

            # ══ D. KELUAR SUBCON ═════════════════════════════════════════
            # Kolom: Tgl | Nama Supplier | Kategori | Nama Barang | Part No. | Qty
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
            st.sidebar.success(f"✅ Keluar Subcon: {keluar_count} transaksi")

            conn.commit()
            st.sidebar.success("🎉 Sinkronisasi selesai!")

        except Exception as e:
            import traceback
            st.sidebar.error(f"❌ Error: {e}")
            st.sidebar.code(traceback.format_exc())

# ─────────────────────────────────────────────
# 4. PENCARIAN
# ─────────────────────────────────────────────
keyword = st.text_input(
    "🔍 CARI BERDASARKAN NAMA PART ATAU NOMOR PART (Contoh: STAY MIRROR / 28STA):"
).upper().strip()

if keyword:
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
        st.warning(f"Kata kunci '{keyword}' tidak ditemukan di database.")
    else:
        st.write("### 📌 Pilih Item Hasil Temuan:")

        for _, row in df_hasil.iterrows():
            part_no   = row['part_no']
            nama_part = row['nama_part']

            with st.expander(f"⚙️ [{part_no}] - {nama_part}"):

                # ── Stok WH ─────────────────────────────────────────
                res_wh = pd.read_sql_query(
                    "SELECT SUM(stok_wh) as total FROM master_wh WHERE part_no=?",
                    conn, params=(part_no,))
                stok_wh = res_wh.iloc[0]['total'] or 0

                st.markdown(f"""
                <div class="card-master">
                  <span style="color:#FFCC00;font-weight:bold;font-size:17px;">
                    🏭 GUDANG UTAMA MATERIAL (AFTER PROCESS)
                  </span><br>
                  <span style="color:#AAA;font-size:13px;">Nomor Part Kode: <b>{part_no}</b></span><br>
                  <span style="font-size:15px;">
                    Sisa Saldo Stock Akhir WH:
                    <b style="color:#00D26A;">{stok_wh:,.2f} Pcs</b>
                  </span>
                </div>""", unsafe_allow_html=True)

                # ── Data Subcon ──────────────────────────────────────
                # Query: cocokkan exact part_no ATAU part_no subcon yang mirip
                df_sub = pd.read_sql_query("""
                    SELECT nama_subcon, tipe_stok, SUM(jumlah_stok) as stok,
                           part_no, nama_part
                    FROM detail_subcon
                    WHERE UPPER(part_no) = ?
                    GROUP BY nama_subcon, tipe_stok
                    ORDER BY nama_subcon, tipe_stok
                """, conn, params=(part_no,))

                # Jika tidak ada, coba match by nama_part (2 kata pertama)
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
                    suppliers = df_sub['nama_subcon'].unique()

                    # ── Tabel ringkasan ──────────────────────────────
                    rows_html = ""
                    for sup in suppliers:
                        df_s = df_sub[df_sub['nama_subcon'] == sup]
                        reg   = df_s[df_s['tipe_stok'].str.lower().str.contains('regular', na=False)]['stok'].sum()
                        klaim = df_s[df_s['tipe_stok'].str.lower().str.contains('klaim|claim', na=False)]['stok'].sum()
                        total = reg + klaim
                        cr = "#00D26A" if reg   > 0 else "#666"
                        ck = "#FF4B4B" if klaim > 0 else "#666"
                        ct = "#FFCC00" if total > 0 else "#666"
                        rows_html += f"""
                        <tr>
                          <td style="text-align:left;font-weight:bold;">📍 {sup}</td>
                          <td style="color:{cr};font-weight:bold;">{reg:,.0f}</td>
                          <td style="color:{ck};font-weight:bold;">{klaim:,.0f}</td>
                          <td style="color:{ct};font-weight:bold;">{total:,.0f}</td>
                        </tr>"""

                    st.markdown(f"""
                    <b style="color:#FFCC00;font-size:15px;">
                      🏢 Distribusi Stok di Supplier Subcon:
                    </b>
                    <table class="supplier-table">
                      <thead><tr>
                        <th style="text-align:left;">Nama Supplier / Subcon</th>
                        <th>Stok Regular (Pcs)</th>
                        <th>Stok Klaim (Pcs)</th>
                        <th>Total (Pcs)</th>
                      </tr></thead>
                      <tbody>{rows_html}</tbody>
                    </table>
                    """, unsafe_allow_html=True)

                    # ── Detail + Histori per supplier ────────────────
                    st.markdown("<br><b style='color:#AAA;'>📋 Detail Histori Per Supplier:</b>",
                                unsafe_allow_html=True)

                    for sup in suppliers:
                        df_s = df_sub[df_sub['nama_subcon'] == sup]
                        reg   = df_s[df_s['tipe_stok'].str.lower().str.contains('regular', na=False)]['stok'].sum()
                        klaim = df_s[df_s['tipe_stok'].str.lower().str.contains('klaim|claim', na=False)]['stok'].sum()
                        pno_s  = df_s.iloc[0]['part_no']
                        nama_s = df_s.iloc[0]['nama_part']

                        st.markdown(f"""
                        <div style="background:#111;border:1px solid #333;padding:12px;
                                    border-radius:6px;margin-top:8px;">
                          <b style="color:#FFF;">📍 {sup}</b><br>
                          <span style="color:#AAA;font-size:12px;">
                            Part No: <span style="color:#FFCC00;">{pno_s}</span>
                            &nbsp;|&nbsp; {nama_s}
                          </span><br><br>
                          <span style="color:#00D26A;font-weight:bold;">● Regular</span>
                          : <b style="color:#00D26A;font-size:15px;">{reg:,.0f} Pcs</b>
                          &nbsp;&nbsp;&nbsp;
                          <span style="color:#FF4B4B;font-weight:bold;">● Klaim</span>
                          : <b style="color:#FF4B4B;font-size:15px;">{klaim:,.0f} Pcs</b>
                        </div>""", unsafe_allow_html=True)

                        df_hist = pd.read_sql_query("""
                            SELECT jenis_transaksi, tanggal, qty
                            FROM histori_subcon
                            WHERE UPPER(part_no)=? AND nama_subcon=?
                            ORDER BY tanggal ASC
                        """, conn, params=(part_no, sup))

                        if not df_hist.empty:
                            hist_rows = "".join(
                                f"<tr><td>{h['jenis_transaksi']}</td>"
                                f"<td>{h['tanggal']}</td>"
                                f"<td style='color:#00D26A;font-weight:bold;'>"
                                f"{h['qty']:,.0f}</td></tr>"
                                for _, h in df_hist.iterrows())
                            st.markdown(f"""
                            <table class="hist-table">
                              <thead><tr>
                                <th>Aktivitas</th><th>Tanggal / Hari</th><th>Qty (Pcs)</th>
                              </tr></thead>
                              <tbody>{hist_rows}</tbody>
                            </table>""", unsafe_allow_html=True)
                        else:
                            st.caption("Tidak ada histori mutasi untuk supplier ini.")
                else:
                    st.info("Item part ini murni berada di WH internal, tidak tersebar di supplier subcon.")
else:
    st.info("💡 Masukkan nama part atau nomor part untuk mulai monitoring.")