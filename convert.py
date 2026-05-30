#!/usr/bin/env python3
"""Convert WomanLog CSV export to Apple Health XML import format.

Usage:
    python3 convert.py input.csv [output.xml]

Transfer the output XML to your iPhone and open it with
Health Data Importer (Lionheart Software) to import into Apple Health.
"""

import argparse
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_args() -> tuple[Path, Path]:
    parser = argparse.ArgumentParser(description="Convert WomanLog CSV to Apple Health XML")
    parser.add_argument("input", type=Path, help="WomanLog CSV export file")
    parser.add_argument("output", type=Path, nargs="?",
                        help="Output XML file (default: WomanLog_Export.xml next to input)")
    args = parser.parse_args()
    output = args.output or args.input.with_stem("WomanLog_Export").with_suffix(".xml")
    return args.input, output

# Full DOCTYPE as used by Apple Health exports — required for iOS to recognise
# the file as a Health export rather than a clinical/FHIR document.
HEALTH_DOCTYPE = """\
<!DOCTYPE HealthData [
<!ELEMENT HealthData (ExportDate,Me,(Record|Correlation|Workout|ActivitySummary|ClinicalRecord|Audiogram|VisionPrescription)*)>
<!ATTLIST HealthData
  locale CDATA #REQUIRED
>
<!ELEMENT ExportDate EMPTY>
<!ATTLIST ExportDate
  value CDATA #REQUIRED
>
<!ELEMENT Me EMPTY>
<!ATTLIST Me
  HKCharacteristicTypeIdentifierDateOfBirth         CDATA #REQUIRED
  HKCharacteristicTypeIdentifierBiologicalSex        CDATA #REQUIRED
  HKCharacteristicTypeIdentifierBloodType            CDATA #REQUIRED
  HKCharacteristicTypeIdentifierFitzpatrickSkinType  CDATA #REQUIRED
>
<!ELEMENT Record (MetadataEntry*,HeartRateVariabilityMetadataList?)>
<!ATTLIST Record
  type          CDATA #REQUIRED
  unit          CDATA #REQUIRED
  value         CDATA #REQUIRED
  sourceName    CDATA #REQUIRED
  sourceVersion CDATA #IMPLIED
  device        CDATA #IMPLIED
  creationDate  CDATA #IMPLIED
  startDate     CDATA #REQUIRED
  endDate       CDATA #REQUIRED
>
<!ELEMENT MetadataEntry EMPTY>
<!ATTLIST MetadataEntry
  key   CDATA #REQUIRED
  value CDATA #REQUIRED
>
<!ELEMENT HeartRateVariabilityMetadataList (InstantaneousBeatsPerMinute*)>
<!ELEMENT InstantaneousBeatsPerMinute EMPTY>
<!ATTLIST InstantaneousBeatsPerMinute
  bpm  CDATA #REQUIRED
  time CDATA #REQUIRED
>
<!ELEMENT Workout (MetadataEntry*,WorkoutEvent*,WorkoutRoute?)>
<!ATTLIST Workout
  workoutActivityType   CDATA #REQUIRED
  duration              CDATA #IMPLIED
  durationUnit          CDATA #IMPLIED
  totalDistance         CDATA #IMPLIED
  totalDistanceUnit     CDATA #IMPLIED
  totalEnergyBurned     CDATA #IMPLIED
  totalEnergyBurnedUnit CDATA #IMPLIED
  sourceName            CDATA #REQUIRED
  sourceVersion         CDATA #IMPLIED
  device                CDATA #IMPLIED
  creationDate          CDATA #IMPLIED
  startDate             CDATA #REQUIRED
  endDate               CDATA #REQUIRED
>
<!ELEMENT WorkoutEvent EMPTY>
<!ATTLIST WorkoutEvent
  type         CDATA #REQUIRED
  date         CDATA #REQUIRED
  duration     CDATA #IMPLIED
  durationUnit CDATA #IMPLIED
>
<!ELEMENT WorkoutRoute (MetadataEntry*,FileReference*)>
<!ATTLIST WorkoutRoute
  sourceName    CDATA #REQUIRED
  sourceVersion CDATA #IMPLIED
  device        CDATA #IMPLIED
  creationDate  CDATA #IMPLIED
  startDate     CDATA #REQUIRED
  endDate       CDATA #REQUIRED
>
<!ELEMENT FileReference EMPTY>
<!ATTLIST FileReference
  path CDATA #REQUIRED
>
<!ELEMENT ActivitySummary EMPTY>
<!ATTLIST ActivitySummary
  dateComponents         CDATA #IMPLIED
  activeEnergyBurned     CDATA #IMPLIED
  activeEnergyBurnedGoal CDATA #IMPLIED
  activeEnergyBurnedUnit CDATA #IMPLIED
  appleExerciseTime      CDATA #IMPLIED
  appleExerciseTimeGoal  CDATA #IMPLIED
  appleStandHours        CDATA #IMPLIED
  appleStandHoursGoal    CDATA #IMPLIED
>
<!ELEMENT ClinicalRecord EMPTY>
<!ATTLIST ClinicalRecord
  type             CDATA #REQUIRED
  identifier       CDATA #REQUIRED
  sourceName       CDATA #REQUIRED
  sourceURL        CDATA #REQUIRED
  fhirVersion      CDATA #REQUIRED
  receivedDate     CDATA #REQUIRED
  resourceFilePath CDATA #REQUIRED
>
<!ELEMENT Correlation (MetadataEntry*,Record*)>
<!ATTLIST Correlation
  type          CDATA #REQUIRED
  sourceName    CDATA #REQUIRED
  sourceVersion CDATA #IMPLIED
  device        CDATA #IMPLIED
  creationDate  CDATA #IMPLIED
  startDate     CDATA #REQUIRED
  endDate       CDATA #REQUIRED
>
]>"""

# Symptom name → (HKCategoryType, HKCategoryValue)
SYMPTOM_MAP = {
    "Abdominal pain":       ("HKCategoryTypeIdentifierAbdominalCramps",     "HKCategoryValueSeverityUnspecified"),
    "Colic":                ("HKCategoryTypeIdentifierAbdominalCramps",     "HKCategoryValueSeverityUnspecified"),
    "Cramps":               ("HKCategoryTypeIdentifierAbdominalCramps",     "HKCategoryValueSeverityUnspecified"),
    "Pelvic cramping":      ("HKCategoryTypeIdentifierPelvicPain",          "HKCategoryValueSeverityUnspecified"),
    "Pain in the groin":    ("HKCategoryTypeIdentifierPelvicPain",          "HKCategoryValueSeverityUnspecified"),
    "Ovulation pain":       ("HKCategoryTypeIdentifierPelvicPain",          "HKCategoryValueSeverityUnspecified"),
    "Ovulation pain left":  ("HKCategoryTypeIdentifierPelvicPain",          "HKCategoryValueSeverityUnspecified"),
    "Ovulation pain right": ("HKCategoryTypeIdentifierPelvicPain",          "HKCategoryValueSeverityUnspecified"),
    "Sacrum pain":          ("HKCategoryTypeIdentifierLowerBackPain",       "HKCategoryValueSeverityUnspecified"),
    "Backaches":            ("HKCategoryTypeIdentifierLowerBackPain",       "HKCategoryValueSeverityUnspecified"),
    "Body aches":           ("HKCategoryTypeIdentifierGeneralizedBodyAche", "HKCategoryValueSeverityUnspecified"),
    "Breast pain":          ("HKCategoryTypeIdentifierBreastPain",          "HKCategoryValueSeverityUnspecified"),
    "Bloating":             ("HKCategoryTypeIdentifierBloating",            "HKCategoryValueSeverityUnspecified"),
    "Hot flashes":          ("HKCategoryTypeIdentifierHotFlashes",          "HKCategoryValueSeverityUnspecified"),
    "Indigestion":          ("HKCategoryTypeIdentifierNausea",              "HKCategoryValueSeverityUnspecified"),
    "Chills":               ("HKCategoryTypeIdentifierChills",              "HKCategoryValueSeverityUnspecified"),
    "Dizziness":            ("HKCategoryTypeIdentifierDizziness",           "HKCategoryValueSeverityUnspecified"),
    "Pms":                  ("HKCategoryTypeIdentifierMoodChanges",         "HKCategoryValueSeverityUnspecified"),
    "Appetite":             ("HKCategoryTypeIdentifierAppetiteChanges",     "HKCategoryValueAppetiteChangesUnspecified"),
    "Cravings":             ("HKCategoryTypeIdentifierAppetiteChanges",     "HKCategoryValueAppetiteChangesIncreased"),
    "Cravings salty":       ("HKCategoryTypeIdentifierAppetiteChanges",     "HKCategoryValueAppetiteChangesIncreased"),
    "Cravings sweet":       ("HKCategoryTypeIdentifierAppetiteChanges",     "HKCategoryValueAppetiteChangesIncreased"),
    "Malaise":              ("HKCategoryTypeIdentifierFatigue",             "HKCategoryValueSeverityUnspecified"),
    "Flatulence":           ("HKCategoryTypeIdentifierBloating",            "HKCategoryValueSeverityUnspecified"),
}

DATE_FMT = "%Y-%m-%d 12:00:00 +0200"


def fmt_day(d: datetime) -> tuple[str, str]:
    ts = d.strftime(DATE_FMT)
    return ts, ts  # startDate == endDate, as in real Apple Health exports


def add_record(root, rtype, unit, start, end, value, metadata=None):
    rec = ET.SubElement(root, "Record", {
        "type": rtype,
        "sourceName": "WomanLog",
        "unit": unit,
        "creationDate": start,
        "startDate": start,
        "endDate": end,
        "value": value,
    })
    if metadata:
        for k, v in metadata.items():
            ET.SubElement(rec, "MetadataEntry", {"key": k, "value": str(v)})


def build_xml(input_csv: Path) -> tuple[bytes, int, dict]:
    root = ET.Element("HealthData", {"locale": "en_US"})
    ET.SubElement(root, "ExportDate", {
        "value": datetime.now().strftime(DATE_FMT)
    })
    ET.SubElement(root, "Me", {
        "HKCharacteristicTypeIdentifierDateOfBirth": "",
        "HKCharacteristicTypeIdentifierBiologicalSex": "HKBiologicalSexFemale",
        "HKCharacteristicTypeIdentifierBloodType": "HKBloodTypeNotSet",
        "HKCharacteristicTypeIdentifierFitzpatrickSkinType": "HKFitzpatrickSkinTypeNotSet",
    })

    n_records = 0
    skipped: dict[str, int] = {}

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = datetime.strptime(row["Date"].strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            rtype = row["Type"].strip()
            value = (row["Value"] or "").strip()

            if rtype == "Start period":
                duration = int(value) if value else 1
                for i in range(duration):
                    s, e = fmt_day(date + timedelta(days=i))
                    add_record(root, "HKCategoryTypeIdentifierMenstrualFlow",
                               "", s, e, "HKCategoryValueVaginalBleedingUnspecified",
                               {"HKMenstrualCycleStart": "1" if i == 0 else "0"})
                    n_records += 1

            elif rtype == "Ovulation":
                s, e = fmt_day(date)
                add_record(root, "HKCategoryTypeIdentifierOvulationTestResult",
                           "", s, e, "HKCategoryValueOvulationTestResultPositive")
                n_records += 1

            elif rtype == "Weight":
                s, e = fmt_day(date)
                add_record(root, "HKQuantityTypeIdentifierBodyMass",
                           "kg", s, e, value)
                n_records += 1

            elif rtype == "Symptom":
                if value == "Spotting bleeding":
                    s, e = fmt_day(date)
                    add_record(root, "HKCategoryTypeIdentifierIntermenstrualBleeding",
                               "", s, e, "HKCategoryValueNotApplicable")
                    n_records += 1
                elif value == "Menstruation flow":
                    s, e = fmt_day(date)
                    add_record(root, "HKCategoryTypeIdentifierMenstrualFlow",
                               "", s, e, "HKCategoryValueVaginalBleedingUnspecified")
                    n_records += 1
                elif value in SYMPTOM_MAP:
                    hk_type, hk_value = SYMPTOM_MAP[value]
                    s, e = fmt_day(date)
                    add_record(root, hk_type, "", s, e, hk_value,
                               {"HKMetadataKeyNote": value})
                    n_records += 1
                else:
                    skipped[value] = skipped.get(value, 0) + 1

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")

    xml_bytes = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + HEALTH_DOCTYPE + "\n"
        + body
    ).encode("utf-8")

    return xml_bytes, n_records, skipped


def main():
    input_csv, output_xml = parse_args()
    xml_bytes, n_records, skipped = build_xml(input_csv)

    output_xml.write_bytes(xml_bytes)

    print(f"Wrote {n_records} records → {output_xml}")
    if skipped:
        print("Skipped (no Apple Health mapping):")
        for sym, count in sorted(skipped.items()):
            print(f"  {sym!r}: {count}×")


if __name__ == "__main__":
    main()
