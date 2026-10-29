# Local database files

The application creates `geneglass.db` in this directory by default.
SQLite database files are intentionally ignored by Git because they contain
local runtime data. The schema is recreated safely with:

```powershell
python -m app.db.init_db
```
