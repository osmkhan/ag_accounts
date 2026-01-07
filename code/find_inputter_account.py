import pandas as pd

jn = pd.read_csv("/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv", dtype=str)
jn["AC_NO"] = pd.to_numeric(jn["AC_NO"], errors="coerce")
jn["DR"] = pd.to_numeric(jn.get("DR", 0), errors="coerce").fillna(0)
jn["CR"] = pd.to_numeric(jn.get("CR", 0), errors="coerce").fillna(0)

# find all lines where salary account (31) is involved
salary_txns = jn[jn["AC_NO"] == 31]

# show which other accounts appear in same transactions
counter_accounts = (
    jn[jn["TRN_DATE"].isin(salary_txns["TRN_DATE"])]
      .groupby("AC_NO", as_index=False)["CR"].sum()
      .sort_values("CR", ascending=False)
)
print(counter_accounts.head(10))


ACLIST_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/ACLIST_1425.csv"
JOURNAL_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv"

ac = pd.read_csv(ACLIST_PATH, dtype=str, keep_default_na=False)
jn = pd.read_csv(JOURNAL_PATH, dtype=str, keep_default_na=False)

ac.columns = [c.strip().upper() for c in ac.columns]
jn.columns = [c.strip().upper() for c in jn.columns]

jn["AC_NO"] = pd.to_numeric(jn["AC_NO"], errors="coerce")
jn["DR"] = pd.to_numeric(jn.get("DR", 0), errors="coerce").fillna(0)
jn["CR"] = pd.to_numeric(jn.get("CR", 0), errors="coerce").fillna(0)

# ---- find which accounts are opposite salary (31) ----
salary_txns = jn[jn["AC_NO"] == 31].copy()
dates = salary_txns["TRN_DATE"].unique()

# all entries from same transactions (same date) — approximate pairing
related = jn[jn["TRN_DATE"].isin(dates)].copy()
related = related.groupby("AC_NO", as_index=False)[["DR","CR"]].sum()
related["NET"] = related["DR"] - related["CR"]

# add account name
ac["NO"] = pd.to_numeric(ac["NO"], errors="coerce")
related = related.merge(ac[["NO","HEAD"]], left_on="AC_NO", right_on="NO", how="left")
related = related[["AC_NO","HEAD","DR","CR","NET"]].sort_values("CR", ascending=False)

print("Top accounts crediting salary (Account 31):")
print(related)