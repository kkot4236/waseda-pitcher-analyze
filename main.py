import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
import glob
import plotly.express as px

# --- 1. ページ設定 ---
st.set_page_config(page_title="Pitch Analysis Dashboard", layout="wide")

# --- 2. データ読み込み ---
@st.cache_data
def load_all_data_from_folder(folder_path):
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not all_files: return None
    list_df = []
    for filename in all_files:
        try:
            temp_df = pd.read_csv(filename, encoding='utf-8')
        except:
            temp_df = pd.read_csv(filename, encoding='cp932')
        fname_lower = os.path.basename(filename).lower()
        category = "SBP" if "sbp" in fname_lower else "vs" if "vs" in fname_lower else "PBP" if "pbp" in fname_lower else "pitching" if "pitching" in fname_lower else "その他"
        
        rename_dict = {
            'Pitch Type': 'TaggedPitchType', 'Is Strike': 'PitchCall',
            'RelSpeed (KMH)': 'RelSpeed', 'InducedVertBreak (CM)': 'InducedVertBreak',
            'HorzBreak (CM)': 'HorzBreak', 'PlateLocSide (CM)': 'PlateLocSide',
            'PlateLocHeight (CM)': 'PlateLocHeight', 'Batter Side': 'BatterSide'
        }
        temp_df = temp_df.rename(columns=rename_dict)
        temp_df['DataCategory'] = category
        temp_df['Pitcher'] = temp_df['Pitcher'].astype(str).str.strip() if 'Pitcher' in temp_df.columns else "Unknown"
        
        if 'PitchCall' in temp_df.columns:
            temp_df['is_strike'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['Y', 'STRIKECALLED', 'STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_swing'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING', 'FOULBALL', 'INPLAY'] else 0)
            temp_df['is_whiff'] = temp_df['PitchCall'].apply(lambda x: 1 if str(x).upper() in ['STRIKESWINGING'] else 0)
        
        if 'Balls' in temp_df.columns and 'Strikes' in temp_df.columns:
            temp_df['is_first_pitch'] = ((temp_df['Balls'] == 0) & (temp_df['Strikes'] == 0)).astype(int)
        
        temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.date if 'Date' in temp_df.columns else pd.Timestamp.now().date()
        list_df.append(temp_df)
    
    data = pd.concat(list_df, axis=0, ignore_index=True)
    return data.convert_dtypes(dtype_backend="numpy_nullable")

# --- 3. リスク管理グラフ (対左右2本表示 ＆ レイアウト同期) ---
def render_risk_management_grid(f_data):
    st.write("#### 📊 リスク管理 (打球結果)")
    def classify_result(row):
        res, call, hit = str(row.get('PlayResult','')).lower(), str(row.get('PitchCall','')).lower(), str(row.get('TaggedHitType','')).lower()
        if 'strikeout' in res or 'strikeout' in call or 'popup' in hit: return '完全アウト'
        elif 'home' in res: return '本塁打'
        elif 'walk' in res or 'hitby' in res: return '四死球'
        elif 'ground' in hit: return 'ゴロ'
        elif 'fly' in hit or 'line' in hit: return '外野フライ+ライナー'
        return None

    f_risk = f_data.copy()
    f_risk['ResultCategory'] = f_risk.apply(classify_result, axis=1)
    f_risk = f_risk.dropna(subset=['ResultCategory'])
    if f_risk.empty: return st.info("分析用のデータがありません。")

    color_map = {'完全アウト': '#6495ED', 'ゴロ': '#ADFF2F', '外野フライ+ライナー': '#FFD700', '四死球': '#F4A460', '本塁打': '#FF0000'}
    cat_order = ['完全アウト', 'ゴロ', '外野フライ+ライナー', '四死球', '本塁打']

    c1, c2 = st.columns([1, 1])
    
    # --- 左側：対打者別 (Right/Leftの2本に戻しました) ---
    with c1:
        side_list = []
        for s in ['Right', 'Left']:
            sd = f_risk[f_risk['BatterSide'] == s]
            if not sd.empty:
                counts = sd['ResultCategory'].value_counts(normalize=True) * 100
                for cat, val in counts.items():
                    side_list.append({'対象': f'対{s}打者', 'カテゴリ': cat, '割合(%)': val})
        
        if side_list:
            fig_side = px.bar(pd.DataFrame(side_list), y='対象', x='割合(%)', color='カテゴリ', orientation='h', 
                              color_discrete_map=color_map, category_orders={'カテゴリ': cat_order})
            fig_side.update_layout(
                xaxis=dict(range=[0, 100], title="割合 (%)"),
                yaxis=dict(title=""),
                margin=dict(l=100, r=20, t=10, b=10), # 左余白を多めに取って右と揃える
                height=250,
                showlegend=False,
                barmode='stack'
            )
            st.plotly_chart(fig_side, use_container_width=True)

    # --- 右側：球種別 ---
    with c2:
        pitch_list = []
        for pt in f_risk['TaggedPitchType'].unique():
            pd_sub = f_risk[f_risk['TaggedPitchType'] == pt]
            if not pd_sub.empty:
                for c, v in (pd_sub['ResultCategory'].value_counts(normalize=True)*100).items():
                    pitch_list.append({'球種': pt, 'カテゴリ': c, '割合(%)': v})
        
        if pitch_list:
            fig_pt = px.bar(pd.DataFrame(pitch_list), y='球種', x='割合(%)', color='カテゴリ', orientation='h', 
                            color_discrete_map=color_map, category_orders={'カテゴリ': cat_order})
            fig_pt.update_layout(
                xaxis=dict(range=[0, 100], title="割合 (%)"),
                yaxis=dict(title=""),
                margin=dict(l=100, r=20, t=10, b=10), # 左マージンを左のグラフと統一
                height=250,
                legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5),
                legend_title="",
                barmode='stack'
            )
            st.plotly_chart(fig_pt, use_container_width=True)

# --- 4. 統計タブ描画 ---
def render_stats_tab(f_data, key_suffix):
    if f_data.empty: return st.warning("表示するデータがありません。")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    fb = f_data[f_data['TaggedPitchType'].isin(["Fastball", "FB"])]
    m1.metric("投球数", f"{len(f_data)} 球")
    m2.metric("平均(直球)", f"{fb['RelSpeed'].mean():.1f} km/h")
    m3.metric("最速", f"{f_data['RelSpeed'].max():.1f} km/h")
    m4.metric("スト率", f"{(f_data['is_strike'].mean()*100):.1f} %")
    m5.metric("初球スト", f"{(f_data[f_data['is_first_pitch']==1]['is_strike'].mean()*100):.1f} %")

    summary = f_data.groupby('TaggedPitchType').agg({'RelSpeed': ['count', 'mean', 'max'], 'is_strike': 'mean', 'is_swing': 'mean', 'is_whiff': 'sum'})
    summary.columns = ['投球数', '平均球速', '最速', 'ストライク率', 'スイング率', '空振り数']
    summary['投球割合'] = (summary['投球数'] / summary['投球数'].sum() * 100)
    summary['Whiff %'] = (summary['空振り数'] / f_data.groupby('TaggedPitchType')['is_swing'].sum() * 100).fillna(0)
    
    disp = summary.copy()
    for c in ['投球割合', 'ストライク率', 'スイング率', 'Whiff %']: 
        disp[c] = (summary[c] * (100 if c!='投球割合' else 1)).apply(lambda x: f"{x:.1f} %")
    
    col_l, col_r = st.columns([2.3, 1])
    with col_l:
        st.write("### 📊 球種別分析")
        st.table(disp[['投球数', '投球割合', '平均球速', '最速', 'ストライク率', 'Whiff %']])
        render_risk_management_grid(f_data)
    
    with col_r:
        st.write("### 🥧 投球割合")
        if not summary.empty:
            plt.clf()
            fig, ax = plt.subplots(figsize=(2.2, 2.2))
            ax.pie(summary['投球数'], labels=summary.index, autopct='%1.1f%%', startangle=90, counterclock=False, 
                   colors=plt.get_cmap('Pastel1').colors, textprops={'fontsize': 7})
            fig.tight_layout(pad=0)
            st.pyplot(fig)

    st.divider()
    st.write("### 🗓 カウント別 投球割合")
    mode = st.radio("表示モード", ["全カウント", "2ストライク時のみ"], horizontal=True, key=f"mode_{key_suffix}")
    f_data['Count'] = f_data['Balls'].fillna(0).astype(int).astype(str) + "-" + f_data['Strikes'].fillna(0).astype(int).astype(str)
    plot_sub = f_data[f_data['Strikes']==2] if mode=="2ストライク時のみ" else f_data
    lbls = ["0-2","1-2","2-2","3-2","2スト全体"] if mode=="2ストライク時のみ" else ["0-0","1-0","2-0","3-0","0-1","1-1","2-1","3-1","0-2","1-2","2-2","3-2","全体"]
    if not plot_sub.empty:
        c_map = pd.crosstab(plot_sub['Count'], plot_sub['TaggedPitchType'])
        tot = pd.DataFrame(plot_sub['TaggedPitchType'].value_counts()).T
        tot.index = [lbls[-1]]
        final = pd.concat([c_map, tot]).reindex(index=lbls, fill_value=0)
        st.bar_chart(final.div(final.sum(axis=1).replace(0,1), axis=0)*100)

# --- 5. メインロジック ---
df = load_all_data_from_folder(os.path.join(os.path.dirname(__file__), "data"))
if df is not None:
    tabs = st.tabs(["🔹 SBP", "🔹 オープン戦", "⚾ 実戦/PBP", "🔥 pitching"])
    
    def get_filtered_data(category_name, k_suffix):
        sub_df = df[df['DataCategory'] == category_name]
        if sub_df.empty: return sub_df
        p_list = sorted([str(p) for p in sub_df['Pitcher'].unique() if p != "Unknown"])
        c1, c2 = st.columns(2)
        p = c1.selectbox("投手を選択", ["すべて"] + p_list, key=f"p_{k_suffix}")
        d = c2.selectbox("日付を選択", ["すべて"] + sorted(sub_df['Date'].unique().astype(str), reverse=True), key=f"d_{k_suffix}")
        if p != "すべて": sub_df = sub_df[sub_df['Pitcher'] == p]
        if d != "すべて": sub_df = sub_df[sub_df['Date'].astype(str) == d]
        return sub_df

    with tabs[0]: render_stats_tab(get_filtered_data("SBP", "sbp"), "sbp")
    with tabs[1]: render_stats_tab(get_filtered_data("vs", "vs"), "vs")
    with tabs[2]: render_stats_tab(get_filtered_data("PBP", "pbp"), "pbp")
    with tabs[3]: render_stats_tab(get_filtered_data("pitching", "ptc"), "ptc")
else:
    st.error("dataフォルダにCSVが見つかりません。")
