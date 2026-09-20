import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="シラバス・時間割作成ツール", layout="wide")


# 1. CSVデータの読み込み関数
@st.cache_data
def load_data():
    script_dir = os.path.dirname(__file__)

    # シラバスデータの読み込み
    csv_path = os.path.join(script_dir, "syllabus_tmu.csv")
    if not os.path.exists(csv_path):
        csv_path = "syllabus_tmu.csv"
    df_syllabus = pd.read_csv(csv_path)

    # 学年別単位データの読み込み
    try:
        credits_path = os.path.join(script_dir, "grade_credits.csv")
        if not os.path.exists(credits_path):
            credits_path = "grade_credits.csv"

        df_credits = pd.read_csv(credits_path)
        # '-' を 0 に置換し、数値型に変換
        for col in df_credits.columns:
            if col != "学年":
                df_credits[col] = (
                    df_credits[col]
                    .astype(str)
                    .str.replace("-", "0")
                    .str.strip()
                )
                df_credits[col] = (
                    pd.to_numeric(df_credits[col], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )
    except Exception as e:
        df_credits = None

    return df_syllabus, df_credits


# データの呼び出し
df, df_credits = load_data()


# 各列の自動特定
CATEGORY_COL = "科目区分" if "科目区分" in df.columns else df.columns[0]
SUB_CATEGORY_COL = "区分詳細" if "区分詳細" in df.columns else None
SUBJECT_COL = "科目名" if "科目名" in df.columns else df.columns[1]

for col in df.columns:
    if any(k in str(col) for k in ["授業", "科目名", "コース"]):
        if not any(ik in str(col) for ik in ["区分", "種別"]):
            SUBJECT_COL = col
            break

# 曜日・時限・開講期の列を特定
DAY_COL = next(
    (c for c in df.columns if "曜日" in str(c) or str(c) == "曜日"), None
)
PERIOD_COL = next(
    (c for c in df.columns if "時限" in str(c) or str(c) == "時限"), None
)
SEMESTER_COL = next(
    (
        c
        for c in df.columns
        if any(k in str(c) for k in ["開講期", "学期", "期"])
    ),
    None,
)


# 2. リセット用コールバック関数
def reset_select(key_to_reset):
    st.session_state[key_to_reset] = "-- 未選択 --"


# 3. 画面タイトルと学年フィルターの設置
st.title("シラバス・時間割作成ツール")

# 対象学年の選択UI
target_year = st.radio(
    "**表示・選択する対象学年を選んでください**",
    options=["1年", "2年", "3年", "4年"],
    horizontal=True,
)

# 選択された学年を数値（1, 2, 3, 4）に変換
selected_grade_num = int(target_year.replace("年", ""))

# --- メイン画面：学年別目標単位数の表示 ---
if df_credits is not None:
    st.subheader(f"🎓 {target_year}の目標取得単位")

    # 選択された学年のデータを行として取得
    grade_row = df_credits[df_credits["学年"] == selected_grade_num]

    if not grade_row.empty:
        # 目標単位数を辞書形式で抽出（'学年' 列を除く）
        target_dict = grade_row.drop(columns=["学年"]).iloc[0].to_dict()

        # 0単位以外の項目を抽出して表示
        active_targets = {k: v for k, v in target_dict.items() if v > 0}

        if active_targets:
            cols = st.columns(len(active_targets))
            for idx, (cat, target_val) in enumerate(active_targets.items()):
                with cols[idx]:
                    st.metric(label=cat, value=f"{target_val} 単位")
# 注意書きの追加
    st.caption("※上記で4年間122単位分。122単位に加え共通科目・専門科目のどれかで6単位とること")

st.divider()

# 「他」を曜日の最後（または端）に追加
days = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "他"]
periods = [1, 2, 3, 4, 5, 6]

# CSV内から存在する学期（「集中」なども含む）を動的に取得
if SEMESTER_COL and SEMESTER_COL in df.columns:
    unique_sems = (
        df[SEMESTER_COL].dropna().astype(str).str.strip().unique().tolist()
    )
    semesters = [s for s in unique_sems if s and s != "nan"]
    if not semesters:
        semesters = ["前期", "後期", "通年", "集中"]
else:
    semesters = ["前期", "後期", "通年", "集中"]

# 4. 全科目のリアルタイム合算集計処理
total_credits = 0
category_credits = {}

for period in periods + [0]:  # 時限 0（集中講義等）も集計対象に含める
    for day in days:
        for sem in semesters:
            key = f"select_{day}_{period}限_{sem}"
            selected = st.session_state.get(key, "-- 未選択 --")

            if selected and selected != "-- 未選択 --":
                match = df[df[SUBJECT_COL] == selected]
                if not match.empty:
                    info = match.iloc[0]
                    credit_val = info.get("単位数", info.get("単位", 2))
                    try:
                        c = float(credit_val)
                    except (ValueError, TypeError):
                        c = 2.0

                    total_credits += c

                    cat = str(info.get(CATEGORY_COL, "その他")).strip()
                    if cat and cat != "nan":
                        category_credits[cat] = (
                            category_credits.get(cat, 0.0) + c
                        )

# 5. 集計結果の表示
st.subheader("📊 年間取得単位数（全学期・全区分 合算）")

if category_credits:
    metrics_cols = st.columns(len(category_credits) + 1)
    metrics_cols[0].metric(
        label="合計取得単位数",
        value=f"{int(total_credits) if total_credits.is_integer() else total_credits} 単位",
    )
    for idx, (cat_name, credits) in enumerate(category_credits.items()):
        val_str = f"{int(credits) if credits.is_integer() else credits} 単位"
        metrics_cols[idx + 1].metric(label=f"【{cat_name}】", value=val_str)
else:
    st.metric(label="合計取得単位数", value="0 単位")
    st.caption(
        "※ 時間割から科目を選択すると、全学期を合算した単位数がリアルタイムで集計されます。"
    )

st.divider()

# 6. 時間割グリッドの表示
header_cols = st.columns([1, 2, 2, 2, 2, 2, 2])
header_cols[0].write("**時限**")
for i, day in enumerate(days):
    header_cols[i + 1].write(f"**{day}**")

for period in periods:
    row_cols = st.columns([1, 2, 2, 2, 2, 2, 2])
    row_cols[0].write(f"**{period}限**")

    for i, day in enumerate(days):
        with row_cols[i + 1]:
            # 「他」の列の場合、時限は 0 （または 1限のセル内）として検索対象にする
            current_period_str = (
                "0" if day == "他" and period == 1 else str(period)
            )

            # 「他」の列で 2限以降の場合はスキップ（1限の行にまとめて表示するため）
            if day == "他" and period > 1:
                continue

            for sem in semesters:
                filtered_df = df.copy()

                # 学年フラグによる絞り込み
                if target_year in filtered_df.columns:
                    filtered_df = filtered_df[
                        filtered_df[target_year].astype(str).str.strip() == "1"
                    ]

                # 学期による絞り込み
                if SEMESTER_COL and SEMESTER_COL in df.columns:
                    filtered_df = filtered_df[
                        filtered_df[SEMESTER_COL]
                        .astype(str)
                        .str.contains(sem, na=False)
                    ]

                # 曜日による絞り込み（「他」または「月」〜「金」）
                if DAY_COL and DAY_COL in df.columns:
                    if day == "他":
                        filtered_df = filtered_df[
                            filtered_df[DAY_COL]
                            .astype(str)
                            .str.contains("他", na=False)
                        ]
                    else:
                        day_short = day.replace("曜日", "")
                        filtered_df = filtered_df[
                            filtered_df[DAY_COL]
                            .astype(str)
                            .str.contains(day_short, na=False)
                        ]

                # 時限による絞り込み
                if PERIOD_COL and PERIOD_COL in df.columns:
                    filtered_df = filtered_df[
                        filtered_df[PERIOD_COL]
                        .astype(str)
                        .str.contains(current_period_str, na=False)
                    ]

                options_list = (
                    filtered_df[SUBJECT_COL].dropna().unique().tolist()
                )

                if len(options_list) > 0:
                    st.caption(f"【{sem}】")
                    select_key = f"select_{day}_{period}限_{sem}"
                    course_options = ["-- 未選択 --"] + options_list

                    selected_course = st.selectbox(
                        label=f"{day}{period}限{sem}",
                        options=course_options,
                        key=select_key,
                        label_visibility="collapsed",
                    )

                    if selected_course != "-- 未選択 --":
                        match = df[df[SUBJECT_COL] == selected_course]
                        if not match.empty:
                            info = match.iloc[0]
                            cat = str(info.get(CATEGORY_COL, "")).strip()
                            credit = info.get(
                                "単位数", info.get("単位", "")
                            )

                            sub_cat = ""
                            if (
                                SUB_CATEGORY_COL
                                and SUB_CATEGORY_COL in info
                            ):
                                raw_sub = str(info[SUB_CATEGORY_COL]).strip()
                                if raw_sub and raw_sub not in [
                                    "nan",
                                    "-",
                                    "None",
                                ]:
                                    sub_cat = raw_sub

                            with st.container(border=True):
                                st.markdown(f"**{selected_course}**")

                                details = []
                                if cat and cat != "nan":
                                    details.append(cat)
                                if sub_cat:
                                    details.append(sub_cat)
                                if (
                                    pd.notna(credit)
                                    and str(credit) != ""
                                ):
                                    details.append(f"{credit}単位")

                                if details:
                                    st.caption(" / ".join(details))

                                st.button(
                                    "削除",
                                    key=f"btn_{select_key}",
                                    on_click=reset_select,
                                    args=(select_key,),
                                )
