# NRGAnalytics

Qlik Sense (Qlik Cloud) load scripts for Electro Market / NRG analytics apps.
1C-sourced QVDs (Russian names) → Georgian field names → per-app data models.

- **Architecture, conventions, and gotchas:** see [CLAUDE.md](CLAUDE.md)
- **Direction plans design record:** see [docs/direction-plans.md](docs/direction-plans.md)
- **P&L source query (1C):** see [docs/pl.txt](docs/pl.txt) — the original analyst query whose
  register+journal logic the SD 0206 script reimplements (its header comment refers to it as
  pl.txt). Reference only, never executed. Full 1C config dump: `D:\NRG` (clone of
  [Sabissimo/NRG1C](https://github.com/Sabissimo/NRG1C)).

Scripts are grouped by app prefix (`SD`, `Sales`, `Stock`, `Debitors`, `Cashflow`, `Credits`,
`Accounting`, `Statement`); each app's master `.qvs` includes the numbered files from
`lib://Holding:DataFiles`. **Local edits take effect only after uploading the changed `.qvs`
files there and reloading the app.**
