# Source from bash entry points: export non-empty KEY=VALUE lines from the repo
# .env. Variables already set in the environment win; empty values are skipped
# so the code's own defaults apply. Missing .env = no-op.
_dn_env_file="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env}"
if [ -f "$_dn_env_file" ]; then
  while IFS= read -r _dn_line || [ -n "$_dn_line" ]; do
    _dn_line="${_dn_line#"${_dn_line%%[![:space:]]*}"}"
    case "$_dn_line" in ''|'#'*) continue ;; esac
    _dn_line="${_dn_line#export }"
    case "$_dn_line" in *=*) ;; *) continue ;; esac
    _dn_key="${_dn_line%%=*}"
    _dn_key="${_dn_key//[[:space:]]/}"
    _dn_val="${_dn_line#*=}"
    _dn_val="${_dn_val#"${_dn_val%%[![:space:]]*}"}"
    _dn_val="${_dn_val%"${_dn_val##*[![:space:]]}"}"
    case "$_dn_val" in \"*\") _dn_val="${_dn_val:1:${#_dn_val}-2}" ;; \'*\') _dn_val="${_dn_val:1:${#_dn_val}-2}" ;; esac
    [ -z "$_dn_val" ] && continue
    case "$_dn_val" in "~/"*) _dn_val="$HOME/${_dn_val#\~/}" ;; esac
    if [ -z "${!_dn_key+x}" ]; then export "$_dn_key=$_dn_val"; fi
  done < "$_dn_env_file"
fi
unset _dn_env_file _dn_line _dn_key _dn_val
