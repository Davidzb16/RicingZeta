export PATH="$HOME/.local/bin:$PATH"

if [[ "$TERM" == "xterm-kitty" ]] || [[ "$TERM" == "kitty" ]]; then
    fastfetch
fi
