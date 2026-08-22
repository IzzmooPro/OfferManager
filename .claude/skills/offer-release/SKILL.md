---
name: offer-release
description: Açıkça verilen Teklif Yönetim Sistemi sürümü için kanonik release kapılarını uygular; build, kurulum, commit, push, tag ve yayın yetkilerini ayrı ayrı korur.
argument-hint: "[vX.Y]"
disable-model-invocation: true
---

# Offer release

Hedef `$ARGUMENTS` içinde tek bir `vX.Y` değilse yayınlama; sürümü sor.

1. `python "${CLAUDE_PROJECT_DIR}/.claude/scripts/offer_state.py" --expect vX.Y` çalıştır; kök, HEAD ve kirli dosyaları kanıtla. İlgisiz değişikliği işe katma.
2. `PROJECT_GUIDE/INDEX.md` release satırına göre yalnız `RELEASE_CHECKLIST.md`, `VERIFICATION_GUIDE.md` ve `project_manifest.json` belgelerini oku.
3. Build yetkisi yoksa burada dur ve yalnız preflight raporu ver. Build yetkisi varsa kanonik `stable.build_command` komutunu kullan; eski artifact'i yeni kanıt sayma.
4. Build sonrası `offer_state.py --expect vX.Y --require-installer`, `python PROJECT_GUIDE/scripts/verify_project_guide.py --release` ve `git diff --check` çalıştır. Kırmızı kapıyı atlama veya otomatik tekrar etme.
5. Kaynak suite, frozen EXE ve installer/upgrade-uninstall-reinstall kanıtlarını ayrı raporla. Bir sınıfı diğerinin yerine kullanma.
6. Commit, push, tag, draft oluşturma ve public release için mevcut mesajda ayrı açık yetki ara. Yayın sonrası HEAD/tag hedefi ile uzak asset adı-boyutu-SHA-256 eşitliğini read-back yap; mevcut release asset'inin üzerine yazma.
