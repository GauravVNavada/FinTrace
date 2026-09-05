# Monthly synthetic exports

Eight self-contained periods: January–August 2026. Each monthly folder contains seven CSV/XLSX exports covering sales, invoices, payments, settlements, refunds, inventory movements, and employee actions.

1. Start FinTrace and create a close for the selected calendar month.
2. Upload all seven CSV/XLSX files from that month's folder together.
3. Wait for “All files understood”, then choose **Run close**.
4. Open Results and investigate the findings. AI uses the configured live provider; incomplete evidence remains unresolved.

Do not upload this README or `manifest.json`. Each period has its own source identifiers; do not mix months in one close. Successful identical uploads are deduplicated. These are synthetic records, not real transactions.

Inventory values use cost, not customer sales/refund values. The files include healthy lifecycles and intentional operational mismatches; anomalies are expected findings, not file-format failures. March includes missing inventory return, quantity mismatch, and ambiguous payment evidence.

`manifest.json` records the SHA-256 and size of every input file. Files were copied byte-for-byte from the original monthly collection; original files were not modified. No hidden answer labels are included in upload folders. API acceptance tests exercise all eight periods from this directory without depending on a personal Desktop path.
