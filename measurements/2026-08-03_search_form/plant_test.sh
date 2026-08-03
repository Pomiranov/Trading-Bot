#!/bin/bash
# ПОДСАДКА. Правило 12: предикат, ни разу не поймавший заведомо подсаженный
# случай, не проверен. Здесь он ловится или не ловится ЧИСЛОМ.
#
# Канарейка — безобидная метка, НЕ токен. В боевой репозиторий не коммитится
# никогда: всё в mktemp -d вне рабочего дерева, каталог удаляется.
#
# ТРИ ДЕФЕКТА ПЕРВОЙ ВЕРСИИ ЭТОГО ТЕСТА, исправленные здесь:
#  1. С2 не подсаживался: `--amend` отказывал («стал бы пустым»), потому что в
#     коммите не было ничего кроме снимаемого файла. Добавлен второй файл.
#  2. три случая сворачивались в ОДИН блоб: содержимое файлов было одинаковым, а
#     git дедуплицирует по содержимому. Теперь у каждого случая своя строка.
#  3. python печатал в cp1251 — вывод был нечитаем. PYTHONUTF8=1.
set -u
CANARY='QF_CANARY_7f3a91'
SCAN="$1"
PY() { PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python "$@"; }

TMP=$(mktemp -d)
echo "временный репозиторий: $TMP"
echo "канарейка            : $CANARY  (метка, не секрет)"
echo

cd "$TMP" || exit 9
git init -q -b main
git config user.email canary@example.invalid
git config user.name  Canary
git config gc.auto 0            # автосборка не должна выкосить висячий объект
git config core.autocrlf false  # чтобы предупреждения не засоряли улику

echo "=== ПОДСАДКА ТРЁХ СОСТОЯНИЙ. У каждого СВОЁ содержимое — иначе один блоб ==="

# ── С1: достижимый коммит в ветке ─────────────────────────────────────────
printf '%s case=C1 reachable\n' "$CANARY" > c1.txt
git add c1.txt && git commit -q -m "C1: метка в достижимом коммите"
C1_C=$(git rev-parse HEAD); C1_B=$(git rev-parse HEAD:c1.txt)

# ── С2: коммит, СНЯТЫЙ через --amend, затем reflog истёк ───────────────────
# Второй файл обязателен: без него amend отказывает, и подсадки не происходит.
printf 'filler, чтобы amend не стал пустым\n' > keep.txt
printf '%s case=C2 amended-away\n' "$CANARY" > c2.txt
git add keep.txt c2.txt && git commit -q -m "C2: метка плюс filler"
C2_C=$(git rev-parse HEAD); C2_B=$(git rev-parse HEAD:c2.txt)
git rm -q c2.txt
git commit -q --amend -m "C2: метка снята amend, filler остался" || echo "🚨 amend отказал"
git reflog expire --expire=now --expire-unreachable=now --all

# ── С3: коммит в ветке, которая затем УДАЛЕНА ─────────────────────────────
git checkout -q -b doomed
printf '%s case=C3 deleted-branch\n' "$CANARY" > c3.txt
git add c3.txt && git commit -q -m "C3: метка в ветке, которую удалим"
C3_C=$(git rev-parse HEAD); C3_B=$(git rev-parse HEAD:c3.txt)
git checkout -q main
git branch -q -D doomed

printf 'С1 коммит %s  блоб %s\n' "$C1_C" "$C1_B"
printf 'С2 коммит %s  блоб %s\n' "$C2_C" "$C2_B"
printf 'С3 коммит %s  блоб %s\n' "$C3_C" "$C3_B"
echo "различных блобов с меткой: $(printf '%s\n%s\n%s\n' "$C1_B" "$C2_B" "$C3_B" | sort -u | wc -l)  ← обязано быть 3"
echo

echo "=== СВЕРКА СОСТОЯНИЙ. Проверяется БЛОБ: именно его находит форма 3 ==="
# ВАЖНО: `git rev-list --all` перечисляет только КОММИТЫ, блоба в нём нет
# никогда. Область для блоба задаётся `--objects`.
OBJ_ALL=$(git rev-list --objects --all)
OBJ_REF=$(git rev-list --objects --all --reflog)
OBJ_DB=$(git cat-file --batch-all-objects --batch-check='%(objectname)')
t() { printf '%s\n' "$2" | grep -qF "$1" && echo ДА || echo НЕТ; }
printf '%-4s %-10s %-18s %-16s\n' 'сл.' 'в --all' 'в --all --reflog' 'в базе объектов'
printf '%-4s %-10s %-18s %-16s\n' 'С1' "$(t "$C1_B" "$OBJ_ALL")" "$(t "$C1_B" "$OBJ_REF")" "$(t "$C1_B" "$OBJ_DB")"
printf '%-4s %-10s %-18s %-16s\n' 'С2' "$(t "$C2_B" "$OBJ_ALL")" "$(t "$C2_B" "$OBJ_REF")" "$(t "$C2_B" "$OBJ_DB")"
printf '%-4s %-10s %-18s %-16s\n' 'С3' "$(t "$C3_B" "$OBJ_ALL")" "$(t "$C3_B" "$OBJ_REF")" "$(t "$C3_B" "$OBJ_DB")"
echo
echo "-- git fsck --unreachable: С2 обязан быть здесь (жив и недостижим)"
git fsck --unreachable --no-progress 2>/dev/null | grep -F "$C2_B" | sed 's/^/   /' \
  || echo "   🚨 блоб С2 в перечне недостижимых НЕ показан"
echo

echo "############################################################"
echo "ФОРМА 0 — СЛОМАННАЯ (ревизии ПОСЛЕ --), как записана в 0e9e078"
echo "############################################################"
git rev-list --all | xargs git grep -l -e "$CANARY" -- >f0.out 2>f0.err; rc=$?
echo "exit code       : $rc"
echo "stdout строк    : $(grep -c . f0.out)"
echo "stderr байт     : $(wc -c < f0.err)   ← ноль означает МОЛЧА"
echo "ПОЙМАНО СЛУЧАЕВ : 0 из 3"
echo

echo "############################################################"
echo "ФОРМА 1 — исправлен только \`--\`; область = ref-ы --all"
echo "############################################################"
git grep -l -e "$CANARY" $(git rev-list --all) >f1.out 2>f1.err; rc=$?
echo "exit code       : $rc"
# git grep печатает <ревизия>:<путь>, блоба в выводе нет — сверяем по ПУТИ
for c in "С1 c1.txt" "С2 c2.txt" "С3 c3.txt"; do set -- $c
  if grep -q ":$2\$" f1.out; then echo "  $1: НАЙДЕН"; else echo "  $1: не найден"; fi
done
echo "различных путей : $(sed 's/^[0-9a-f]*://' f1.out | sort -u | grep -c .)"
sed 's/^\([0-9a-f]\{8\}\)[0-9a-f]*:/  коммит \1… путь /' f1.out | sort -u
echo

echo "############################################################"
echo "ФОРМА 2 — то же с --reflog (форма 3 из 0e9e078, \`--\` исправлен)"
echo "############################################################"
git grep -l -e "$CANARY" $(git rev-list --all --reflog) >f2.out 2>f2.err; rc=$?
echo "exit code       : $rc"
for c in "С1 c1.txt" "С2 c2.txt" "С3 c3.txt"; do set -- $c
  if grep -q ":$2\$" f2.out; then echo "  $1: НАЙДЕН"; else echo "  $1: не найден"; fi
done
echo "различных путей : $(sed 's/^[0-9a-f]*://' f2.out | sort -u | grep -c .)"
sed 's/^\([0-9a-f]\{8\}\)[0-9a-f]*:/  коммит \1… путь /' f2.out | sort -u
echo

echo "############################################################"
echo "ФОРМА 3 — ПРЕДИКАТ по всей базе объектов (починенная форма)"
echo "############################################################"
QF_NEEDLE="$CANARY" PY "$SCAN" "$TMP" "временный репозиторий подсадки" >f3.out 2>f3.err; rc=$?
cat f3.out; cat f3.err
echo "exit code       : $rc   (0=чисто, 1=совпадения есть, 3=отказ формы)"
echo "-- сверка по каждому случаю:"
for c in "С1 $C1_B" "С2 $C2_B" "С3 $C3_B"; do set -- $c
  if grep -qF "$2" f3.out; then echo "  $1: НАЙДЕН"; else echo "  $1: 🚨 НЕ НАЙДЕН"; fi
done
echo

echo "=== ОТРИЦАТЕЛЬНЫЙ КОНТРОЛЬ: метки, которой нет ==="
QF_NEEDLE='QF_CANARY_NO_SUCH_MARK_zzz' PY "$SCAN" "$TMP" "тот же репозиторий, метки нет" | tail -2
echo "exit code       : ${PIPESTATUS[0]}   (обязан быть 0: просмотр состоялся, совпадений нет)"
echo
echo "=== ОТКАЗ ФОРМЫ ОБЯЗАН БЫТЬ ГРОМКИМ ==="
QF_NEEDLE='' PY "$SCAN" "$TMP" x; echo "  пустое значение     -> exit $?  (обязан 3)"
QF_NEEDLE="$CANARY" PY "$SCAN" "$TMP/nosuchdir" x 2>&1 | tail -1
echo "  не репозиторий      -> exit ${PIPESTATUS[0]}  (обязан 3)"
echo

echo "=== УДАЛЕНИЕ ВРЕМЕННОГО РЕПОЗИТОРИЯ ==="
cd /
rm -rf "$TMP"
if [ -d "$TMP" ]; then echo "🚨 НЕ УДАЛЁН: $TMP"; else echo "удалён, каталога нет: $TMP"; fi
