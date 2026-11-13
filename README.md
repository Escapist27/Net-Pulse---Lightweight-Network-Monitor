# NetPulse — Lightweight Network Monitor

Лёгкий монитор сети с графическим интерфейсом. Добавляешь устройства (имя + IP/хост),
задаёшь период — программа пингует их с выбранным интервалом и фиксирует каждый обрыв
связи: когда начался, когда закончился и сколько длился. Лог (`.log`) и отчёт (`.json`)
сохраняются в выбранную папку.

*A lightweight GUI network monitor: pings your devices on an interval and records every
outage (start, end, duration). Interface in Russian and English.*

## Установка на Windows 10/11

Скачайте `NetPulse-Setup-x.y.z.exe` со страницы **[Releases](../../releases)** и запустите.
Права администратора не обязательны.

- Настройки: `%APPDATA%\NetPulse\netpulse_config.json`
- Логи по умолчанию: `Документы\NetPulse\logs` (папку можно сменить в настройках)

## Запуск из исходников (Windows / Linux / macOS)

```bash
pip install -r requirements.txt
python netpulse.py
```

Пример конфигурации — [`netpulse_config.example.json`](netpulse_config.example.json)
(скопируйте как `netpulse_config.json` рядом с `netpulse.py`).

## Сборка установщика

Всё для сборки лежит в папке [`windows/`](windows/):

| Файл | Назначение |
|---|---|
| `build.bat` | Сборка в один клик: зависимости → `NetPulse.exe` → установщик |
| `netpulse.spec` | Конфигурация PyInstaller |
| `installer.iss` | Скрипт Inno Setup |
| `version_info.txt` | Версия и описание в свойствах `.exe` |

**Локально на Windows:** установите [Python 3.10+](https://www.python.org/downloads/) и
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`),
затем запустите `windows\build.bat`. Готовый установщик появится в `windows\Output\`.

**Через GitHub Actions:** вкладка *Actions → Windows installer → Run workflow* — установщик
будет в артефактах сборки. При пуше тега `v*` (например `git tag v1.0.0 && git push --tags`)
он автоматически прикрепится к релизу.

## Лицензия

[MIT](LICENSE)
