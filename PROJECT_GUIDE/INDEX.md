---
purpose: Görev türüne göre okunacak belgeleri seçer; başka bilgi içermez.
read_when: Her görevin başında.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# INDEX — ne okumalıyım?

**Kural:** Bir görevde bu klasörün tamamını okuma. Aşağıdaki satırdan **en fazla 2–4 belge** oku. Belge içindeki bağlantılara ancak gerçekten gerekiyorsa git.

| Görev türü | Oku |
|---|---|
| Genel yönelim / "proje nerede?" | [CURRENT_STATUS.md](CURRENT_STATUS.md) + [ARCHITECTURE.md](ARCHITECTURE.md) |
| Kod düzeltmesi (genel) | [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) + [TESTING_GUIDE.md](TESTING_GUIDE.md) + [MODULE_MAP.md](MODULE_MAP.md) ilgili bölüm |
| Import (CSV/XLSX, mükerrer, sayfa seçimi) | [DATA_AND_PATHS.md](DATA_AND_PATHS.md) + [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) + [TESTING_GUIDE.md](TESTING_GUIDE.md) |
| Worker / kapanış / restart | [ARCHITECTURE.md](ARCHITECTURE.md) + [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) + [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) |
| Veri, yol, migration, yedek | [DATA_AND_PATHS.md](DATA_AND_PATHS.md) + [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) |
| Credential / SMTP / gizlilik | [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md) + [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) |
| Test yazma / test seçme | [TESTING_GUIDE.md](TESTING_GUIDE.md) |
| Build | [BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md) + [CURRENT_STATUS.md](CURRENT_STATUS.md) |
| Release | [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) + [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) + [project_manifest.json](project_manifest.json) |
| Frozen EXE / installer doğrulaması | [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) |
| Denetim geçmişi / bulgu kapanışı | [AUDIT_HISTORY.md](AUDIT_HISTORY.md) + [KNOWN_RISKS.md](KNOWN_RISKS.md) |
| Neden böyle yapılmış? | [DECISIONS.md](DECISIONS.md) |
| Bilinen hata belirtisi | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Claude uygulaması | [COLLABORATION_WORKFLOW.md](COLLABORATION_WORKFLOW.md) + [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md) |
| Codex incelemesi | [COLLABORATION_WORKFLOW.md](COLLABORATION_WORKFLOW.md) + incelenen konunun kanıt belgesi |

## Belge sınıfları

- **Snapshot (eskir):** [CURRENT_STATUS.md](CURRENT_STATUS.md), [project_manifest.json](project_manifest.json), [KNOWN_RISKS.md](KNOWN_RISKS.md)
- **Kalıcı:** [ARCHITECTURE.md](ARCHITECTURE.md), [MODULE_MAP.md](MODULE_MAP.md), [DATA_AND_PATHS.md](DATA_AND_PATHS.md), [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md), [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)
- **Süreç:** [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md), [COLLABORATION_WORKFLOW.md](COLLABORATION_WORKFLOW.md), [TESTING_GUIDE.md](TESTING_GUIDE.md), [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md), [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
- **Tarihçe:** [AUDIT_HISTORY.md](AUDIT_HISTORY.md), [DECISIONS.md](DECISIONS.md), [decisions/](decisions/README.md)

## Bakım

Rehberin tutarlılığı: `python PROJECT_GUIDE/scripts/verify_project_guide.py` (modlar için [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md)).
