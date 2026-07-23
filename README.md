# NRGAnalytics

Qlik Sense (Qlik Cloud) load scripts for Electro Market / NRG analytics apps.
1C-sourced QVDs (Russian names) → Georgian field names → per-app data models.

- **Architecture, conventions, and gotchas:** see [CLAUDE.md](CLAUDE.md)
- **Direction plans design record:** see [docs/direction-plans.md](docs/direction-plans.md)

Scripts are grouped by app prefix (`SD`, `Sales`, `Stock`, `Debitors`, `Cashflow`, `Credits`,
`Accounting`, `Statement`); each app's master `.qvs` includes the numbered files from
`lib://Holding:DataFiles`. **Local edits take effect only after uploading the changed `.qvs`
files there and reloading the app.**
