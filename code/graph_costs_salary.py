# pip install pandas matplotlib python-dateutil
"""
Simplified: Analyze expense heads and their growth from a double-entry ledger.

Outputs (to OUT_DIR):
- monthly_expense_shares.csv   # month x head totals, % of total expenses, % of revenue
- top_costs.csv                # ranked expense heads with totals, avg share, growth signals
- top_expense_trends.png       # line chart of top-N expense heads over time (PKR)
- expense_share_heatmap.png    # heatmap of % of total expenses by month (Top-N)
- largest_costs_bar.png        # bar chart of largest costs over the selected span

Assumptions:
- 'aclist' has HEAD (name) and CLASS (1 A, 2 L, 3 Income, 4 Expense)
- 'journal' has DR/CR in PKR and TRN_DATE, AC_NO
- Income increases on credit (CR-DR). Expenses increase on debit (DR-CR).

Edit CONFIG below or pass CLI args, then run:  python analyze_costs_simple.py
CLI overrides config:  --start 2021 --end 2025 --top 10
"""

from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

# -------------------
# CONFIG (can be overridden by CLI)
# -------------------
ACLIST_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/ACLIST_1425.csv"
JOURNAL_PATH = "/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/JOURNAL_1425.csv"
OUT_DIR = Path("/Users/osmankhan/Desktop/agro_accounts/ag_data_2014_2025/analysis")
TOP_N = 10  # how many expense heads to show in charts
OUT_DIR.mkdir(parents=True, exist_ok=True)
YEAR_START = 2024
YEAR_END = 2026

# -------------------
# Helpers
# -------------------
def ensure_dt_month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.to_period("M").astype(str)

def to_dt_start_of_month(month_str: pd.Series) -> pd.Series:
    return pd.to_datetime(month_str + "-01", errors="coerce")

def load_and_prepare(aclist_path: str, journal_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ac = pd.read_csv(aclist_path, dtype=str, keep_default_na=False)
    jn = pd.read_csv(journal_path, dtype=str, keep_default_na=False)

    ac.columns = [c.strip().upper() for c in ac.columns]
    jn.columns = [c.strip().upper() for c in jn.columns]

    # Coerce types
    ac["NO"] = pd.to_numeric(ac.get("NO"), errors="coerce")
    ac["CLASS"] = pd.to_numeric(ac.get("CLASS"), errors="coerce")
    ac["LEVEL"] = pd.to_numeric(ac.get("LEVEL"), errors="coerce")
    ac["HEAD"] = ac.get("HEAD", "").astype(str).str.strip()

    jn["TRN_DATE"] = pd.to_datetime(jn.get("TRN_DATE"), errors="coerce")
    jn["AC_NO"] = pd.to_numeric(jn.get("AC_NO"), errors="coerce")
    jn["DR"] = pd.to_numeric(jn.get("DR", 0), errors="coerce").fillna(0)
    jn["CR"] = pd.to_numeric(jn.get("CR", 0), errors="coerce").fillna(0)
    jn = jn.dropna(subset=["TRN_DATE", "AC_NO"])

    # Simple dedupe of accounts: prefer deepest LEVEL, then non-empty HEAD
    ac["_has_head"] = (ac["HEAD"] != "").astype(int)
    ac = ac.sort_values(["NO", "LEVEL", "_has_head"], ascending=[True, False, False])
    ac_dim = ac.drop_duplicates(subset=["NO"], keep="first")[["NO", "HEAD", "CLASS"]].copy()

    # Merge
    df = jn.merge(ac_dim, left_on="AC_NO", right_on="NO", how="left", validate="m:1")
    df["net_expense"] = df["DR"] - df["CR"]   # + for expenses
    df["net_income"] = df["CR"] - df["DR"]    # + for revenue
    df["month"] = ensure_dt_month(df["TRN_DATE"])

    return df, ac_dim

def filter_year_span(df: pd.DataFrame, year_start: int, year_end: int) -> pd.DataFrame:
    start = pd.Timestamp(year_start, 1, 1)
    end = pd.Timestamp(year_end, 12, 31)
    return df[(df["TRN_DATE"] >= start) & (df["TRN_DATE"] <= end)].copy()

def compute_monthly(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Expenses (CLASS == 4)
    expenses = df[df["CLASS"] == 4].copy()
    monthly_costs = expenses.groupby(["month", "HEAD"], as_index=False).agg(
        total_pkr=("net_expense", "sum")
    )
    # Month totals (denominator)
    month_expense_total = monthly_costs.groupby("month", as_index=False)["total_pkr"].sum()
    month_expense_total = month_expense_total.rename(columns={"total_pkr": "month_expense_total_pkr"})

    # Revenue (CLASS == 3)
    income = df[df["CLASS"] == 3].copy()
    rev_monthly = income.groupby("month", as_index=False).agg(
        total_revenue_pkr=("net_income", "sum")
    )

    # Combine denominators and shares
    monthly_costs = (
        monthly_costs.merge(month_expense_total, on="month", how="left")
                     .merge(rev_monthly, on="month", how="left")
                     .fillna({"total_revenue_pkr": 0})
    )
    # % of total expenses
    monthly_costs["pct_of_expenses"] = (
        monthly_costs["total_pkr"] / monthly_costs["month_expense_total_pkr"]
    ).where(monthly_costs["month_expense_total_pkr"] != 0, 0) * 100

    # % of revenue
    monthly_costs["pct_of_revenue"] = (
        monthly_costs["total_pkr"] / monthly_costs["total_revenue_pkr"]
    ).where(monthly_costs["total_revenue_pkr"] > 0, pd.NA) * 100
    corn_accounts = df[df["HEAD"].str.contains("corn", case=False, na=False)]
    corn_expenses = corn_accounts[corn_accounts["CLASS"] == 4].copy()

    # compute monthly totals
    corn_expenses["month"] = corn_expenses["TRN_DATE"].dt.to_period("M").astype(str)
    corn_monthly = (
        corn_expenses.groupby(["month", "HEAD"], as_index=False)
        .agg(total_pkr=("net_expense", "sum"))
        .sort_values(["month", "total_pkr"], ascending=[True, False])
    )
    plt.figure(figsize=(9,5))
    for h in corn_monthly["HEAD"].unique():
        d = corn_monthly[corn_monthly["HEAD"] == h]
        plt.plot(pd.to_datetime(d["month"] + "-01"), d["total_pkr"], label=h)

    plt.title("Corn-related Expense Accounts Over Time (PKR)")
    plt.xlabel("Month")
    plt.ylabel("PKR (DR − CR)")
    plt.legend(frameon=False)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "corn_expense_trend.png", dpi=180)
    plt.close()
    out_path = OUT_DIR / "corn_expenses.csv"
    corn_monthly.to_csv(out_path, index=False)
    print("Wrote:", out_path)
    print(corn_monthly.head(10))

    return monthly_costs, month_expense_total, rev_monthly

def rank_costs(monthly_costs: pd.DataFrame) -> pd.DataFrame:
    # Totals across span + avg share + growth signal (mean MoM % change)
    top_costs = (
        monthly_costs.groupby("HEAD", as_index=False)
        .agg(
            total_spend_pkr=("total_pkr", "sum"),
            avg_share_pct=("pct_of_expenses", "mean"),
            first_month=("month", "min"),
            last_month=("month", "max"),
            months_active=("month", "nunique"),
        )
        .sort_values(["total_spend_pkr", "avg_share_pct"], ascending=[False, False])
    )

    mc_sorted = (
        monthly_costs.sort_values(["HEAD", "month"])
        .assign(pct_change=lambda d: d.groupby("HEAD")["total_pkr"].pct_change())
    )
    growth = mc_sorted.groupby("HEAD", as_index=False).agg(mean_mom_growth=("pct_change", "mean"))
    return top_costs.merge(growth, on="HEAD", how="left")

def make_charts(monthly_costs: pd.DataFrame, top_costs: pd.DataFrame, out_dir: Path, top_n: int):
    out_dir.mkdir(parents=True, exist_ok=True)

    # Choose Top-N by total spend
    top_heads = top_costs.head(top_n)["HEAD"].tolist()
    plot_df = monthly_costs[monthly_costs["HEAD"].isin(top_heads)].copy()
    plot_df = plot_df.sort_values("month")
    plot_df["month_dt"] = to_dt_start_of_month(plot_df["month"])

    # 1) Line chart of Top-N expense heads over time
    plt.figure(figsize=(10, 5))
    for h in top_heads:
        d = plot_df[plot_df["HEAD"] == h]
        plt.plot(d["month_dt"], d["total_pkr"], linewidth=2, label=h)
    plt.title("Top Expense Categories Over Time (PKR)")
    plt.xlabel("Month")
    plt.ylabel("PKR (DR − CR)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    plt.tight_layout()
    (out_dir / "top_expense_trends.png").write_bytes(plt.gcf().canvas.tostring_rgb())  # ensure file system init
    plt.savefig(out_dir / "top_expense_trends.png", dpi=180)
    plt.close()

    # 2) Heatmap of % of total expenses by month (Top-N)
    heat = (
        plot_df.pivot_table(index="month_dt", columns="HEAD", values="pct_of_expenses", aggfunc="mean")
        .sort_index()
        .reindex(columns=top_heads)
    )
    plt.figure(figsize=(10, 6))
    plt.imshow(heat.fillna(0).to_numpy(), aspect="auto", interpolation="nearest")
    plt.title("% of Total Expenses by Month (Top Categories)")
    plt.xlabel("Expense Head")
    plt.ylabel("Month")
    plt.xticks(range(len(heat.columns)), heat.columns, rotation=45, ha="right", fontsize=8)
    yticks = range(0, len(heat.index), max(1, len(heat.index)//12 or 1))
    plt.yticks(yticks, [heat.index[i].strftime("%Y-%m") for i in yticks], fontsize=8)
    plt.colorbar(label="% of total expenses")
    plt.tight_layout()
    plt.savefig(out_dir / "expense_share_heatmap.png", dpi=180)
    plt.close()

    # 3) Bar chart of largest costs (overall in span)
    largest = top_costs.head(top_n)
    plt.figure(figsize=(10, 6))
    plt.bar(largest["HEAD"], largest["total_spend_pkr"])
    plt.title(f"Largest Costs (Top {top_n}) over Selected Span")
    plt.xlabel("Expense Head")
    plt.ylabel("Total PKR (DR − CR)")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_dir / "largest_costs_bar.png", dpi=180)
    plt.close()

def main():
    parser = argparse.ArgumentParser(description="Simplified expense analysis from double-entry ledger.")
    parser.add_argument("--aclist", default=ACLIST_PATH, help="Path to ACLIST.csv")
    parser.add_argument("--journal", default=JOURNAL_PATH, help="Path to JOURNAL.csv")
    parser.add_argument("--out", default=str(OUT_DIR), help="Output directory")
    parser.add_argument("--top", type=int, default=TOP_N, help="Top-N expense heads to chart")
    parser.add_argument("--start", type=int, default=YEAR_START, help="Start year (inclusive)")
    parser.add_argument("--end", type=int, default=YEAR_END, help="End year (inclusive)")
    args = parser.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    df, ac_dim = load_and_prepare(args.aclist, args.journal)
    df = filter_year_span(df, args.start, args.end)

    monthly_costs, month_expense_total, rev_monthly = compute_monthly(df)
    if monthly_costs.empty:
        print("No expense rows in the selected span."); return

    # Save monthly shares
    monthly_path = out_dir / "monthly_expense_shares.csv"
    monthly_costs.sort_values(["month", "total_pkr"], ascending=[True, False]).to_csv(monthly_path, index=False)

    # Rank costs
    top_costs = rank_costs(monthly_costs)
    top_path = out_dir / "top_costs.csv"
    top_costs.to_csv(top_path, index=False)

    # Charts
    make_charts(monthly_costs, top_costs, out_dir, args.top)

    # Summary
    horizon_start = pd.to_datetime(monthly_costs["month"].min() + "-01")
    horizon_end = (pd.to_datetime(monthly_costs["month"].max() + "-01") + relativedelta(day=31))
    total_expenses = month_expense_total["month_expense_total_pkr"].sum()
    print(f"Wrote: {monthly_path}")
    print(f"Wrote: {top_path}")
    print(f"Wrote: {out_dir / 'top_expense_trends.png'}")
    print(f"Wrote: {out_dir / 'expense_share_heatmap.png'}")
    print(f"Wrote: {out_dir / 'largest_costs_bar.png'}")
    print(f"Span: {horizon_start.date()} → {horizon_end.date()}")
    print(f"Total expenses across span (PKR): {total_expenses:,.0f}")
    print("Top heads:")
    print(top_costs.head(args.top)[["HEAD","total_spend_pkr","avg_share_pct","mean_mom_growth"]].to_string(index=False))
    

if __name__ == "__main__":
    main()
