# Развёртывание на Windows без Python (мини‑ПК ФФО‑4)

## 1) Сборка на вашей машине (где есть Python)

Из папки `qrpass_client`:

```powershell
.\package_windows_release.ps1 -ExeName QRPassClient
```

Готовый комплект появится в `release\qrpass_client_ffo4_release\`.

## 2) Что копировать на мини‑ПК

Скопируйте всю папку `release\qrpass_client_ffo4_release\` на новый Windows‑ПК.

В ней уже есть:

- `QRPassClient\...` или `QRPassClient.exe` (в зависимости от режима сборки)
- `.env` (создан из `.env.example`)
- `run_client.bat`
- `update_cameras_ffo4_from_xlsx.sql` (если был создан)
- `best.pt` (если лежал рядом при сборке)

## 3) Настройка на мини‑ПК

1. Отредактируйте `.env`:
   - `SERVER_URL=...`
   - `API_TOKEN=...`
   - `USE_MDB_CAMERAS=true`
   - `MDB_PARENT_DIR=...` (каталог с `users.db`/`mdb.py`, если используете этот режим)
2. Запустите `run_client.bat`.

## 4) Автозапуск после перезагрузки Windows

Самый простой способ: `Win + R` -> `shell:startup` и положить туда ярлык на `run_client.bat`.

## 5) Важные замечания

- Python на мини‑ПК **не нужен**.
- Может понадобиться Microsoft Visual C++ Redistributable (обычно уже установлен; если exe не стартует — поставьте `VC_redist.x64`).
- На некоторых антивирусах первый запуск может быть медленным из-за проверки нового exe.
