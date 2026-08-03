#!/bin/bash
# Воспроизведение механизма «git add пишет блоб до коммита» на канарейке.
#
# КАНАРЕЙКА ГЕНЕРИРУЕТСЯ ЗДЕСЬ, во время прогона, и НИКОГДА не печатается: наружу
# идёт только отпечаток sha256[:16] (правило 16 §8). Поэтому ни в исходнике этого
# скрипта, ни в его выводе литерала метки нет, и в боевой репозиторий он не попадёт.
#
# Каждый случай — ОТДЕЛЬНЫЙ чистый репозиторий.
set -u
SCAN="$1"
CANARY="QF_CANARY_$(head -c3 /dev/urandom | od -An -tx1 | tr -d ' \n')"
FP=$(printf '%s' "$CANARY" | sha256sum | cut -c1-16)
PY() { PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python "$@"; }

ROOT=$(mktemp -d)
echo "временный корень   : $ROOT"
echo "канарейка          : отпечаток sha256[:16] = $FP  (литерал не печатается)"
echo "длина метки        : ${#CANARY} символов"
echo

init_repo() {                      # $1 = имя случая
  local d="$ROOT/$1"
  mkdir -p "$d"; cd "$d" || exit 9
  git init -q -b main
  git config user.email canary@example.invalid
  git config user.name  Canary
  git config gc.auto 0             # автосборка не должна выкосить висячий объект
  git config core.autocrlf false
  # Посторонний коммит: чтобы история БЫЛА и «не найден» не означал «область пуста»
  printf 'unrelated baseline\n' > README.md
  git add README.md && git commit -q -m "baseline, метки здесь нет"
}

# Печатает строку таблицы: найден ли блоб каждой из трёх форм
report() {                         # $1 = случай, $2 = блоб-цель
  local case="$1" blob="$2"
  local wt all ref db scanned hits

  # 0. Есть ли метка в РАБОЧЕМ ДЕРЕВЕ. Если есть — попадание ref-форм может быть
  #    «по рабочему дереву», а не по истории, и таблицу читать нельзя.
  wt=$(grep -rl -F -e "$CANARY" . --exclude-dir=.git 2>/dev/null | wc -l)

  # 1. область = ref-ы --all
  local rl; rl=$(git rev-list --objects --all 2>/dev/null | awk '{print $1}')
  if [ -z "$rl" ]; then all="—(нет коммитов)"; else
    if printf '%s\n' "$rl" | grep -qF "$blob"; then all="НАЙДЕН"; else all="не найден"; fi
  fi

  # 2. область = ref-ы --all --reflog
  local rr; rr=$(git rev-list --objects --all --reflog 2>/dev/null | awk '{print $1}')
  if [ -z "$rr" ]; then ref="—(нет коммитов)"; else
    if printf '%s\n' "$rr" | grep -qF "$blob"; then ref="НАЙДЕН"; else ref="не найден"; fi
  fi

  # 3. область = ПРЕДИКАТ по всей базе объектов
  local out; out=$(QF_NEEDLE="$CANARY" PY "$SCAN" "$PWD" "$case" 2>&1)
  scanned=$(printf '%s\n' "$out" | sed -n 's/.*из них просмотрено.*: *\([0-9]*\).*/\1/p')
  hits=$(printf '%s\n' "$out" | sed -n 's/^СОВПАДЕНИЙ (объектов) *: *\([0-9]*\).*/\1/p')
  if printf '%s\n' "$out" | grep -qF "$blob"; then db="НАЙДЕН"; else db="не найден"; fi

  printf '| %-4s | %-16s | %-16s | %-10s | %8s | %5s | %s |\n' \
         "$case" "$all" "$ref" "$db" "${scanned:-?}" "${hits:-?}" \
         "$( [ "$wt" -eq 0 ] && echo 'чисто' || echo "🚨 метка в дереве ($wt)")"
}

echo "=================== К1: git add, КОММИТА НЕТ ==================="
init_repo K1
printf 'payload %s\n' "$CANARY" > secret.txt
git add secret.txt
K1_BLOB=$(git rev-parse :secret.txt)
git update-index --force-remove secret.txt      # из индекса
rm -f secret.txt                                # из рабочего дерева
echo "блоб-цель К1: $K1_BLOB"
echo "в индексе после снятия: $(git ls-files -s | grep -c "$K1_BLOB")   (0 = блоб ничем не держится)"
echo "git status: $(git status --porcelain | wc -l) строк (0 = дерево чисто)"
echo "fsck --unreachable про этот блоб:"; git fsck --unreachable --no-progress 2>/dev/null | grep -F "$K1_BLOB" | sed 's/^/  /' || echo "  (не показан)"
K1_D=$PWD

echo
echo "======= К2: git add грязного → правка файла → коммит ЧИСТОГО ======="
echo "======= это ровно механизм 02.08 ======="
init_repo K2
printf 'log line 1\npayload %s\nlog line 3\n' "$CANARY" > copy.log
git add copy.log                                 # ← ЗДЕСЬ блоб уже записан
K2_DIRTY=$(git rev-parse :copy.log)
printf 'log line 1\npayload <ВЫРЕЗАНО>\nlog line 3\n' > copy.log   # «скан поймал, почистили»
git add copy.log
K2_CLEAN=$(git rev-parse :copy.log)
git commit -q -m "копия лога, метка вырезана"
echo "грязный блоб (до правки): $K2_DIRTY"
echo "чистый блоб (в коммите) : $K2_CLEAN"
echo "различны: $( [ "$K2_DIRTY" != "$K2_CLEAN" ] && echo ДА || echo НЕТ )"
echo "в индексе грязный: $(git ls-files -s | grep -c "$K2_DIRTY")   (0 = ничем не держится)"
echo "git status: $(git status --porcelain | wc -l) строк"
echo "fsck --unreachable про грязный блоб:"; git fsck --unreachable --no-progress 2>/dev/null | grep -F "$K2_DIRTY" | sed 's/^/  /' || echo "  (не показан)"
K2_D=$PWD

echo
echo "=================== К3: коммит снят через --amend ==================="
init_repo K3
printf 'keep me\n' > keep.txt
printf 'payload %s\n' "$CANARY" > secret.txt
git add keep.txt secret.txt && git commit -q -m "метка плюс filler"
K3_BLOB=$(git rev-parse HEAD:secret.txt)
git rm -q secret.txt
git commit -q --amend -m "метка снята amend, filler остался" || echo "🚨 amend отказал"
echo "блоб-цель К3: $K3_BLOB   (reflog НЕ истёк)"
K3_D=$PWD

echo
echo "============ К3б: тот же случай ПОСЛЕ истечения reflog ============"
cp -r "$ROOT/K3" "$ROOT/K3b"
cd "$ROOT/K3b" || exit 9
git reflog expire --expire=now --expire-unreachable=now --all
echo "reflog истёк"
K3B_D=$PWD

echo
echo "=================== К4: коммит в УДАЛЁННОЙ ветке ==================="
init_repo K4
git checkout -q -b doomed
printf 'payload %s\n' "$CANARY" > secret.txt
git add secret.txt && git commit -q -m "метка в ветке, которую удалим"
K4_BLOB=$(git rev-parse HEAD:secret.txt)
git checkout -q main
git branch -q -D doomed
echo "блоб-цель К4: $K4_BLOB"
K4_D=$PWD

echo
echo "############################################################"
echo "СВОДНАЯ ТАБЛИЦА. Каждый случай — свой чистый репозиторий."
echo "############################################################"
printf '| %-4s | %-16s | %-16s | %-10s | %8s | %5s | %s |\n' 'сл.' 'в --all' 'в --all --reflog' 'в базе' 'просм.' 'совп.' 'рабочее дерево'
printf '|%s|%s|%s|%s|%s|%s|%s|\n' '------' '------------------' '------------------' '------------' '----------' '-------' '----------------'
cd "$K1_D"  && report K1  "$K1_BLOB"
cd "$K2_D"  && report K2  "$K2_DIRTY"
cd "$K3_D"  && report K3  "$K3_BLOB"
cd "$K3B_D" && report K3б "$K3_BLOB"
cd "$K4_D"  && report K4  "$K4_BLOB"

echo
echo "############################################################"
echo "ПРИЁМКА ЧАСТИ 1"
echo "############################################################"
acc() {   # $1=случай $2=каталог $3=блоб
  cd "$2" || return
  local rl rr out a r d
  rl=$(git rev-list --objects --all 2>/dev/null | awk '{print $1}')
  rr=$(git rev-list --objects --all --reflog 2>/dev/null | awk '{print $1}')
  printf '%s\n' "$rl" | grep -qF "$3" && a=НАЙДЕН || a='не найден'
  printf '%s\n' "$rr" | grep -qF "$3" && r=НАЙДЕН || r='не найден'
  out=$(QF_NEEDLE="$CANARY" PY "$SCAN" "$PWD" "$1" 2>&1)
  printf '%s\n' "$out" | grep -qF "$3" && d=НАЙДЕН || d='не найден'
  if [ "$a" = 'не найден' ] && [ "$r" = 'не найден' ] && [ "$d" = НАЙДЕН ]; then
    echo "  $1: ✅ ПРИНЯТО — не найден первыми двумя формами, найден третьей"
  else
    echo "  $1: 🚨 НЕ ПРИНЯТО — --all=$a  --all --reflog=$r  база=$d"
  fi
}
acc K1 "$K1_D" "$K1_BLOB"
acc K2 "$K2_D" "$K2_DIRTY"
echo "  (К3, К3б, К4 — контекст, требование приёмки задано только на К1 и К2)"

echo
echo "=== УДАЛЕНИЕ ВРЕМЕННОГО КОРНЯ ==="
cd /
rm -rf "$ROOT"
if [ -d "$ROOT" ]; then echo "🚨 НЕ УДАЛЁН: $ROOT"; else echo "удалён, каталога нет: $ROOT"; fi
echo
echo "КОНТРОЛЬ: литерал канарейки в этом выводе не печатался ни разу."
echo "Метка называется отпечатком: $FP"
