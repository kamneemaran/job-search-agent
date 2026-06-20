# User Preferences

## Job Filtering
Filter out these role types in `daily_scan.py` → `PROFILE["title_red_flags"]`:
- **Mobile:** android, ios, swift, kotlin
- **Frontend:** frontend, front-end, front end, ui engineer, web engineer
- **QA:** qa, qa engineer, quality assurance, quality engineer, test engineer, sdet, automation engineer
- **Network/SRE:** network infrastructure, network engineer, network architect, sre, site reliability engineer, devops, devops engineer

## Tracker Statuses
- `new` - not yet applied
- `applied` - application submitted (skipped in future scans)
- `rejected` - not moving forward or not relevant (skipped in future scans)
- `offer` - offer received

## Google Sheet
- Sheet: `job_matches` at https://docs.google.com/spreadsheets/d/1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg/edit
- "Resume" column replaced with "Company Link" (career page or LinkedIn company URL)
