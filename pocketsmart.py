import json
import pandas as pd
import streamlit as st
from common import ask, chat_reply, make_pdf, page_setup

page_setup("PocketSmart AI", "💰", "Your smart budget & recommendation assistant")
st.caption("General guidance, not professional financial advice.")
SYSTEM = "You are a practical personal-finance assistant. Be specific, realistic and concise."

with st.sidebar:
    cur = st.selectbox("Currency", ["₹", "$", "€", "£"])
    income = st.number_input(f"Monthly income ({cur})", 0.0, value=50000.0, step=1000.0)
    goal = st.number_input(f"Monthly savings goal ({cur})", 0.0, value=10000.0, step=500.0)
    up = st.file_uploader("Upload transactions CSV (columns: category, amount)", type="csv")

data = pd.DataFrame({"category": ["Rent", "Food", "Transport", "Utilities", "Entertainment", "Shopping"],
                     "amount": [15000.0, 8000.0, 3000.0, 2000.0, 2500.0, 3000.0]})
if up:
    try:
        raw = pd.read_csv(up)
        raw.columns = [c.strip().lower() for c in raw.columns]
        raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce").fillna(0)
        data = raw[["category", "amount"]].groupby("category", as_index=False).sum()
    except Exception:
        st.sidebar.error("CSV must have 'category' and 'amount' columns.")

st.subheader("Monthly expenses (edit, add or delete rows)")
df = st.data_editor(data, num_rows="dynamic", key=f"ed_{up.name if up else 'default'}")
df = df.dropna(subset=["category"]).copy()
df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
spent = df["amount"].sum()
saved = income - spent

c = st.columns(3)
c[0].metric("Total spent", f"{cur}{spent:,.0f}")
c[1].metric("Left over", f"{cur}{saved:,.0f}", f"{cur}{saved - goal:,.0f} vs goal")
c[2].metric("Savings rate", f"{(saved / income * 100) if income else 0:.0f}%")
if len(df):
    st.bar_chart(df.groupby("category")["amount"].sum())

snapshot = json.dumps({"income": income, "savings_goal": goal, "currency": cur,
                       "expenses": df.groupby("category")["amount"].sum().to_dict()})
tabs = st.tabs(["📊 Budget analysis", "🛍️ Recommendations", "💬 Ask about spending"])

with tabs[0]:
    if st.button("Analyze my budget", type="primary"):
        with st.spinner("Analyzing..."):
            st.session_state.analysis = ask(
                f"Analyze this monthly budget: {snapshot}. Categorize spending as needs/wants, suggest a realistic "
                'budget and ways to reach the savings goal. Return JSON: {"summary": str, "health_score": int 0-100, '
                '"budget_plan": [{"category": str, "current": number, "recommended": number, "reason": str}], '
                '"tips": [str], "goal_feasibility": str}', SYSTEM, json_mode=True)
    a = st.session_state.get("analysis")
    if a:
        st.metric("Budget health score", f"{a['health_score']}/100")
        st.info(a["summary"])
        plan = pd.DataFrame(a["budget_plan"])
        st.bar_chart(plan.set_index("category")[["current", "recommended"]])
        st.dataframe(plan, hide_index=True)
        st.success(a["goal_feasibility"])
        st.markdown("**Saving tips**\n" + "\n".join(f"- {t}" for t in a["tips"]))
        report = a["summary"] + "\n\n" + plan.to_string(index=False) + "\n\nTips:\n" + "\n".join(f"- {t}" for t in a["tips"])
        st.download_button("⬇️ Download report (PDF)", make_pdf("PocketSmart Budget Report", report), "budget_report.pdf")

with tabs[1]:
    q = st.text_input("What do you want to buy / decide?", placeholder="e.g. a laptop for college, a phone under my budget")
    b = st.number_input(f"Budget for this purchase ({cur})", 0.0, value=30000.0, step=1000.0)
    pref = st.text_input("Preferences (optional)", placeholder="brand, must-have features...")
    if st.button("Recommend") and q.strip():
        with st.spinner("Finding options..."):
            st.session_state.recs = ask(
                f"User finances: {snapshot}. Purchase wanted: {q}. Budget {cur}{b}. Preferences: {pref}. Recommend 3-5 "
                'options within budget. Prices are estimates. Return JSON: {"advice": str, "recommendations": [{"item": str, '
                '"approx_price": number, "why": str, "tradeoff": str}]}', SYSTEM, json_mode=True)
    r = st.session_state.get("recs")
    if r:
        st.info(r["advice"])
        for x in r["recommendations"]:
            with st.container(border=True):
                st.markdown(f"**{x['item']}** - ~{cur}{x['approx_price']:,.0f}")
                st.write(x["why"])
                st.caption(f"Trade-off: {x['tradeoff']}")
        st.caption("Prices are AI estimates. Check current prices before buying.")

with tabs[2]:
    st.session_state.setdefault("fchat", [])
    for m in st.session_state.fchat:
        st.chat_message(m["role"]).write(m["content"])
    if msg := st.chat_input("Ask about your spending, saving, or budgeting..."):
        st.session_state.fchat.append({"role": "user", "content": msg})
        st.chat_message("user").write(msg)
        reply = chat_reply(st.session_state.fchat, SYSTEM + f" User's budget data: {snapshot}")
        if reply:
            st.session_state.fchat.append({"role": "assistant", "content": reply})
            st.chat_message("assistant").write(reply)
