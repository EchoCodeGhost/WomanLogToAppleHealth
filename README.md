# WomanLog → Apple Health

Converts a WomanLog CSV export to Apple Health format so you can import your historical period data into the iOS Health app's Cycle Calendar.

## What gets imported

| WomanLog data | Apple Health |
|---|---|
| Period start + duration | Menstrual Flow (one entry per day, cycle start marked) |
| Spotting bleeding | Intermenstrual Bleeding |
| Ovulation | Ovulation Test Result (Positive) |
| Weight | Body Mass |
| Abdominal pain, Cramps, Colic | Abdominal Cramps |
| Pelvic cramping, Ovulation pain, Pain in the groin | Pelvic Pain |
| Sacrum pain, Backaches | Lower Back Pain |
| Body aches | Generalized Body Ache |
| Breast pain | Breast Pain |
| Bloating, Flatulence | Bloating |
| Hot flashes | Hot Flashes |
| Indigestion | Nausea |
| Chills | Chills |
| Dizziness | Dizziness |
| PMS | Mood Changes |
| Malaise | Fatigue (closest equivalent) |
| Appetite | Appetite Changes (Unspecified) |
| Cravings, Cravings salty, Cravings sweet | Appetite Changes (Increased) |

The original WomanLog symptom name is preserved as a note (`HKMetadataKeyNote`) on each record, so no detail is lost even when multiple symptoms share the same Apple Health type.

All WomanLog symptom types are mapped.

## Requirements

- Python 3.9+
- A WomanLog CSV export (Menu → Export data → CSV)
- **Health Data Importer** by Lionheart Software LLC ([App Store](https://apps.apple.com/app/health-data-importer/id1158733998)) — free download, ~3 € one-time IAP to unlock full import

## Usage

1. Export your data from WomanLog: **Menu → Export data → CSV**
2. Run:
   ```bash
   python3 convert.py /path/to/womanlog_export.csv
   ```
   This creates `WomanLog_Export.xml` next to the input file. You can optionally specify a different output path:
   ```bash
   python3 convert.py input.csv output.xml
   ```
3. Transfer `WomanLog_Export.xml` to your iPhone (AirDrop, Nextcloud, iCloud Drive, email…)
4. Open the file with **Health Data Importer** → grant HealthKit permissions → import

The data appears in **Health → Cycle Tracking** (Zykluskalender).

## Why not just "Share → Health"?

The iOS Health app's Share Sheet only accepts clinical FHIR/CDA documents from healthcare providers — not Apple Health's own export format. That path always gives the error *"Klinische Dokumente können nicht importiert werden"*. Health Data Importer bypasses this limitation by writing directly to HealthKit.

## Format notes (for developers)

A few non-obvious requirements discovered by comparing against a real Apple Health export:

- **MenstrualFlow value**: must be `HKCategoryValueVaginalBleedingUnspecified` (not the older `HKCategoryValueMenstrualFlowUnspecified`)
- **Cycle start key**: `HKMenstrualCycleStart` (not `HKMetadataKeyMenstrualCycleStart`)
- **startDate must equal endDate** for all category records — spanning to the next day causes the entry to be ignored
- The XML must have a full `<!DOCTYPE HealthData [...]>` declaration — without it iOS misidentifies the file as a clinical document
