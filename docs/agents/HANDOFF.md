# Handoff — формат сдачи результата

**Ни один агент не объявляет задачу завершённой без handoff.** Handoff — это одновременно тело Pull Request и сообщение в ChatGPT Control Center.

Постановка задачи — [`TASK_SPECIFICATION.md`](TASK_SPECIFICATION.md).

---

## 17 обязательных полей

| № | Поле | Требование |
|---|---|---|
| 1 | **Task ID** | как в постановке |
| 2 | **Agent Profile** | точное имя профиля в Canvas, например `Codex-Quant-Implementation` |
| 3 | **Branch** | полное имя ветки |
| 4 | **Worktree** | абсолютный путь |
| 5 | **Base commit** | короткий SHA, зафиксированный в начале работы |
| 6 | **Summary** | 3–6 строк: что сделано и почему именно так |
| 7 | **Changed files** | полный список с пометкой added / modified / deleted |
| 8 | **Commands executed** | все значимые команды, которые изменяли состояние или проверяли результат |
| 9 | **Tests and results** | каждая проверка + **exit code** |
| 10 | **Validation evidence** | конкретика: числа passed/failed, ключевые строки вывода, URL, скриншот-путь |
| 11 | **Remaining risks** | что может сломаться и почему |
| 12 | **Known limitations** | что сознательно не покрыто |
| 13 | **Manual actions required** | что должен сделать владелец (OWNER CHECKPOINT), если нужно |
| 14 | **Commit hashes** | все коммиты этой задачи |
| 15 | **Pull Request** | URL, состояние (Draft / Ready), base branch |
| 16 | **Recommended reviewer** | какой агент или человек должен проверить и почему |
| 17 | **Status** | ровно одно из: `READY_FOR_REVIEW` · `BLOCKED` · `PARTIAL` · `FAILED` |

Дополнительно, если применимо: **Source Pack updates** — какие документы `docs/source/` требуют обновления и почему (`docs/source/00 §8`).

---

## Значения статуса

| Статус | Когда ставится |
|---|---|
| `READY_FOR_REVIEW` | scope выполнен полностью, все применимые проверки прошли, PR открыт |
| `PARTIAL` | часть scope выполнена и пригодна к review; невыполненное перечислено в полях 12–13 |
| `BLOCKED` | работа остановлена внешней причиной: нет credential, не решён `OQ-…`, недоступен ресурс. Указать точную причину и одно требуемое действие |
| `FAILED` | задача выполнима, но попытка не удалась. Указать, что именно не сработало и что уже проверено |

Запрещено: `READY_FOR_REVIEW` при красном применимом гейте; статус «почти готово»; отсутствие статуса.

Гейт, который был красным **до** правки агента (`check-dashboard-tokens.mjs` — `Q-02`, `qa:landing` — `Q-03`), не блокирует `READY_FOR_REVIEW`, но обязателен к упоминанию в полях 9 и 12 со ссылкой на ID.

---

## Шаблон

```markdown
## Handoff

**1. Task ID:** RM-P0-003
**2. Agent Profile:** Codex-Quant-Implementation
**3. Branch:** agent/codex/rm-p0-003-add-ci
**4. Worktree:** /Users/danila/OpenHands/worktrees/Quant/agent-codex-rm-p0-003-add-ci
**5. Base commit:** 7f357e3

**6. Summary**
Добавлен GitHub Actions workflow, прогоняющий 6 гейтов сайта, pytest и dashboard-тест
формата на каждый PR в активную ветку разработки. Два известных красных гейта помечены
continue-on-error со ссылкой на Q-02 / Q-03, а не исправлены и не удалены.

**7. Changed files**
- added:    .github/workflows/ci.yml
- modified: docs/source/11_MASTER_ROADMAP.md  (RM-P0-003 → closed)

**8. Commands executed**
- scripts/agents/create-worktree.sh agent/codex/rm-p0-003-add-ci quant-site-approved-reference-redesign
- cd website && npm run typecheck && npm run lint && npm run check && npm run build
- python3 -m pytest tests/
- node bot/ui/static/app/format.test.mjs
- git add .github/workflows/ci.yml docs/source/11_MASTER_ROADMAP.md
- git commit / git push -u origin agent/codex/rm-p0-003-add-ci
- gh pr create --draft --base quant-site-approved-reference-redesign

**9. Tests and results**
| Проверка | Exit code |
|---|---|
| npm run typecheck | 0 |
| npm run lint | 0 |
| npm run check | 0 |
| npm run build | 0 |
| pytest tests/ | 0 |
| node bot/ui/static/app/format.test.mjs | 0 |
| node bot/ui/static/check-dashboard-tokens.mjs | 1 — красный ДО правки (Q-02) |

**10. Validation evidence**
- pytest: 161 passed, 72 skipped
- format.test.mjs: 27/27
- build: 12 SSG-страниц, First Load 363 kB
- workflow не объявляет ни одного `secrets.*`

**11. Remaining risks**
Workflow не проверялся на runner GitHub — CI в репозитории появляется впервые. Первый
прогон может выявить отличия окружения (версия Node, наличие Python 3.11).

**12. Known limitations**
Q-02 и Q-03 не исправлены — вне scope. E2E `qa:landing` в CI не включён: требует установки
Playwright, это RM-P1-020.

**13. Manual actions required**
Нет. Для включения обязательных проверок в branch protection потребуется действие владельца
после первого успешного прогона.

**14. Commit hashes:** a1b2c3d
**15. Pull Request:** https://github.com/Pomiranov/Trading-Bot/pull/NN — Draft, base `quant-site-approved-reference-redesign`
**16. Recommended reviewer:** claude — проверить архитектуру workflow и отсутствие доступа к секретам
**17. Status:** READY_FOR_REVIEW

**Source Pack updates:** `docs/source/10` — раздел 25 «CI/CD — NOT STARTED» требует обновления после merge.
```

---

## Правила

1. **Handoff пишется по факту, а не по плану.** Если проверка не запускалась — так и написать, а не проставить 0.
2. **Секреты в handoff не попадают.** Про credential допустимо сообщить: существует, тип, путь, права, дата изменения, прошла ли проверка подключения. Значение — никогда.
3. **Exit code обязателен для каждой проверки.** Формулировка «тесты прошли» без кода не принимается.
4. **Base commit фиксируется в начале работы**, а не восстанавливается в конце по памяти.
5. **`Manual actions required` — это единственное место**, где агент просит действий владельца. Одна причина, одно действие, точные шаги, ожидаемый результат, способ проверки без раскрытия секрета.
6. **Один handoff — одна задача.** Не объединять несколько Task ID.
7. Handoff в теле PR и handoff в Control Center — **один и тот же текст**.

---

## Приёмка Control Center

Control Center принимает handoff, проверяя:

- статус соответствует фактам полей 9–12;
- каждый пункт acceptance criteria из постановки закрыт и подтверждён полем 10;
- изменённые файлы (поле 7) не выходят за scope постановки;
- нет запрещённых действий: merge, force push, изменение branch protection, коммит секретов;
- worktree (поле 4) находится под `/Users/danila/OpenHands/worktrees/Quant/`, а не в canonical дереве;
- указаны требуемые обновления Source Pack, если изменение значимое.

Только после этого задача передаётся владельцу для решения о merge.
