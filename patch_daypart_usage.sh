apply() {
  sed -i 's/\(title = f"\)[^"]* дайджест Реала"/\1$(python3 - <<PY
from utils_daypart import get_daypart
print(get_daypart())
PY
) дайджест Реала"/' digest.py
}
apply
