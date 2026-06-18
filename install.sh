#!/usr/bin/env bash
# monitory installer: creates a project-local virtual environment,
# installs dependencies and exposes the `monitory` command in ~/.local/bin.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
COMMAND_NAME="monitory"

if command -v tput >/dev/null 2>&1 && [ -t 1 ]; then
    BOLD="$(tput bold)"; GREEN="$(tput setaf 2)"; YELLOW="$(tput setaf 3)"; RED="$(tput setaf 1)"; RESET="$(tput sgr0)"
else
    BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

info()  { echo "${BOLD}==>${RESET} $*"; }
ok()    { echo "${GREEN}✓${RESET} $*"; }
warn()  { echo "${YELLOW}!${RESET} $*"; }
fail()  { echo "${RED}✗ $*${RESET}" >&2; exit 1; }

uninstall() {
    info "Uninstalling $COMMAND_NAME..."
    rm -rf "$VENV_DIR"
    rm -f "$BIN_DIR/$COMMAND_NAME"
    ok "Done. Removed the virtual environment and $BIN_DIR/$COMMAND_NAME"
    exit 0
}

if [ "${1:-}" = "--uninstall" ]; then
    uninstall
fi

info "Checking for Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 not found. Install it with your distro's package manager (apt, dnf, pacman, etc.) and re-run this script."
fi

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 9) else 0)')"
if [ "$PY_OK" != "1" ]; then
    fail "Python 3.9+ is required, found $PY_VERSION."
fi
ok "Python $PY_VERSION"

if ! python3 -c "import venv" >/dev/null 2>&1; then
    fail "Python's 'venv' module is not available. On Debian/Ubuntu install it with: sudo apt install python3-venv"
fi

info "Creating virtual environment at $VENV_DIR..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
ok "Virtual environment ready"

info "Installing dependencies (rich, psutil)..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$PROJECT_DIR"
ok "Dependencies installed"

info "Exposing the '$COMMAND_NAME' command in $BIN_DIR..."
mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/$COMMAND_NAME" "$BIN_DIR/$COMMAND_NAME"
ok "Symlink created: $BIN_DIR/$COMMAND_NAME -> $VENV_DIR/bin/$COMMAND_NAME"

case ":$PATH:" in
    *":$BIN_DIR:"*)
        ok "$BIN_DIR is already in your PATH"
        ;;
    *)
        warn "$BIN_DIR is not in your PATH."
        warn "Add this line to your ~/.bashrc or ~/.zshrc and open a new terminal:"
        echo
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo
        ;;
esac

echo
ok "Installation complete."
echo "Run ${BOLD}${COMMAND_NAME}${RESET} from any terminal or inside tmux to get started."
echo "To uninstall: ${BOLD}./install.sh --uninstall${RESET}"
