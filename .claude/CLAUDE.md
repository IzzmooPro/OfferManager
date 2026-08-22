# Paylaşılan Claude yardımcıları

Kanonik proje talimatı kökteki `CLAUDE.md` ve `PROJECT_GUIDE/INDEX.md`
dosyalarındadır. Bu dosya onları tekrar etmez veya geçersiz kılmaz.

- Her görevde önce kök `CLAUDE.md` yönlendirmesini uygula.
- Yalnız göreve uyan `.claude/skills/` ve path-scoped `.claude/rules/`
  içeriğini kullan.
- Uzun ara, belirsiz checkout veya release öncesinde
  `.claude/scripts/offer_state.py` ile salt-okunur preflight yap.
- Skill/rule ile PROJECT_GUIDE çelişirse PROJECT_GUIDE geçerlidir.
- Agent paketi değiştiğinde
  `.claude/scripts/validate_agent_pack.py` ve `.claude/tests/` testlerini çalıştır.
