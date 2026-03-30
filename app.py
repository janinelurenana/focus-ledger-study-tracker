"""
app.py — Streamlit UI for StudyTracker
Run with: streamlit run app.py
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from datetime import datetime, date, time

import analysis
import database
import visualization

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="FocusLedger",
    page_icon="📚",
    layout="wide",
)

database.init_db()

# ── Sidebar navigation ────────────────────────────────────────────────────────

st.sidebar.title("📚 Study Tracker")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    [
        "📝 Add Study Entry",
        "📋 Add Study Plan",
        "📖 Study Log",
        "🗂  Study Plans",
        "🕒 All Activity",
        "📊 Analytics",
        "📈 Dashboard",
    ],
    label_visibility="collapsed",
)

# ── Shared filter (Analytics + Dashboard) ────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.markdown("**Date filter**")
filter_choice = st.sidebar.selectbox(
    "Date range",
    ["All time", "Last 7 days", "Last 30 days", "Last 60 days"],
    label_visibility="collapsed",
)

filter_map = {
    "All time"    : None,
    "Last 7 days" : pd.Timestamp.today() - pd.Timedelta(days=7),
    "Last 30 days": pd.Timestamp.today() - pd.Timedelta(days=30),
    "Last 60 days": pd.Timestamp.today() - pd.Timedelta(days=60),
}
since = filter_map[filter_choice]

# ── Overdue warning (shown on every page if applicable) ──────────────────────

@st.cache_data(ttl=60)
def _get_plans_cached():
    """Cache plan list for 60s to avoid a DB query on every Streamlit rerun."""
    return database.get_all_plans()


def show_overdue_banner():
    today = datetime.today().date()
    plans = _get_plans_cached()
    overdue = [
        p for p in plans
        if p["status"] == "pending" and p["due_date"]
        and today > datetime.strptime(p["due_date"], "%Y-%m-%d").date()
    ]
    if overdue:
        names = ", ".join(f"**{p['subject']}**" for p in overdue)
        st.warning(f"⚠️  You have {len(overdue)} overdue plan(s): {names}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Add Study Entry
# ══════════════════════════════════════════════════════════════════════════════

if page == "📝 Add Study Entry":
    st.title("Add Study Entry")
    show_overdue_banner()

    with st.form("entry_form", clear_on_submit=True):
        subject      = st.text_input("Subject")
        entry_date   = st.date_input("Date", value=date.today())
        col1, col2   = st.columns(2)
        start_time   = col1.time_input("Start time", value=time(9, 0))
        end_time     = col2.time_input("End time",   value=time(10, 0))
        accomplished = st.text_area("What did you accomplish?", height=80)
        next_goal    = st.text_input("Next goal")
        submitted    = st.form_submit_button("Save Entry")

    if submitted:
        # Validate subject
        if not subject.strip():
            st.error("Subject cannot be empty.")
        elif len(subject.strip()) > 100:
            st.error("Subject must be 100 characters or fewer.")
        # Validate time order
        elif end_time <= start_time:
            st.error("End time must be after start time.")

        else:
            # Calculate hours
            start_mins = start_time.hour * 60 + start_time.minute
            end_mins   = end_time.hour   * 60 + end_time.minute
            hours      = round((end_mins - start_mins) / 60, 4)

            # Overlap check
            date_str    = entry_date.strftime("%Y-%m-%d")
            start_str   = start_time.strftime("%H:%M")
            end_str     = end_time.strftime("%H:%M")
            existing    = database.get_entries_by_date(date_str)

            overlapping = [
                e for e in existing
                if e["start_time"] and e["end_time"]
                and int(e["start_time"].replace(":", "")[:2]) * 60
                 + int(e["start_time"][3:5])
                 < end_mins
                and int(e["end_time"].replace(":", "")[:2]) * 60
                 + int(e["end_time"][3:5])
                 > start_mins
            ]

            if overlapping:
                st.warning(
                    f"⚠️  This session overlaps with "
                    f"{len(overlapping)} existing entry(s): "
                    + ", ".join(f"{e['id']} {e['subject']} "
                                f"({e['start_time']}–{e['end_time']})"
                                for e in overlapping)
                )
                st.info("Entry saved anyway. Edit or review in Study Log if needed.")

            entry = {
                "id"          : database.next_entry_id(),
                "date"        : date_str,
                "start_time"  : start_str,
                "end_time"    : end_str,
                "subject"     : subject.strip(),
                "hours"       : hours,
                "accomplished": accomplished.strip(),
                "next_goal"   : next_goal.strip(),
                "created_at"  : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            database.insert_entry(entry)
            st.success(f"✅ Entry **{entry['id']}** saved — **{hours:.2f}h** for **{subject}**.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Add Study Plan
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Add Study Plan":
    st.title("Add Study Plan")
    show_overdue_banner()

    with st.form("plan_form", clear_on_submit=True):
        subject      = st.text_input("Subject")
        target_hours = st.number_input("Target hours", min_value=0.0, step=0.5)
        goal         = st.text_input("Goal")
        due_date     = st.date_input("Due date", value=None)
        submitted    = st.form_submit_button("Save Plan")

    if submitted:
        if not subject.strip():
            st.error("Subject cannot be empty.")
        elif len(subject.strip()) > 100:
            st.error("Subject must be 100 characters or fewer.")
        else:
            plan = {
                "id"            : database.next_plan_id(),
                "subject"       : subject.strip(),
                "target_hours"  : target_hours,
                "goal"          : goal.strip(),
                "due_date"      : due_date.strftime("%Y-%m-%d") if due_date else "",
                "status"        : "pending",
                "completed_date": "",
            }
            database.insert_plan(plan)
            st.success(f"✅ Plan **{plan['id']}** saved for **{subject}**.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Study Log
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📖 Study Log":
    st.title("Study Log")
    entries = database.get_all_entries()

    if not entries:
        st.info("No study entries yet. Add your first session!")
    else:
        # Summary metric row
        total_hours   = sum(float(e["hours"] or 0) for e in entries)
        total_entries = len(entries)
        subjects      = len({e["subject"] for e in entries})

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Sessions", total_entries)
        c2.metric("Total Hours",    f"{total_hours:.1f}h")
        c3.metric("Subjects",       subjects)

        st.markdown("---")

        # Entries table — newest first
        df = pd.DataFrame(entries)
        df = df[["id", "date", "start_time", "end_time",
                 "subject", "hours", "accomplished", "next_goal", "created_at"]]
        df.columns = ["ID", "Date", "Start", "End",
                      "Subject", "Hours", "Accomplished", "Next Goal", "Logged At"]
        df = df.sort_values("Date", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Study Plans
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🗂  Study Plans":
    st.title("Study Plans")
    show_overdue_banner()

    plans = database.get_all_plans()

    if not plans:
        st.info("No study plans yet.")
    else:
        today = date.today()

        for plan in plans:
            if plan["status"] == "completed":
                badge = "✅ Completed"
            elif plan["due_date"] and today > datetime.strptime(plan["due_date"], "%Y-%m-%d").date():
                badge = "⚠️ Overdue"
            else:
                badge = "🔵 Pending"

            with st.expander(f"{plan['id']} — {plan['subject']}  |  {badge}"):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Goal:** {plan['goal'] or '—'}")
                c1.markdown(f"**Target hours:** {plan['target_hours'] or '—'}")
                c2.markdown(f"**Due date:** {plan['due_date'] or '—'}")
                c2.markdown(f"**Status:** {plan['status'].capitalize()}")
                if plan["status"] == "completed":
                    c2.markdown(f"**Completed:** {plan['completed_date']}")

                st.markdown("---")

                if plan["status"] == "pending":
                    col_a, col_c = st.columns([1, 3])

                    if col_a.button("Mark complete", key=f"complete_{plan['id']}"):
                        database.update_plan_status(
                            plan["id"], "completed",
                            datetime.today().strftime("%Y-%m-%d")
                        )
                        st.success(f"**{plan['subject']}** marked as completed!")
                        st.rerun()

                    # Inline edit fields
                    with st.popover("✏️ Edit"):
                        new_hours = st.number_input(
                            "Target hours",
                            value=float(plan["target_hours"] or 0),
                            step=0.5,
                            key=f"hrs_{plan['id']}"
                        )
                        new_goal = st.text_input(
                            "Goal",
                            value=plan["goal"] or "",
                            key=f"goal_{plan['id']}"
                        )
                        new_due = st.date_input(
                            "Due date",
                            value=datetime.strptime(plan["due_date"], "%Y-%m-%d").date()
                                  if plan["due_date"] else None,
                            key=f"due_{plan['id']}"
                        )
                        if st.button("Save changes", key=f"save_{plan['id']}"):
                            database.update_plan_field(plan["id"], "target_hours", str(new_hours))
                            database.update_plan_field(plan["id"], "goal", new_goal)
                            database.update_plan_field(
                                plan["id"], "due_date",
                                new_due.strftime("%Y-%m-%d") if new_due else ""
                            )
                            st.success("Plan updated.")
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: All Activity
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🕒 All Activity":
    st.title("All Activity")

    timeline = []

    for e in database.get_all_entries():
        timeline.append({
            "Type"       : "📝 Entry",
            "ID"         : e["id"],
            "Date"       : e["date"],
            "Time"       : f"{e.get('start_time','?')}–{e.get('end_time','?')}",
            "Subject"    : e["subject"],
            "Hours"      : e["hours"],
            "Detail"     : e.get("accomplished") or "—",
            "Next Goal"  : e.get("next_goal") or "—",
        })

    for p in database.get_all_plans():
        if p["status"] == "completed":
            timeline.append({
                "Type"       : "✅ Plan",
                "ID"         : p["id"],
                "Date"       : p.get("completed_date") or p.get("due_date") or "—",
                "Time"       : "—",
                "Subject"    : p["subject"],
                "Hours"      : p["target_hours"],
                "Detail"     : p.get("goal") or "—",
                "Next Goal"  : "—",
            })

    if not timeline:
        st.info("No activity yet.")
    else:
        df = pd.DataFrame(timeline)
        df = df.sort_values("Date", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Analytics
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Analytics":
    st.title("Analytics")
    st.caption(f"Showing: **{filter_choice}**")

    # ── Hours per subject ──
    st.subheader("Total hours per subject")
    result = analysis.hours_per_subject(since)
    if result is not None and not result.empty:
        st.bar_chart(result)
    else:
        st.info("No data.")

    st.markdown("---")

    # ── Weekly totals ──
    st.subheader("Weekly study totals")
    weekly = analysis.weekly_totals(since)
    if weekly is not None and not weekly.empty:
        weekly.index = [w.strftime("%b %d") for w in weekly.index]
        st.line_chart(weekly)
    else:
        st.info("No data.")

    st.markdown("---")

    # ── Average study time ──
    st.subheader("Average study time")
    avg = analysis.average_study_time(since)
    if avg:
        c1, c2 = st.columns(2)
        c1.metric("Avg per session", f"{avg['overall_avg']:.2f}h")
        c2.metric("Avg per study day", f"{avg['daily_avg']:.2f}h")
        st.dataframe(
            avg["subject_avg"].rename("Avg hours").reset_index(),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No data.")

    st.markdown("---")

    # ── Streak (always full history) ──
    st.subheader("Study streak")
    s = analysis.streak()
    if s:
        c1, c2, c3 = st.columns(3)
        c1.metric("Current streak", f"{s['current']} day(s)")
        c2.metric("Longest streak", f"{s['longest']} day(s)")
        c3.metric("Last studied",   str(s["last_date"]))
    else:
        st.info("No data.")

    st.markdown("---")

    # ── Plan completion rate (always full history) ──
    st.subheader("Plan completion rate")
    rate = analysis.plan_completion_rate()
    if rate:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total plans",     rate["total"])
        c2.metric("Completed",       rate["completed"])
        c3.metric("Completion rate", f"{rate['rate']:.0f}%")
        st.progress(min(rate["rate"] / 100, 1.0))
    else:
        st.info("No plans yet.")

    st.markdown("---")

    # ── Peak study hours ──
    st.subheader("Peak study hours")
    peak = analysis.peak_study_hours(since)
    if peak is not None and peak.sum() > 0:
        peak.index = [f"{h:02d}:00" for h in peak.index]
        st.bar_chart(peak)
    else:
        st.info("No time-of-day data yet.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard (charts)
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📈 Dashboard":
    st.title("Dashboard")
    st.caption(f"Showing: **{filter_choice}**")

    combined = analysis.load_combined(since)
    if combined.empty:
        st.info("No data yet — add study entries or complete a plan first.")
    else:
        fig = visualization.show_dashboard(since, filter_choice)
        st.pyplot(fig)
        plt.close(fig)   # free memory after rendering
