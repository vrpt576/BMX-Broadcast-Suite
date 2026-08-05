# Upgrading Between Versions

1. Stop BBS and OBS Browser Sources if practical.
2. Back up `.env`, custom themes, and `data/`.
3. Commit or stash local source changes.
4. Pull or extract the new release.
5. Re-run the installer or update dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r connectorequirements.txt
```

```bash
./.venv/bin/python -m pip install -r connector/requirements.txt
```

6. On Windows MSI installations, start BBS once; missing supported keys are
   appended to the protected ProgramData `.env` without replacing existing
   values. Source installations should compare `connector/.env.example` with
   `.env` and add missing keys manually.
7. Run tests if developing: `pytest`.
8. Start BBS, open `/diagnostics`, then test all overlays in demo mode.
9. Keep the previous release ZIP until the event is complete.

Never overwrite `.env` with the example file during an upgrade.
