# Décision de licence — 30 octobre 2026

**Décision de l'opérateur :** la projection publique `gnu6dotlive/blob.in` est publiée sous
**licence MIT**. Elle remplace, pour cette projection, la déclaration
`LicenseRef-Proprietary` du dépôt privé, que les documents datés de ce dépôt citent encore :
ils restent tels qu'écrits, comme trace de l'état d'alors.

Ce qui a été vérifié avant la décision :

- **Aucun code donneur GPL.** Les registres G01 et G02A consignent qu'aucune source du
  donneur historique `blobin-core` (GPL-3.0-or-later) n'a été importée ; aucun en-tête GPL,
  copyright tiers ou SPDX n'apparaît dans `crates/`, `scripts/`, `tools/` ou `tests/`.
- **Dépendances permissives.** Les 293 paquets de `Cargo.lock` déclarent une licence MIT,
  Apache-2.0, BSD, ISC, Zlib ou Unlicense, ou un choix qui en comprend une.
- **wgpu-hal 30.0.1**, copie corrigée dans `vendor/`, garde ses deux licences (MIT,
  Apache-2.0) ; voir `THIRD_PARTY_NOTICES.md`.
- **Aucun secret** : gitleaks, sur les 76 commits de l'historique privé, ne trouve rien.

Ce qui n'est pas publié : `tools/qchain-f3-probe`, qui dépend de chemins du dépôt privé
gnu.in.labs et ne se compile pas ailleurs ; le Render Bridge, qui vit dans gnu.in.labs.

Ce qui ne tourne pas seul : les deux tests de `crates/blob-frame/tests/qchain_evidence.rs`
relisent les frames F4 du moteur, gardées hors du dépôt. Ils sont ignorés par défaut et se
lancent avec `QCHAIN_EVIDENCE_ROOT=… cargo test -- --ignored`.

La projection est découpée par `tools/public_cut.py` (dépôt privé), jamais à la main.
