"""
HMIS Data Quality Analyzer
===========================
A configurable validation tool that checks HMIS CSV export data against
HUD Universal Data Element standards. Flags missing required fields,
validates date logic, checks value ranges, and generates summary reports
with error trending.

Author: James Calby
License: MIT

Usage:
    python hmis_data_quality_analyzer.py --input client_export.csv --config config.json
    python hmis_data_quality_analyzer.py --input client_export.csv --program SSVF
"""

import csv
import json
import sys
import os
from datetime import datetime, date
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# HUD Universal Data Element Definitions
# These map to the HMIS Data Standards Manual required elements.
# ---------------------------------------------------------------------------

HUD_REQUIRED_FIELDS = {
    "universal": [
        "PersonalID",
        "FirstName",
        "LastName",
        "DOB",
        "SSN",
        "Gender",
        "Race",
        "Ethnicity",
        "VeteranStatus",
        "EntryDate",
        "ProjectType",
        "RelationshipToHoH",
        "EnrollmentID",
        "HouseholdID",
    ],
    "entry": [
        "PriorLivingSituation",
        "LengthOfStay",
        "DisablingCondition",
        "MonthlyIncome",
        "IncomeFromAnySource",
        "InsuranceFromAnySource",
        "DomesticViolenceSurvivor",
    ],
    "exit": [
        "ExitDate",
        "Destination",
        "DestinationType",
    ],
}

# Valid HUD response codes for key fields
VALID_VALUES = {
    "Gender": [0, 1, 2, 3, 4, 5, 8, 9, 99],
    "Race": [1, 2, 3, 4, 5, 8, 9, 99],
    "Ethnicity": [0, 1, 8, 9, 99],
    "VeteranStatus": [0, 1, 8, 9, 99],
    "DisablingCondition": [0, 1, 8, 9, 99],
    "RelationshipToHoH": [1, 2, 3, 4, 5, 99],
    "IncomeFromAnySource": [0, 1, 8, 9, 99],
    "InsuranceFromAnySource": [0, 1, 8, 9, 99],
    "DomesticViolenceSurvivor": [0, 1, 8, 9, 99],
    "Destination": list(range(1, 36)) + [8, 9, 17, 24, 30, 37, 99],
}

# Program type codes per HUD
PROGRAM_TYPES = {
    1: "Emergency Shelter - Entry/Exit",
    2: "Transitional Housing",
    3: "PH - Permanent Supportive Housing",
    4: "Street Outreach",
    6: "Services Only",
    7: "Other",
    8: "Safe Haven",
    9: "PH - Housing Only",
    10: "PH - Housing with Services",
    11: "Day Shelter",
    12: "Homelessness Prevention",
    13: "PH - Rapid Re-Housing",
    14: "Coordinated Entry",
}


class ValidationError:
    """Represents a single data quality error."""

    def __init__(
        self,
        record_id: str,
        field: str,
        error_type: str,
        message: str,
        severity: str = "error",
    ):
        self.record_id = record_id
        self.field = field
        self.error_type = error_type
        self.message = message
        self.severity = severity  # "error", "warning", "info"
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "field": self.field,
            "error_type": self.error_type,
            "message": self.message,
            "severity": self.severity,
        }


class HMISDataQualityAnalyzer:
    """
    Main analyzer class. Loads CSV data, validates against HUD standards,
    and produces a structured quality report.
    """

    def __init__(self, config: Optional[dict] = None):
        self.errors: List[ValidationError] = []
        self.records: List[dict] = []
        self.config = config or {}
        self.stats = {
            "total_records": 0,
            "records_with_errors": 0,
            "total_errors": 0,
            "errors_by_field": Counter(),
            "errors_by_type": Counter(),
            "errors_by_severity": Counter(),
            "completeness_by_field": {},
        }

    def load_csv(self, filepath: str) -> None:
        """Load HMIS export CSV into memory."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Input file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.records = [row for row in reader]

        self.stats["total_records"] = len(self.records)
        print(f"Loaded {len(self.records)} records from {filepath}")

    def _add_error(
        self,
        record_id: str,
        field: str,
        error_type: str,
        message: str,
        severity: str = "error",
    ) -> None:
        """Register a validation error."""
        err = ValidationError(record_id, field, error_type, message, severity)
        self.errors.append(err)
        self.stats["errors_by_field"][field] += 1
        self.stats["errors_by_type"][error_type] += 1
        self.stats["errors_by_severity"][severity] += 1

    # -------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------

    def validate_required_fields(self, record: dict, field_set: str = "universal") -> None:
        """Check that all required fields are present and non-empty."""
        record_id = record.get("PersonalID", "UNKNOWN")
        fields = HUD_REQUIRED_FIELDS.get(field_set, [])

        for field in fields:
            value = record.get(field, "").strip()
            if not value:
                self._add_error(
                    record_id,
                    field,
                    "missing_required",
                    f"Required field '{field}' is blank or missing.",
                    "error",
                )

    def validate_date_fields(self, record: dict) -> None:
        """Validate date logic: DOB in past, EntryDate <= ExitDate, etc."""
        record_id = record.get("PersonalID", "UNKNOWN")
        today = date.today()

        # Date of birth
        dob_raw = record.get("DOB", "").strip()
        entry_raw = record.get("EntryDate", "").strip()
        exit_raw = record.get("ExitDate", "").strip()

        dob = self._parse_date(dob_raw)
        entry_date = self._parse_date(entry_raw)
        exit_date = self._parse_date(exit_raw)

        if dob_raw and dob is None:
            self._add_error(
                record_id, "DOB", "invalid_format",
                f"DOB '{dob_raw}' is not a valid date format.",
            )
        elif dob and dob > today:
            self._add_error(
                record_id, "DOB", "future_date",
                "Date of birth is in the future.",
            )
        elif dob and (today.year - dob.year) > 120:
            self._add_error(
                record_id, "DOB", "implausible_date",
                "Date of birth implies age over 120 years.",
                "warning",
            )

        if entry_raw and entry_date is None:
            self._add_error(
                record_id, "EntryDate", "invalid_format",
                f"EntryDate '{entry_raw}' is not a valid date format.",
            )

        if exit_raw and exit_date is None:
            self._add_error(
                record_id, "ExitDate", "invalid_format",
                f"ExitDate '{exit_raw}' is not a valid date format.",
            )

        # Entry must be before or equal to exit
        if entry_date and exit_date and entry_date > exit_date:
            self._add_error(
                record_id, "ExitDate", "date_logic",
                "ExitDate is before EntryDate.",
            )

        # Entry should not be in the future
        if entry_date and entry_date > today:
            self._add_error(
                record_id, "EntryDate", "future_date",
                "EntryDate is in the future.",
                "warning",
            )

    def validate_value_ranges(self, record: dict) -> None:
        """Check that coded fields contain valid HUD response values."""
        record_id = record.get("PersonalID", "UNKNOWN")

        for field, valid_codes in VALID_VALUES.items():
            raw = record.get(field, "").strip()
            if not raw:
                continue  # Missing values handled by required field check

            try:
                code = int(float(raw))
            except (ValueError, TypeError):
                self._add_error(
                    record_id, field, "invalid_value",
                    f"Value '{raw}' is not a valid numeric code for {field}.",
                )
                continue

            if code not in valid_codes:
                self._add_error(
                    record_id, field, "out_of_range",
                    f"Value '{code}' is not a valid HUD response code for {field}.",
                )

    def validate_ssn(self, record: dict) -> None:
        """Check SSN format and flag known invalid patterns."""
        record_id = record.get("PersonalID", "UNKNOWN")
        ssn = record.get("SSN", "").strip().replace("-", "")

        if not ssn:
            return  # Handled by required field check

        if len(ssn) != 9 or not ssn.isdigit():
            self._add_error(
                record_id, "SSN", "invalid_format",
                "SSN is not 9 digits.",
                "warning",
            )
            return

        # Flag known invalid SSNs
        invalid_patterns = ["000000000", "111111111", "999999999", "123456789"]
        if ssn in invalid_patterns:
            self._add_error(
                record_id, "SSN", "placeholder_value",
                "SSN appears to be a placeholder value.",
                "warning",
            )

        if ssn.startswith("9"):
            self._add_error(
                record_id, "SSN", "invalid_format",
                "SSN starting with 9 is reserved for ITINs.",
                "info",
            )

    def validate_veteran_status(self, record: dict) -> None:
        """Cross-check veteran status with age."""
        record_id = record.get("PersonalID", "UNKNOWN")
        vet_raw = record.get("VeteranStatus", "").strip()
        dob_raw = record.get("DOB", "").strip()

        if not vet_raw or not dob_raw:
            return

        try:
            vet_status = int(float(vet_raw))
        except (ValueError, TypeError):
            return

        dob = self._parse_date(dob_raw)
        if dob and vet_status == 1:
            age = (date.today() - dob).days // 365
            if age < 17:
                self._add_error(
                    record_id, "VeteranStatus", "logical_inconsistency",
                    f"Client marked as veteran but age is {age}.",
                    "warning",
                )

    # -------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Try multiple date formats."""
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except (ValueError, AttributeError):
                continue
        return None

    # -------------------------------------------------------------------
    # Main Analysis Pipeline
    # -------------------------------------------------------------------

    def run_analysis(self, program_filter: Optional[str] = None) -> dict:
        """Run all validations and return structured results."""
        records_to_check = self.records

        if program_filter:
            records_to_check = [
                r for r in self.records
                if r.get("ProjectType", "").strip() == program_filter
                or r.get("ProgramName", "").strip().upper() == program_filter.upper()
            ]
            print(f"Filtered to {len(records_to_check)} records for '{program_filter}'")

        errored_records = set()

        for record in records_to_check:
            record_id = record.get("PersonalID", "UNKNOWN")
            errors_before = len(self.errors)

            # Run validation suite
            self.validate_required_fields(record, "universal")
            self.validate_required_fields(record, "entry")
            self.validate_date_fields(record)
            self.validate_value_ranges(record)
            self.validate_ssn(record)
            self.validate_veteran_status(record)

            # Check if client has been exited
            if record.get("ExitDate", "").strip():
                self.validate_required_fields(record, "exit")

            if len(self.errors) > errors_before:
                errored_records.add(record_id)

        self.stats["total_errors"] = len(self.errors)
        self.stats["records_with_errors"] = len(errored_records)

        # Calculate field completeness
        if records_to_check:
            all_fields = set()
            for fl in HUD_REQUIRED_FIELDS.values():
                all_fields.update(fl)

            for field in all_fields:
                filled = sum(
                    1 for r in records_to_check if r.get(field, "").strip()
                )
                self.stats["completeness_by_field"][field] = round(
                    (filled / len(records_to_check)) * 100, 1
                )

        return self._build_report()

    def _build_report(self) -> dict:
        """Generate the final structured report."""
        total = self.stats["total_records"]
        errored = self.stats["records_with_errors"]
        clean_pct = round(((total - errored) / total * 100), 1) if total else 0

        report = {
            "summary": {
                "total_records": total,
                "records_with_errors": errored,
                "clean_records": total - errored,
                "clean_percentage": clean_pct,
                "total_errors": self.stats["total_errors"],
            },
            "errors_by_field": dict(self.stats["errors_by_field"].most_common()),
            "errors_by_type": dict(self.stats["errors_by_type"].most_common()),
            "errors_by_severity": dict(self.stats["errors_by_severity"]),
            "completeness_by_field": dict(
                sorted(
                    self.stats["completeness_by_field"].items(),
                    key=lambda x: x[1],
                )
            ),
            "errors": [e.to_dict() for e in self.errors],
        }

        return report

    def print_summary(self, report: dict) -> None:
        """Print a human-readable summary to console."""
        s = report["summary"]
        print("\n" + "=" * 60)
        print("  HMIS DATA QUALITY REPORT")
        print("=" * 60)
        print(f"  Total Records Analyzed:   {s['total_records']}")
        print(f"  Records with Errors:      {s['records_with_errors']}")
        print(f"  Clean Records:            {s['clean_records']}")
        print(f"  Clean Percentage:         {s['clean_percentage']}%")
        print(f"  Total Errors Found:       {s['total_errors']}")
        print("-" * 60)

        if report["errors_by_field"]:
            print("\n  Top Error Fields:")
            for field, count in list(report["errors_by_field"].items())[:10]:
                bar = "█" * min(count, 40)
                print(f"    {field:<30} {count:>5}  {bar}")

        if report["completeness_by_field"]:
            print("\n  Field Completeness (lowest first):")
            for field, pct in list(report["completeness_by_field"].items())[:10]:
                bar_len = int(pct / 2.5)
                bar = "█" * bar_len + "░" * (40 - bar_len)
                print(f"    {field:<30} {pct:>6.1f}%  {bar}")

        print("\n" + "=" * 60)

    def export_errors_csv(self, filepath: str) -> None:
        """Export all errors to a CSV file for further analysis."""
        if not self.errors:
            print("No errors to export.")
            return

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["record_id", "field", "error_type", "message", "severity"],
            )
            writer.writeheader()
            for err in self.errors:
                writer.writerow(err.to_dict())

        print(f"Exported {len(self.errors)} errors to {filepath}")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="HMIS Data Quality Analyzer - Validate HMIS exports against HUD standards"
    )
    parser.add_argument("--input", required=True, help="Path to HMIS CSV export file")
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument("--program", help="Filter by program name or type code")
    parser.add_argument("--output", help="Export errors to CSV file")
    parser.add_argument(
        "--json", action="store_true", help="Output full report as JSON"
    )

    args = parser.parse_args()

    # Load config if provided
    config = {}
    if args.config:
        with open(args.config, "r") as f:
            config = json.load(f)

    # Run analysis
    analyzer = HMISDataQualityAnalyzer(config=config)
    analyzer.load_csv(args.input)
    report = analyzer.run_analysis(program_filter=args.program)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        analyzer.print_summary(report)

    if args.output:
        analyzer.export_errors_csv(args.output)


if __name__ == "__main__":
    main()
