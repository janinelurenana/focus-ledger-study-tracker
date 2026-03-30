"""
StudyTracker CLI — Stage 2
SQLite-backed terminal program to log study sessions and manage study plans.
"""

import os
from datetime import datetime

import pandas as pd
import database as database
import analysis as analysis
import visualization


# ── Helper utilities ──────────────────────────────────────────────────────────

def separator(char="─", width=50):
    print(char * width)

def header(title):
    separator()
    print(f"  {title}")
    separator()

def parse_date(date_str):
    """Try to parse a date string. Returns a date object or None."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_time(time_str):
    """
    Try to parse a HH:MM time string. Returns a datetime.time or None.
    Accepts both 09:30 and 9:30.
    """
    for fmt in ("%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(time_str.strip(), fmt).time()
        except (ValueError, AttributeError):
            continue
    return None


def time_to_minutes(t) -> int:
    """Convert a datetime.time to total minutes since midnight."""
    return t.hour * 60 + t.minute


def check_overlap(date: str, start: str, end: str) -> list[dict]:
    """
    Return any existing entries on `date` whose time window overlaps
    the proposed [start, end) window.

    Overlap condition: existing.start < new.end AND existing.end > new.start
    This catches all four overlap cases (partial left, partial right,
    contained within, contains entirely).
    """
    existing = database.get_entries_by_date(date)
    overlaps = []

    new_start = time_to_minutes(parse_time(start))
    new_end   = time_to_minutes(parse_time(end))

    for entry in existing:
        e_start = time_to_minutes(parse_time(entry["start_time"]))
        e_end   = time_to_minutes(parse_time(entry["end_time"]))
        if e_start < new_end and e_end > new_start:
            overlaps.append(entry)

    return overlaps


# ── Overdue checker ───────────────────────────────────────────────────────────

def check_overdue():
    """Print a warning if any pending plans are past their due date."""
    today = datetime.today().date()
    plans = database.get_all_plans()

    overdue = [
        plan for plan in plans
        if plan["status"] == "pending" and parse_date(plan["due_date"]) is not None
        and today > parse_date(plan["due_date"])
    ]

    if overdue:
        print(f"  ⚠  You have {len(overdue)} overdue plan(s):")
        for plan in overdue:
            print(f"     - {plan['subject']} ({plan['goal'] or 'no goal set'})")
        print()


# ── Feature 1: Add a study entry ─────────────────────────────────────────────

def add_study_entry():
    header("ADD STUDY ENTRY")
    subject      = input("  Subject             : ").strip()
    date_str     = input("  Date (YYYY-MM-DD, Enter = today): ").strip()
    start_str    = input("  Start time (HH:MM)  : ").strip()
    end_str      = input("  End time   (HH:MM)  : ").strip()
    accomplished = input("  Accomplished        : ").strip()
    next_goal    = input("  Next goal           : ").strip()

    # ── Validate subject ──
    if not subject:
        print("  ⚠  Subject cannot be empty. Entry not saved.\n")
        return

    # ── Validate / default date ──
    if not date_str:
        date_str = datetime.today().strftime("%Y-%m-%d")
    elif parse_date(date_str) is None:
        print("  ⚠  Invalid date format. Use YYYY-MM-DD. Entry not saved.\n")
        return

    # ── Validate start and end time ──
    start_time = parse_time(start_str)
    end_time   = parse_time(end_str)

    if start_time is None:
        print("  ⚠  Invalid start time. Use HH:MM (e.g. 09:30). Entry not saved.\n")
        return
    if end_time is None:
        print("  ⚠  Invalid end time. Use HH:MM (e.g. 11:00). Entry not saved.\n")
        return

    # ── Calculate hours — reject negative or zero sessions ──
    hours = (time_to_minutes(end_time) - time_to_minutes(start_time)) / 60

    if hours <= 0:
        print("  ⚠  End time must be after start time. Entry not saved.\n")
        return

    # ── Overlap detection ──
    overlapping = check_overlap(date_str, start_str, end_str)
    if overlapping:
        print(f"\n  ⚠  Warning: this session overlaps with {len(overlapping)} existing entry(s):")
        for e in overlapping:
            print(f"     - {e['id']}  {e['subject']}  {e['start_time']}–{e['end_time']}")
        confirm = input("\n  Save anyway? (y/N): ").strip().lower()
        if confirm != "y":
            print("  Entry not saved.\n")
            return

    entry = {
        "id"          : database.next_entry_id(),
        "date"        : date_str,
        "start_time"  : start_time.strftime("%H:%M"),
        "end_time"    : end_time.strftime("%H:%M"),
        "subject"     : subject,
        "hours"       : round(hours, 4),
        "accomplished": accomplished,
        "next_goal"   : next_goal,
        "created_at"  : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    database.insert_entry(entry)
    print(f"\n  ✓  Entry {entry['id']} saved — {hours:.2f}h for '{subject}'.\n")


# ── Feature 2: Add a study plan ──────────────────────────────────────────────

def add_study_plan():
    header("ADD STUDY PLAN")
    subject      = input("  Subject       : ").strip()
    target_hours = input("  Target hours  : ").strip()
    goal         = input("  Goal          : ").strip()
    due_date     = input("  Due date (YYYY-MM-DD): ").strip()

    if not subject:
        print("  ⚠  Subject cannot be empty. Plan not saved.\n")
        return

    if due_date and parse_date(due_date) is None:
        print("  ⚠  Invalid date format. Use YYYY-MM-DD (e.g. 2025-06-01).\n")
        return

    plan = {
        "id"            : database.next_plan_id(),
        "subject"       : subject,
        "target_hours"  : target_hours,
        "goal"          : goal,
        "due_date"      : due_date,
        "status"        : "pending",
        "completed_date": "",
    }
    database.insert_plan(plan)
    print(f"\n  ✓  Plan {plan['id']} saved for '{subject}'.\n")


# ── Feature 3: View study log ─────────────────────────────────────────────────

def view_study_log():
    header("STUDY LOG")
    entries = database.get_all_entries()

    if not entries:
        print("  No study entries yet.\n")
        return

    for entry in entries:
        print(f"  [{entry['id']}]  {entry.get('date', '—')}  "
              f"{entry.get('start_time', '?')}–{entry.get('end_time', '?')}")
        print(f"      Subject      : {entry['subject']}")
        print(f"      Hours        : {entry['hours'] or '—'}")
        print(f"      Accomplished : {entry['accomplished'] or '—'}")
        print(f"      Next goal    : {entry['next_goal'] or '—'}")
        print(f"      Logged at    : {entry.get('created_at') or '—'}")
        separator("·", 50)
    print()


# ── Feature 4: View study plan ────────────────────────────────────────────────

def view_study_plan():
    header("STUDY PLAN")
    plans = database.get_all_plans()

    if not plans:
        print("  No study plans yet.\n")
        return

    today = datetime.today().date()

    for plan in plans:
        if plan["status"] == "completed":
            badge = "✅ completed"
        else:
            due = parse_date(plan["due_date"])
            badge = "⚠  OVERDUE" if (due and today > due) else "🔵 pending"

        print(f"  [{plan['id']}]  [{badge}]")
        print(f"      Subject        : {plan['subject']}")
        print(f"      Target hours   : {plan['target_hours'] or '—'}")
        print(f"      Goal           : {plan['goal'] or '—'}")
        print(f"      Due date       : {plan['due_date'] or '—'}")
        if plan["status"] == "completed":
            print(f"      Completed date : {plan.get('completed_date') or '—'}")
        separator("·", 50)
    print()


# ── Feature 5: Complete a study plan ─────────────────────────────────────────

def complete_study_plan():
    header("COMPLETE STUDY PLAN")
    plans   = database.get_all_plans()
    pending = [(i, p) for i, p in enumerate(plans) if p["status"] == "pending"]

    if not pending:
        print("  No pending plans to complete.\n")
        return

    for display_num, (_, plan) in enumerate(pending, start=1):
        print(f"  [{display_num}] {plan['id']}  {plan['subject']}"
              f"  |  Goal: {plan['goal'] or '—'}"
              f"  |  Due: {plan['due_date'] or '—'}")
    separator("·", 50)

    choice = input("  Mark plan # as done (or 0 to cancel): ").strip()

    if choice == "0":
        print("  Cancelled.\n")
        return

    if not choice.isdigit() or not (1 <= int(choice) <= len(pending)):
        print("  ⚠  Invalid number. No changes made.\n")
        return

    _, chosen_plan = pending[int(choice) - 1]
    today = datetime.today().strftime("%Y-%m-%d")
    database.update_plan_status(chosen_plan["id"], "completed", today)

    print(f"\n  ✓  {chosen_plan['id']} '{chosen_plan['subject']}' marked as completed.\n")


# ── Feature 5b: Edit a study plan ────────────────────────────────────────────

def edit_study_plan():
    header("EDIT STUDY PLAN")
    plans    = database.get_all_plans()
    editable = [(i, p) for i, p in enumerate(plans) if p["status"] == "pending"]

    if not editable:
        print("  No plans available to edit.\n")
        return

    for display_num, (_, plan) in enumerate(editable, start=1):
        print(f"  [{display_num}] {plan['id']}  {plan['subject']}"
              f"  |  Hours: {plan['target_hours'] or '—'}"
              f"  |  Due: {plan['due_date'] or '—'}")
    separator("·", 50)

    choice = input("  Edit plan # (or 0 to cancel): ").strip()

    if choice == "0":
        print("  Cancelled.\n")
        return

    if not choice.isdigit() or not (1 <= int(choice) <= len(editable)):
        print("  ⚠  Invalid number. No changes made.\n")
        return

    _, chosen_plan = editable[int(choice) - 1]

    separator("·", 50)
    print(f"  Editing: {chosen_plan['id']} — {chosen_plan['subject']}")
    separator("·", 50)
    print(f"  1.  Target hours  (current: {chosen_plan['target_hours'] or '—'})")
    print(f"  2.  Due date      (current: {chosen_plan['due_date'] or '—'})")
    print(f"  3.  Goal          (current: {chosen_plan['goal'] or '—'})")
    separator("·", 50)

    field_choice = input("  Which field? [1-3]: ").strip()

    if field_choice == "1":
        current_val = chosen_plan["target_hours"]
        new_val = input(f"  New target hours (Enter to keep '{current_val}'): ").strip()
        if not new_val:
            print("  No change made.\n")
            return
        database.update_plan_field(chosen_plan["id"], "target_hours", new_val)
        print(f"\n  ✓  Target hours updated to '{new_val}'.\n")

    elif field_choice == "2":
        current_val = chosen_plan["due_date"]
        new_val = input(f"  New due date (Enter to keep '{current_val}'): ").strip()
        if not new_val:
            print("  No change made.\n")
            return
        if parse_date(new_val) is None:
            print("  ⚠  Invalid date format. Use YYYY-MM-DD. No changes made.\n")
            return
        database.update_plan_field(chosen_plan["id"], "due_date", new_val)
        print(f"\n  ✓  Due date updated to '{new_val}'.\n")

    elif field_choice == "3":
        current_val = chosen_plan["goal"]
        new_val = input(f"  New goal (Enter to keep '{current_val}'): ").strip()
        if not new_val:
            print("  No change made.\n")
            return
        database.update_plan_field(chosen_plan["id"], "goal", new_val)
        print(f"\n  ✓  Goal updated to '{new_val}'.\n")

    else:
        print("  ⚠  Invalid field choice. No changes made.\n")



def view_all_activity():
    header("ALL ACTIVITY — TIMELINE")

    timeline = []

    for entry in database.get_all_entries():
        timeline.append({
            "kind"   : "entry",
            "id"     : entry["id"],
            "date"   : entry.get("date", ""),
            "subject": entry["subject"],
            "hours"  : entry.get("hours") or "—",
            "detail" : entry.get("accomplished") or "—",
            "next"   : entry.get("next_goal") or "—",
        })

    for plan in database.get_all_plans():
        if plan["status"] == "completed":
            timeline.append({
                "kind"   : "plan",
                "id"     : plan["id"],
                "date"   : plan.get("completed_date") or plan.get("due_date", ""),
                "subject": plan["subject"],
                "hours"  : plan.get("target_hours") or "—",
                "detail" : plan.get("goal") or "—",
                "next"   : None,
            })

    if not timeline:
        print("  No activity to show yet.\n")
        return

    timeline.sort(key=lambda x: x["date"] or "0000-00-00", reverse=True)

    for item in timeline:
        date_label = item["date"] or "unknown date"

        if item["kind"] == "entry":
            print(f"  📝 STUDY ENTRY     ·  {item['id']}  ·  {date_label}")
        else:
            print(f"  ✅ COMPLETED PLAN  ·  {item['id']}  ·  {date_label}")

        print(f"     Subject : {item['subject']}")
        print(f"     Hours   : {item['hours']}")
        print(f"     Detail  : {item['detail']}")
        if item["next"] is not None:
            print(f"     Next    : {item['next']}")
        separator("·", 50)

    print()


# ── Shared filter prompt ──────────────────────────────────────────────────────

def ask_filter():
    """
    Ask the user to choose a date range.
    Returns (since, label) where since is a pd.Timestamp or None (= all time).
    Pressing Enter defaults to All time.
    """
    separator("·", 50)
    print("  Filter by date range:")
    print("  1.  Last 7 days")
    print("  2.  Last 30 days")
    print("  3.  Last 60 days")
    print("  4.  All time  (default)")
    separator("·", 50)

    choice = input("  Choose [1-4] or Enter for All time: ").strip()
    print()

    today = pd.Timestamp.today().normalize()

    options = {
        "1": (today - pd.Timedelta(days=7),  "Last 7 days"),
        "2": (today - pd.Timedelta(days=30), "Last 30 days"),
        "3": (today - pd.Timedelta(days=60), "Last 60 days"),
        "4": (None,                           "All time"),
    }

    since, label = options.get(choice, (None, "All time"))
    return since, label


# ── Feature 7: Analytics summary ─────────────────────────────────────────────

def show_analytics():
    header("ANALYTICS SUMMARY")
    since, label = ask_filter()
    print(f"  Showing: {label}\n")
    analysis.print_full_summary(since)


# ── Feature 8: Visualization dashboard ───────────────────────────────────────

def show_visualization():
    header("VISUALIZATION DASHBOARD")
    combined = analysis.load_combined()
    if combined.empty:
        print("  No data yet — add study entries or complete a plan first.\n")
        return
    since, label = ask_filter()
    print(f"  Opening dashboard [{label}]...\n")
    import matplotlib.pyplot as plt
    fig = visualization.show_dashboard(since, label)
    plt.show()


# ── Main menu loop ────────────────────────────────────────────────────────────

def show_menu():
    separator("═", 50)
    print("  📚  STUDY TRACKER")
    separator("═", 50)
    check_overdue()
    print("  1.   Add study entry")
    print("  2.   Add study plan")
    print("  3.   View study log")
    print("  4.   View study plan")
    print("  5.   Complete a study plan")
    print("  6.   Edit a study plan")
    print("  7.   View all activity")
    print("  8.   Analytics")
    print("  9.   Visualize")
    print("  10.  Exit")
    separator("─", 50)

def main():
    database.init_db()   # create tables + migrate CSVs on first run
    print()
    while True:
        show_menu()
        choice = input("  Choose [1-10]: ").strip()
        print()

        if   choice == "1":  add_study_entry()
        elif choice == "2":  add_study_plan()
        elif choice == "3":  view_study_log()
        elif choice == "4":  view_study_plan()
        elif choice == "5":  complete_study_plan()
        elif choice == "6":  edit_study_plan()
        elif choice == "7":  view_all_activity()
        elif choice == "8":  show_analytics()
        elif choice == "9":  show_visualization()
        elif choice == "10":
            print("  Goodbye! Keep studying. 👋\n")
            break
        else:
            print("  ⚠  Invalid choice. Please enter a number from 1 to 10.\n")


if __name__ == "__main__":
    main()