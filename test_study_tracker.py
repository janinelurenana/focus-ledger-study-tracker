"""
test_study_tracker.py — Edge case & unit tests for StudyTracker CLI
Run with: python -m pytest test_study_tracker.py -v
"""

import csv
import os
import pytest
import tempfile
import shutil
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch

# ── Point the app at a temp data directory before importing ──────────────────
# We monkey-patch the module-level path constants so tests never touch real data.

import study_tracker
import analysis


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    """
    Redirect all file I/O to a fresh temp directory for every test.
    Resets in-memory lists too so tests are fully isolated.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Patch path constants in both modules
    study_tracker.DATA_DIR      = str(data_dir)
    study_tracker.ENTRIES_FILE  = str(data_dir / "study_entries.csv")
    study_tracker.PLANS_FILE    = str(data_dir / "study_plans.csv")
    analysis.DATA_DIR           = str(data_dir)
    analysis.ENTRIES_FILE       = str(data_dir / "study_entries.csv")
    analysis.PLANS_FILE         = str(data_dir / "study_plans.csv")

    # Reset in-memory stores
    study_tracker.study_log   = []
    study_tracker.study_plan  = []

    # Initialise fresh CSV files
    study_tracker.init_storage()
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Storage & ID generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestStorage:

    def test_init_creates_csv_files(self, tmp_path):
        """init_storage() creates both CSVs with correct headers."""
        assert os.path.exists(study_tracker.ENTRIES_FILE)
        assert os.path.exists(study_tracker.PLANS_FILE)

        with open(study_tracker.ENTRIES_FILE) as f:
            headers = csv.DictReader(f).fieldnames
        assert headers == study_tracker.ENTRIES_FIELDS

    def test_init_is_idempotent(self):
        """Calling init_storage() twice doesn't overwrite existing data."""
        study_tracker.study_log = []
        with patch("builtins.input", side_effect=["Python", "2", "Read ch1", "Do ch2"]):
            study_tracker.add_study_entry()

        study_tracker.init_storage()   # second call — should not wipe the file
        study_tracker.load_data()
        assert len(study_tracker.study_log) == 1

    def test_load_data_repopulates_lists(self):
        """load_data() reads CSVs back into in-memory lists correctly."""
        with patch("builtins.input", side_effect=["Python", "2", "Read ch1", "Do ch2"]):
            study_tracker.add_study_entry()

        study_tracker.study_log = []   # wipe memory
        study_tracker.load_data()
        assert len(study_tracker.study_log) == 1
        assert study_tracker.study_log[0]["subject"] == "Python"

    def test_entry_id_increments(self):
        """Entry IDs increment correctly: E001, E002, E003."""
        for i in range(3):
            with patch("builtins.input", side_effect=[f"Subject{i}", "1", "done", "next"]):
                study_tracker.add_study_entry()

        ids = [e["id"] for e in study_tracker.study_log]
        assert ids == ["E001", "E002", "E003"]

    def test_plan_id_increments(self):
        """Plan IDs increment correctly and are prefixed P, not E."""
        for i in range(2):
            with patch("builtins.input", side_effect=[f"Subject{i}", "10", "goal", "2099-12-31"]):
                study_tracker.add_study_plan()

        ids = [p["id"] for p in study_tracker.study_plan]
        assert ids == ["P001", "P002"]

    def test_entry_and_plan_ids_never_collide(self):
        """E001 and P001 are different IDs — prefixes keep them distinct."""
        with patch("builtins.input", side_effect=["Python", "2", "done", "next"]):
            study_tracker.add_study_entry()
        with patch("builtins.input", side_effect=["Python", "10", "goal", "2099-12-31"]):
            study_tracker.add_study_plan()

        assert study_tracker.study_log[0]["id"]  == "E001"
        assert study_tracker.study_plan[0]["id"] == "P001"
        assert study_tracker.study_log[0]["id"] != study_tracker.study_plan[0]["id"]

    def test_id_generation_after_reload(self):
        """IDs continue from correct number after app restart (load_data)."""
        for _ in range(3):
            with patch("builtins.input", side_effect=["Python", "1", "done", "next"]):
                study_tracker.add_study_entry()

        study_tracker.study_log = []
        study_tracker.load_data()

        with patch("builtins.input", side_effect=["Python", "1", "done", "next"]):
            study_tracker.add_study_entry()

        assert study_tracker.study_log[-1]["id"] == "E004"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — add_study_entry
# ═══════════════════════════════════════════════════════════════════════════════

class TestAddStudyEntry:

    def test_valid_entry_is_saved(self):
        with patch("builtins.input", side_effect=["Python", "2.5", "Read docs", "Try examples"]):
            study_tracker.add_study_entry()
        assert len(study_tracker.study_log) == 1
        assert study_tracker.study_log[0]["subject"] == "Python"

    def test_date_is_auto_captured(self):
        today = datetime.today().strftime("%Y-%m-%d")
        with patch("builtins.input", side_effect=["Python", "1", "done", "next"]):
            study_tracker.add_study_entry()
        assert study_tracker.study_log[0]["date"] == today

    def test_empty_subject_rejected(self, capsys):
        with patch("builtins.input", side_effect=["", "1", "done", "next"]):
            study_tracker.add_study_entry()
        assert len(study_tracker.study_log) == 0
        assert "cannot be empty" in capsys.readouterr().out

    def test_whitespace_only_subject_rejected(self, capsys):
        with patch("builtins.input", side_effect=["   ", "1", "done", "next"]):
            study_tracker.add_study_entry()
        assert len(study_tracker.study_log) == 0

    def test_optional_fields_can_be_blank(self):
        """Hours, accomplished, next_goal are all optional — blank is fine."""
        with patch("builtins.input", side_effect=["Python", "", "", ""]):
            study_tracker.add_study_entry()
        assert len(study_tracker.study_log) == 1

    def test_non_numeric_hours_stored_as_string(self):
        """Non-numeric hours don't crash the save — analysis handles coercion."""
        with patch("builtins.input", side_effect=["Python", "two hours", "done", "next"]):
            study_tracker.add_study_entry()
        assert study_tracker.study_log[0]["hours"] == "two hours"

    def test_entry_persisted_to_csv(self):
        with patch("builtins.input", side_effect=["Python", "3", "done", "next"]):
            study_tracker.add_study_entry()

        study_tracker.study_log = []
        study_tracker.load_data()
        assert study_tracker.study_log[0]["subject"] == "Python"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — add_study_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestAddStudyPlan:

    def test_valid_plan_is_saved(self):
        with patch("builtins.input", side_effect=["Networking", "20", "OSPF lab", "2099-12-31"]):
            study_tracker.add_study_plan()
        assert len(study_tracker.study_plan) == 1
        assert study_tracker.study_plan[0]["status"] == "pending"

    def test_completed_date_blank_on_create(self):
        with patch("builtins.input", side_effect=["Networking", "20", "goal", "2099-12-31"]):
            study_tracker.add_study_plan()
        assert study_tracker.study_plan[0]["completed_date"] == ""

    def test_empty_subject_rejected(self, capsys):
        with patch("builtins.input", side_effect=["", "10", "goal", "2099-12-31"]):
            study_tracker.add_study_plan()
        assert len(study_tracker.study_plan) == 0

    def test_invalid_date_format_rejected(self, capsys):
        with patch("builtins.input", side_effect=["Networking", "10", "goal", "31-12-2099"]):
            study_tracker.add_study_plan()
        assert len(study_tracker.study_plan) == 0
        assert "Invalid date" in capsys.readouterr().out

    def test_blank_due_date_allowed(self):
        """Due date is optional — blank should be accepted."""
        with patch("builtins.input", side_effect=["Networking", "10", "goal", ""]):
            study_tracker.add_study_plan()
        assert len(study_tracker.study_plan) == 1

    def test_plan_in_the_past_allowed(self):
        """Past due dates are valid — overdue detection happens at display time."""
        with patch("builtins.input", side_effect=["Old subject", "5", "goal", "2020-01-01"]):
            study_tracker.add_study_plan()
        assert len(study_tracker.study_plan) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — complete_study_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompleteStudyPlan:

    def _add_plan(self, subject="Python", due="2099-12-31"):
        with patch("builtins.input", side_effect=[subject, "10", "goal", due]):
            study_tracker.add_study_plan()

    def test_completing_plan_sets_status(self):
        self._add_plan()
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()
        assert study_tracker.study_plan[0]["status"] == "completed"

    def test_completing_plan_stamps_completed_date(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._add_plan()
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()
        assert study_tracker.study_plan[0]["completed_date"] == today

    def test_completing_plan_persists_to_csv(self):
        self._add_plan()
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()

        study_tracker.study_plan = []
        study_tracker.load_data()
        assert study_tracker.study_plan[0]["status"] == "completed"

    def test_cancel_with_zero(self):
        self._add_plan()
        with patch("builtins.input", return_value="0"):
            study_tracker.complete_study_plan()
        assert study_tracker.study_plan[0]["status"] == "pending"

    def test_invalid_choice_no_change(self, capsys):
        self._add_plan()
        with patch("builtins.input", return_value="99"):
            study_tracker.complete_study_plan()
        assert study_tracker.study_plan[0]["status"] == "pending"
        assert "Invalid" in capsys.readouterr().out

    def test_no_pending_plans_message(self, capsys):
        """If all plans are completed, show a clear message."""
        self._add_plan()
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()
        # Try to complete again — should say no pending plans
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()
        assert "No pending" in capsys.readouterr().out

    def test_complete_one_of_multiple_plans(self):
        """Completing plan 2 of 3 should only affect that plan."""
        for subj in ["Python", "Networking", "Linux"]:
            self._add_plan(subject=subj)
        with patch("builtins.input", return_value="2"):
            study_tracker.complete_study_plan()

        statuses = [p["status"] for p in study_tracker.study_plan]
        assert statuses == ["pending", "completed", "pending"]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — edit_study_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestEditStudyPlan:

    def _add_plan(self):
        with patch("builtins.input", side_effect=["Python", "10", "goal", "2099-06-01"]):
            study_tracker.add_study_plan()

    def test_edit_target_hours(self):
        self._add_plan()
        # Pick plan 1, field 1 (target_hours), new value "20"
        with patch("builtins.input", side_effect=["1", "1", "20"]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["target_hours"] == "20"

    def test_edit_due_date(self):
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "2", "2099-12-31"]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["due_date"] == "2099-12-31"

    def test_edit_goal(self):
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "3", "New goal text"]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["goal"] == "New goal text"

    def test_blank_input_keeps_current_value(self):
        """Pressing Enter without typing anything keeps the existing value."""
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "1", ""]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["target_hours"] == "10"  # unchanged

    def test_blank_due_date_keeps_current_value(self):
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "2", ""]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["due_date"] == "2099-06-01"  # unchanged

    def test_edit_persists_to_csv(self):
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "1", "99"]):
            study_tracker.edit_study_plan()

        study_tracker.study_plan = []
        study_tracker.load_data()
        assert study_tracker.study_plan[0]["target_hours"] == "99"

    def test_edit_invalid_date_rejected(self, capsys):
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "2", "not-a-date"]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["due_date"] == "2099-06-01"  # unchanged
        assert "Invalid date" in capsys.readouterr().out

    def test_edit_cancel_with_zero(self):
        self._add_plan()
        with patch("builtins.input", return_value="0"):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["target_hours"] == "10"  # unchanged

    def test_edit_invalid_field_choice(self, capsys):
        """Entering a field number outside 1-3 should do nothing."""
        self._add_plan()
        with patch("builtins.input", side_effect=["1", "5"]):
            study_tracker.edit_study_plan()
        assert study_tracker.study_plan[0]["target_hours"] == "10"
        assert "Invalid field" in capsys.readouterr().out

    def test_edit_completed_plan_blocked(self, capsys):
        """Completed plans should not be editable."""
        self._add_plan()
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()
        capsys.readouterr()
        with patch("builtins.input", return_value="1"):
            study_tracker.edit_study_plan()
        assert "No plans available" in capsys.readouterr().out

    def test_no_plans_message(self, capsys):
        with patch("builtins.input", return_value="1"):
            study_tracker.edit_study_plan()
        assert "No plans available" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — overdue detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestOverdueDetection:

    def test_past_due_date_flagged(self, capsys):
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with patch("builtins.input", side_effect=["Python", "10", "goal", yesterday]):
            study_tracker.add_study_plan()
        study_tracker.check_overdue()
        assert "overdue" in capsys.readouterr().out.lower()

    def test_future_due_date_not_flagged(self, capsys):
        with patch("builtins.input", side_effect=["Python", "10", "goal", "2099-12-31"]):
            study_tracker.add_study_plan()
        study_tracker.check_overdue()
        assert capsys.readouterr().out == ""

    def test_completed_plan_not_flagged_as_overdue(self, capsys):
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with patch("builtins.input", side_effect=["Python", "10", "goal", yesterday]):
            study_tracker.add_study_plan()
        with patch("builtins.input", return_value="1"):
            study_tracker.complete_study_plan()
        capsys.readouterr()   # clear output from above
        study_tracker.check_overdue()
        assert capsys.readouterr().out == ""

    def test_blank_due_date_not_flagged(self, capsys):
        with patch("builtins.input", side_effect=["Python", "10", "goal", ""]):
            study_tracker.add_study_plan()
        study_tracker.check_overdue()
        assert capsys.readouterr().out == ""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — analysis functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalysis:

    def _seed_entries(self, rows):
        """Write rows directly to the CSV to bypass the CLI."""
        with open(study_tracker.ENTRIES_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=study_tracker.ENTRIES_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        study_tracker.load_data()

    def _seed_plans(self, rows):
        with open(study_tracker.PLANS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=study_tracker.PLANS_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        study_tracker.load_data()

    def test_hours_per_subject_sums_correctly(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": today, "subject": "Python",     "hours": "3", "accomplished": "", "next_goal": ""},
            {"id": "E002", "date": today, "subject": "Python",     "hours": "2", "accomplished": "", "next_goal": ""},
            {"id": "E003", "date": today, "subject": "Networking", "hours": "4", "accomplished": "", "next_goal": ""},
        ])
        result = analysis.hours_per_subject()
        assert result["Python"] == 5.0
        assert result["Networking"] == 4.0

    def test_hours_per_subject_includes_completed_plans(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": today, "subject": "Python", "hours": "3", "accomplished": "", "next_goal": ""},
        ])
        self._seed_plans([
            {"id": "P001", "subject": "Python", "target_hours": "10", "goal": "goal",
             "due_date": today, "status": "completed", "completed_date": today},
        ])
        result = analysis.hours_per_subject()
        assert result["Python"] == 13.0   # 3 entry + 10 plan

    def test_completed_plan_without_completed_date_excluded(self):
        """A plan marked completed but missing completed_date should be ignored."""
        today = datetime.today().strftime("%Y-%m-%d")
        self._seed_plans([
            {"id": "P001", "subject": "Python", "target_hours": "10", "goal": "goal",
             "due_date": today, "status": "completed", "completed_date": ""},
        ])
        result = analysis.hours_per_subject()
        assert result is None   # no data at all

    def test_non_numeric_hours_coerced_to_zero(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": today, "subject": "Python", "hours": "bad", "accomplished": "", "next_goal": ""},
        ])
        result = analysis.hours_per_subject()
        assert result["Python"] == 0.0

    def test_filter_since_excludes_old_data(self):
        old_date   = (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d")
        today      = datetime.today().strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": old_date, "subject": "Python", "hours": "5", "accomplished": "", "next_goal": ""},
            {"id": "E002", "date": today,    "subject": "Python", "hours": "2", "accomplished": "", "next_goal": ""},
        ])
        since  = pd.Timestamp.today() - pd.Timedelta(days=30)
        result = analysis.hours_per_subject(since=since)
        assert result["Python"] == 2.0   # only today's entry

    def test_empty_csv_returns_none(self):
        result = analysis.hours_per_subject()
        assert result is None

    def test_streak_single_day(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": today, "subject": "Python", "hours": "1", "accomplished": "", "next_goal": ""},
        ])
        result = analysis.streak()
        assert result["current"] == 1
        assert result["longest"] == 1

    def test_streak_two_consecutive_days(self):
        today     = datetime.today().strftime("%Y-%m-%d")
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": yesterday, "subject": "Python", "hours": "1", "accomplished": "", "next_goal": ""},
            {"id": "E002", "date": today,     "subject": "Python", "hours": "1", "accomplished": "", "next_goal": ""},
        ])
        result = analysis.streak()
        assert result["current"] == 2
        assert result["longest"] == 2

    def test_streak_broken_by_gap(self):
        today      = datetime.today().strftime("%Y-%m-%d")
        three_ago  = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": three_ago, "subject": "Python", "hours": "1", "accomplished": "", "next_goal": ""},
            {"id": "E002", "date": today,     "subject": "Python", "hours": "1", "accomplished": "", "next_goal": ""},
        ])
        result = analysis.streak()
        assert result["current"] == 1   # gap breaks current
        assert result["longest"] == 1   # neither run was longer than 1

    def test_streak_longest_preserved_after_gap(self):
        """A 3-day run followed by a gap: longest=3, current=1."""
        base = datetime.today() - timedelta(days=10)
        dates = [
            (base + timedelta(days=0)).strftime("%Y-%m-%d"),  # run of 3
            (base + timedelta(days=1)).strftime("%Y-%m-%d"),
            (base + timedelta(days=2)).strftime("%Y-%m-%d"),
            (base + timedelta(days=5)).strftime("%Y-%m-%d"),  # isolated
        ]
        self._seed_entries([
            {"id": f"E00{i+1}", "date": d, "subject": "Python",
             "hours": "1", "accomplished": "", "next_goal": ""}
            for i, d in enumerate(dates)
        ])
        result = analysis.streak()
        assert result["longest"] == 3
        assert result["current"] == 0   # last entry was 10-5=5 days ago

    def test_streak_all_isolated_dates(self):
        """Every date has a gap — longest should be 1, not 0."""
        dates = [
            (datetime.today() - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in [10, 8, 6, 4]
        ]
        self._seed_entries([
            {"id": f"E00{i+1}", "date": d, "subject": "Python",
             "hours": "1", "accomplished": "", "next_goal": ""}
            for i, d in enumerate(dates)
        ])
        result = analysis.streak()
        assert result["longest"] == 1

    def test_streak_yesterday_keeps_current(self):
        """Yesterday counts as active — streak should not reset to 0."""
        yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        self._seed_entries([
            {"id": "E001", "date": yesterday, "subject": "Python", "hours": "1", "accomplished": "", "next_goal": ""},
        ])
        result = analysis.streak()
        assert result["current"] == 1   # not 0

    def test_plan_completion_rate(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._seed_plans([
            {"id": "P001", "subject": "A", "target_hours": "5", "goal": "", "due_date": today, "status": "completed", "completed_date": today},
            {"id": "P002", "subject": "B", "target_hours": "5", "goal": "", "due_date": today, "status": "pending",   "completed_date": ""},
            {"id": "P003", "subject": "C", "target_hours": "5", "goal": "", "due_date": today, "status": "completed", "completed_date": today},
        ])
        result = analysis.plan_completion_rate()
        assert result["total"]     == 3
        assert result["completed"] == 2
        assert abs(result["rate"] - 66.67) < 0.1
