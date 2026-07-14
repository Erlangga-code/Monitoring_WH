import streamlit as st
import pandas as pd
import sqlite3
import re
from io import BytesIO
from datetime import datetime

# ─────────────────────────────────────────────
# 1. DATABASE
# ─────────────────────────────────────────────
conn = sqlite3.connect("monitoring_pabrik.db", check_same_thread=False)
cursor = conn.cursor()


def pastikan_tabel_sync_info():
    """Tabel info sinkronisasi terakhir - tidak ikut ter-drop saat re-sync."""
    cursor.execute("""CREATE TABLE IF NOT EXISTS sync_info (
        id INTEGER PRIMARY KEY,
        file_name TEXT, waktu TEXT,
        wh_count INTEGER, sub_count INTEGER,
        masuk_count INTEGER, keluar_count INTEGER)""")
    conn.commit()


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


def simpan_info_sync(file_name, wh, sub, masuk, keluar):
    cursor.execute("DELETE FROM sync_info")
    cursor.execute("""INSERT INTO sync_info
        (id, file_name, waktu, wh_count, sub_count, masuk_count, keluar_count)
        VALUES (1,?,?,?,?,?,?)""",
        (file_name, datetime.now().strftime("%d-%m-%Y %H:%M:%S"), wh, sub, masuk, keluar))
    conn.commit()


def ambil_info_sync():
    try:
        df = pd.read_sql_query("SELECT * FROM sync_info", conn)
        if not df.empty:
            return df.iloc[0]
    except Exception:
        pass
    return None


def bersihkan(teks):
    """Hapus _x000D_, newline, dan spasi berlebih."""
    if pd.isna(teks):
        return ""
    return re.sub(r'_x000D_|\r|\n', '', str(teks)).strip()


def to_num(val):
    v = pd.to_numeric(val, errors='coerce')
    return float(v) if pd.notna(v) else 0.0


def to_excel_bytes(dfs: dict):
    """dfs: dict {nama_sheet: dataframe} -> bytes file excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for nama_sheet, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=nama_sheet[:31])
    return output.getvalue()


def status_stok(total, threshold):
    """Mengembalikan (label, warna) berdasarkan jumlah stok & ambang batas."""
    if total <= 0:
        return "🔴 STOK KOSONG", "#FF4B4B"
    elif total < threshold:
        return "🟡 STOK MENIPIS", "#FFCC00"
    else:
        return "🟢 STOK AMAN", "#00D26A"


pastikan_tabel_sync_info()

# ─────────────────────────────────────────────
# 2. UI CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Monitoring Gudang & Subcon",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* ====== UMUM / RESPONSIVE ====== */
.block-container{
    padding-top: 1rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px;
}
h1 { font-size: 1.6rem !important; }
h3 { font-size: 1.15rem !important; }

/* Kartu ringkasan stok WH */
.card-master{
    background:#1A1A1A;border-left:5px solid #FFCC00;
    padding:14px 16px;border-radius:8px;margin-bottom:12px;
}
.card-master .judul{color:#FFCC00;font-weight:bold;font-size:16px;}
.card-master .sub{color:#AAA;font-size:12px;}
.card-master .nilai{font-size:15px;}
.card-master .nilai b{color:#00D26A;}

/* Badge status stok */
.status-badge{
    display:inline-block;padding:4px 12px;border-radius:20px;
    font-weight:bold;font-size:12px;margin-left:8px;
    border:1px solid currentColor;
}

/* Wrapper agar tabel HTML bisa di-scroll horizontal di HP */
.table-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch; width:100%; }

.supplier-table{width:100%;border-collapse:collapse;margin-top:10px;min-width:480px;}
.supplier-table th{background:#1a1a2e;color:#FFCC00;padding:8px 10px;border:1px solid #333;text-align:center;font-size:13px;}
.supplier-table td{padding:8px 10px;border:1px solid #2a2a2a;color:#eee;font-size:13px;}
.supplier-table tr:hover td{background:#1e1e1e}

.hist-table{width:100%;border-collapse:collapse;margin-top:8px;min-width:420px;}
.hist-table th{background:#222;color:#FFCC00;padding:8px;border:1px solid #333;text-align:center;font-size:12px}
.hist-table td{padding:8px;border:1px solid #333;text-align:center;color:white;font-size:12px}

/* Chip pencarian terakhir */
.search-chip{
    display:inline-block;background:#1a1a2e;color:#FFCC00;
    border:1px solid #333;border-radius:14px;padding:3px 10px;
    margin:2px;font-size:12px;
}

/* Mobile tweaks */
@media (max-width: 768px){
    .block-container{padding-left:0.6rem !important;padding-right:0.6rem !important;}
    h1{font-size:1.25rem !important;}
    .card-master .judul{font-size:14px;}
    .card-master .nilai{font-size:13px;}
}
</style>
""", unsafe_allow_html=True)

st.title("🏭 MONITORING GUDANG & SUBCON LOGISTIK")

info_sync = ambil_info_sync()
if info_sync is not None:
    st.caption(
        f"🕒 Sinkronisasi terakhir: **{info_sync['waktu']}** "
        f"dari file `{info_sync['file_name']}` &nbsp;|&nbsp; "
        f"WH: {int(info_sync['wh_count'])} baris · "
        f"Subcon: {int(info_sync['sub_count'])} baris · "
        f"Masuk: {int(info_sync['masuk_count'])} trx · "
        f"Keluar: {int(info_sync['keluar_count'])} trx"
    )
else:
    st.caption("⚠️ Belum ada data tersinkronisasi. Silakan upload file Excel melalui menu di sidebar (☰).")

# ─────────────────────────────────────────────
# 3. SIDEBAR — UPLOAD, SYNC, & SETTING
# ─────────────────────────────────────────────
st.sidebar.header("🔄 Sinkronisasi Sistem")
file_excel = st.sidebar.file_uploader("Upload File Excel (.xlsx):", type=["xlsx"])

if file_excel and st.sidebar.button("⚡ SINKRONKAN DATA SEKARANG", use_container_width=True):
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
                if not p_no:
                    continue
                stok  = to_num(r.get('Stock Akhir', 0))
                cursor.execute(
                    "INSERT INTO master_wh (part_no,nama_part,stok_wh) VALUES(?,?,?)",
                    (p_no.upper(), nama, stok))
                wh_count += 1
            st.sidebar.success(f"✅ WH Inv: {wh_count} baris")

            # ══ B. SUBCON INV ════════════════════════════════════════════
            sub_count = 0
            for _, r in df_subcon.iterrows():
                p_no_sub  = bersihkan(r.get('Part No. SubCon', ''))
                if not p_no_sub:
                    continue

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
            masuk_count = 0
            for _, r in df_masuk.iterrows():
                p_no = bersihkan(r.get('Part No.', ''))
                if not p_no:
                    continue
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
            keluar_count = 0
            for _, r in df_keluar.iterrows():
                p_no = bersihkan(r.get('Part No.', ''))
                if not p_no:
                    continue
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
            simpan_info_sync(file_excel.name, wh_count, sub_count, masuk_count, keluar_count)
            st.sidebar.success("🎉 Sinkronisasi selesai!")
            st.rerun()

        except Exception as e:
            import traceback
            st.sidebar.error(f"❌ Error: {e}")
            st.sidebar.code(traceback.format_exc())

st.sidebar.divider()
st.sidebar.header("⚙️ Pengaturan")
threshold_stok = st.sidebar.number_input(
    "Ambang batas 'Stok Menipis' (Pcs)",
    min_value=0, value=50, step=10,
    help="Jika total stok (WH + Subcon) sebuah part berada di bawah angka ini, "
         "akan ditandai 🟡 STOK MENIPIS. Jika 0, ditandai 🔴 STOK KOSONG."
)

# ─────────────────────────────────────────────
# 4. NAVIGASI UTAMA (TAB)
# ─────────────────────────────────────────────
tab_cari, tab_dash = st.tabs(["🔍 Pencarian Part", "📊 Dashboard Ringkasan"])

# ═════════════════════════════════════════════
# TAB 1 — PENCARIAN
# ═════════════════════════════════════════════
with tab_cari:

    # ── Riwayat pencarian (chip cepat) ──────────────────────────────
    if "riwayat_cari" not in st.session_state:
        st.session_state.riwayat_cari = []

    keyword_input = st.text_input(
        "Cari berdasarkan nama part atau nomor part (Contoh: STAY MIRROR / 28STA):",
        key="keyword_box",
        placeholder="Ketik nama atau nomor part di sini..."
    ).upper().strip()

    if st.session_state.riwayat_cari:
        chips = "".join(
            f"<span class='search-chip'>🕘 {k}</span>"
            for k in st.session_state.riwayat_cari
        )
        st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)

    keyword = keyword_input

    if keyword:
        # simpan riwayat (maks 6, unik, terbaru di depan)
        riw = st.session_state.riwayat_cari
        if keyword in riw:
            riw.remove(keyword)
        riw.insert(0, keyword)
        st.session_state.riwayat_cari = riw[:6]

        df_hasil = pd.read_sql_query("""
            SELECT DISTINCT part_no, nama_part FROM master_wh
            WHERE (UPPER(part_no) LIKE ? OR UPPER(nama_part) LIKE ?)
              AND UPPER(nama_part) NOT LIKE '%BENDING%'
            UNION
            SELECT DISTINCT part_no, nama_part FROM detail_subcon
            WHERE (UPPER(part_no) LIKE ? OR UPPER(nama_part) LIKE ?)
              AND UPPER(nama_part) NOT LIKE '%BENDING%'
            ORDER BY part_no ASC
        """, conn, params=(f"%{keyword}%",) * 4)

        if df_hasil.empty:
            st.warning(f"Kata kunci '{keyword}' tidak ditemukan di database.")
        else:
            st.write(f"### 📌 Hasil Pencarian ({len(df_hasil)} item)")

            for idx_hasil, row in enumerate(df_hasil.itertuples()):
                part_no   = row.part_no
                nama_part = row.nama_part

                with st.expander(f"⚙️ [{part_no}] — {nama_part}"):

                    # ── Stok WH ─────────────────────────────────────
                    res_wh = pd.read_sql_query(
                        "SELECT SUM(stok_wh) as total FROM master_wh WHERE part_no=?",
                        conn, params=(part_no,))
                    stok_wh = res_wh.iloc[0]['total'] or 0

                    # ── Data Subcon ───────────────────────────────────
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

                    total_subcon = df_sub['stok'].sum() if not df_sub.empty else 0
                    grand_total = stok_wh + total_subcon
                    label_status, warna_status = status_stok(grand_total, threshold_stok)

                    # ── Kartu ringkasan WH ──────────────────────────
                    st.markdown(f"""
                    <div class="card-master">
                      <span class="judul">🏭 GUDANG UTAMA MATERIAL (AFTER PROCESS)</span>
                      <span class="status-badge" style="color:{warna_status};">{label_status}</span><br>
                      <span class="sub">Nomor Part Kode: <b>{part_no}</b></span><br>
                      <span class="nilai">Sisa Saldo Stock Akhir WH: <b>{stok_wh:,.2f} Pcs</b></span>
                    </div>""", unsafe_allow_html=True)

                    # ── Ringkasan total (metric, responsif HP/PC) ───
                    c1, c2, c3 = st.columns(3)
                    c1.metric("📦 Stok WH", f"{stok_wh:,.0f} Pcs")
                    c2.metric("🏢 Stok di Subcon", f"{total_subcon:,.0f} Pcs")
                    c3.metric("Σ Total Keseluruhan", f"{grand_total:,.0f} Pcs")

                    # ── Data Subcon ──────────────────────────────────
                    if not df_sub.empty:
                        suppliers = df_sub['nama_subcon'].unique()

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
                        <b style="color:#FFCC00;font-size:15px;">🏢 Distribusi Stok di Supplier Subcon:</b>
                        <div class="table-wrap">
                        <table class="supplier-table">
                          <thead><tr>
                            <th style="text-align:left;">Nama Supplier / Subcon</th>
                            <th>Stok Regular (Pcs)</th>
                            <th>Stok Klaim (Pcs)</th>
                            <th>Total (Pcs)</th>
                          </tr></thead>
                          <tbody>{rows_html}</tbody>
                        </table>
                        </div>
                        """, unsafe_allow_html=True)

                        # ── Tombol unduh ringkasan per item ─────────
                        ringkasan_simple = []
                        for sup in suppliers:
                            df_s = df_sub[df_sub['nama_subcon'] == sup]
                            reg   = df_s[df_s['tipe_stok'].str.lower().str.contains('regular', na=False)]['stok'].sum()
                            klaim = df_s[df_s['tipe_stok'].str.lower().str.contains('klaim|claim', na=False)]['stok'].sum()
                            ringkasan_simple.append({
                                "Supplier": sup, "Regular": reg, "Klaim": klaim, "Total": reg + klaim
                            })
                        df_export = pd.DataFrame(ringkasan_simple)
                        df_export.loc[len(df_export)] = ["STOK WH", "", "", stok_wh]

                        st.download_button(
                            label="⬇️ Unduh Ringkasan Stok Part Ini (Excel)",
                            data=to_excel_bytes({"Ringkasan": df_export}),
                            file_name=f"ringkasan_{part_no}.xlsx",
                            key=f"download_ringkasan_{idx_hasil}_{part_no}",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

                        # ── Detail + Histori per supplier (collapsible) ──
                        st.markdown("<br><b style='color:#AAA;'>📋 Klik Supplier untuk Lihat Detail & Histori:</b>",
                                    unsafe_allow_html=True)

                        for sup in suppliers:
                            df_s  = df_sub[df_sub['nama_subcon'] == sup]
                            reg   = df_s[df_s['tipe_stok'].str.lower().str.contains('regular', na=False)]['stok'].sum()
                            klaim = df_s[df_s['tipe_stok'].str.lower().str.contains('klaim|claim', na=False)]['stok'].sum()
                            total = reg + klaim
                            pno_s  = df_s.iloc[0]['part_no']
                            nama_s = df_s.iloc[0]['nama_part']

                            label_reg   = f"Regular: {reg:,.0f} Pcs"
                            label_klaim = f"Klaim: {klaim:,.0f} Pcs"
                            label_total = f"Total: {total:,.0f} Pcs"

                            with st.expander(f"📍 {sup} | {label_reg} | {label_klaim} | {label_total}"):
                                st.markdown(f"""
                                <div style="background:#0d0d0d;border:1px solid #2a2a2a;padding:12px;border-radius:6px;margin-bottom:10px;">
                                  <span style="color:#AAA;font-size:12px;">
                                    Part No Subcon: <span style="color:#FFCC00;">{pno_s}</span>
                                    &nbsp;|&nbsp; {nama_s}
                                  </span><br><br>
                                  <span style="color:#00D26A;font-weight:bold;font-size:14px;">● Stok Regular : {reg:,.0f} Pcs</span>
                                  &nbsp;&nbsp;&nbsp;
                                  <span style="color:#FF4B4B;font-weight:bold;font-size:14px;">● Stok Klaim : {klaim:,.0f} Pcs</span>
                                </div>""", unsafe_allow_html=True)

                                df_hist = pd.read_sql_query("""
                                    SELECT jenis_transaksi, tanggal, qty
                                    FROM histori_subcon
                                    WHERE UPPER(part_no)=? AND nama_subcon=?
                                    ORDER BY tanggal ASC
                                """, conn, params=(part_no, sup))

                                if not df_hist.empty:
                                    hist_rows = ""
                                    for _, h in df_hist.iterrows():
                                        jenis = str(h['jenis_transaksi'])
                                        if 'MASUK' in jenis.upper() or 'TERIMA' in jenis.upper():
                                            warna = "#00D26A"
                                            ikon  = "⬇️"
                                        else:
                                            warna = "#FF6B6B"
                                            ikon  = "⬆️"
                                        hist_rows += (
                                            f"<tr>"
                                            f"<td>{ikon} {jenis}</td>"
                                            f"<td>{h['tanggal']}</td>"
                                            f"<td style='color:{warna};font-weight:bold;'>{h['qty']:,.0f}</td>"
                                            f"</tr>"
                                        )
                                    st.markdown(f"""
                                    <div class="table-wrap">
                                    <table class="hist-table">
                                      <thead><tr>
                                        <th>Aktivitas</th>
                                        <th>Tanggal / Hari</th>
                                        <th>Qty (Pcs)</th>
                                      </tr></thead>
                                      <tbody>{hist_rows}</tbody>
                                    </table>
                                    </div>""", unsafe_allow_html=True)
                                else:
                                    st.caption("Tidak ada histori mutasi untuk supplier ini.")
                    else:
                        st.info("Item part ini murni berada di WH internal, tidak tersebar di supplier subcon.")
    else:
        st.info("💡 Masukkan nama part atau nomor part untuk mulai monitoring.")

# ═════════════════════════════════════════════
# TAB 2 — DASHBOARD RINGKASAN
# ═════════════════════════════════════════════
with tab_dash:

    if info_sync is None:
        st.info("💡 Belum ada data. Silakan upload & sinkronkan file Excel terlebih dahulu di sidebar.")
    else:
        # ── Ambil data dasar (sudah dikecualikan BENDING) ────────────
        df_wh_all = pd.read_sql_query("""
            SELECT part_no, nama_part, SUM(stok_wh) as stok_wh
            FROM master_wh
            WHERE UPPER(nama_part) NOT LIKE '%BENDING%'
            GROUP BY part_no, nama_part
        """, conn)

        df_sub_all = pd.read_sql_query("""
            SELECT part_no, SUM(jumlah_stok) as stok_subcon
            FROM detail_subcon
            WHERE UPPER(nama_part) NOT LIKE '%BENDING%'
            GROUP BY part_no
        """, conn)

        df_gabung = pd.merge(df_wh_all, df_sub_all, on="part_no", how="left")
        df_gabung['stok_subcon'] = df_gabung['stok_subcon'].fillna(0)
        df_gabung['total'] = df_gabung['stok_wh'] + df_gabung['stok_subcon']

        jml_supplier = pd.read_sql_query(
            "SELECT COUNT(DISTINCT nama_subcon) as n FROM detail_subcon", conn
        ).iloc[0]['n']

        # ── Metric ringkas ────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 Jumlah Part (WH)", f"{len(df_gabung):,}")
        m2.metric("🏭 Total Stok WH", f"{df_gabung['stok_wh'].sum():,.0f} Pcs")
        m3.metric("🏢 Total Stok di Subcon", f"{df_gabung['stok_subcon'].sum():,.0f} Pcs")
        m4.metric("🤝 Jumlah Supplier Subcon", f"{jml_supplier:,}")

        st.divider()

        # ── Daftar part dengan stok kosong / menipis ───────────────────
        df_alert = df_gabung[df_gabung['total'] < threshold_stok].copy()
        df_alert = df_alert.sort_values('total')

        st.markdown(f"#### ⚠️ Part dengan Status Stok Kosong / Menipis (< {threshold_stok:,.0f} Pcs)")
        if df_alert.empty:
            st.success("Tidak ada part dengan stok kosong atau menipis. 🎉")
        else:
            df_alert_show = df_alert[['part_no', 'nama_part', 'stok_wh', 'stok_subcon', 'total']].copy()
            df_alert_show['Status'] = df_alert_show['total'].apply(
                lambda t: status_stok(t, threshold_stok)[0])
            df_alert_show.columns = ['Part No.', 'Nama Part', 'Stok WH', 'Stok Subcon', 'Total', 'Status']
            st.dataframe(
                df_alert_show,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Stok WH": st.column_config.NumberColumn(format="%.0f"),
                    "Stok Subcon": st.column_config.NumberColumn(format="%.0f"),
                    "Total": st.column_config.NumberColumn(format="%.0f"),
                }
            )
            st.download_button(
                "⬇️ Unduh Daftar Stok Menipis/Kosong (Excel)",
                data=to_excel_bytes({"Stok Menipis": df_alert_show}),
                file_name="stok_menipis_kosong.xlsx",
                key="download_stok_menipis",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.divider()

        # ── Top part dengan stok terbanyak di subcon ───────────────────
        st.markdown("#### 🏆 Top 15 Part dengan Stok Terbanyak di Supplier Subcon")
        df_top_sub = df_gabung[df_gabung['stok_subcon'] > 0].sort_values(
            'stok_subcon', ascending=False).head(15)
        if df_top_sub.empty:
            st.info("Belum ada data stok subcon.")
        else:
            df_top_show = df_top_sub[['part_no', 'nama_part', 'stok_wh', 'stok_subcon', 'total']].copy()
            df_top_show.columns = ['Part No.', 'Nama Part', 'Stok WH', 'Stok Subcon', 'Total']
            st.dataframe(
                df_top_show, use_container_width=True, hide_index=True,
                column_config={
                    "Stok WH": st.column_config.NumberColumn(format="%.0f"),
                    "Stok Subcon": st.column_config.NumberColumn(format="%.0f"),
                    "Total": st.column_config.NumberColumn(format="%.0f"),
                }
            )

        st.divider()

        # ── Rekap per supplier subcon ───────────────────────────────────
        st.markdown("#### 🏢 Rekap Total Stok per Supplier Subcon")
        df_rekap_supplier = pd.read_sql_query("""
            SELECT nama_subcon as Supplier,
                   SUM(CASE WHEN LOWER(tipe_stok) LIKE '%regular%' THEN jumlah_stok ELSE 0 END) as Regular,
                   SUM(CASE WHEN LOWER(tipe_stok) LIKE '%klaim%' OR LOWER(tipe_stok) LIKE '%claim%' THEN jumlah_stok ELSE 0 END) as Klaim,
                   SUM(jumlah_stok) as Total
            FROM detail_subcon
            WHERE UPPER(nama_part) NOT LIKE '%BENDING%'
            GROUP BY nama_subcon
            ORDER BY Total DESC
        """, conn)
        st.dataframe(
            df_rekap_supplier, use_container_width=True, hide_index=True,
            column_config={
                "Regular": st.column_config.NumberColumn(format="%.0f"),
                "Klaim": st.column_config.NumberColumn(format="%.0f"),
                "Total": st.column_config.NumberColumn(format="%.0f"),
            }
        )

        st.divider()

        # ── Data lengkap & unduh semua ───────────────────────────────────
        with st.expander("📂 Lihat & Unduh Seluruh Data Master (WH + Subcon)"):
            cari_dash = st.text_input("Filter cepat (nama / nomor part):", key="filter_dashboard").upper().strip()
            df_tampil = df_gabung.copy()
            if cari_dash:
                df_tampil = df_tampil[
                    df_tampil['part_no'].str.upper().str.contains(cari_dash, na=False) |
                    df_tampil['nama_part'].str.upper().str.contains(cari_dash, na=False)
                ]
            df_tampil = df_tampil.sort_values('part_no')
            df_tampil_show = df_tampil[['part_no', 'nama_part', 'stok_wh', 'stok_subcon', 'total']].copy()
            df_tampil_show.columns = ['Part No.', 'Nama Part', 'Stok WH', 'Stok Subcon', 'Total']
            st.dataframe(
                df_tampil_show, use_container_width=True, hide_index=True,
                column_config={
                    "Stok WH": st.column_config.NumberColumn(format="%.0f"),
                    "Stok Subcon": st.column_config.NumberColumn(format="%.0f"),
                    "Total": st.column_config.NumberColumn(format="%.0f"),
                }
            )
            st.download_button(
                "⬇️ Unduh Semua Data Master (Excel)",
                data=to_excel_bytes({
                    "Master Gabungan": df_tampil_show,
                    "Rekap Supplier": df_rekap_supplier,
                }),
                file_name="master_stok_gudang_subcon.xlsx",
                key="download_master_gabungan",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
