# yt-list-for-obsidian
dont forget to download the libraries
1 PySide6
2 PySide6

## for windows
### 1
python -m venv .venv
. .\.venv\Scripts\Activate.ps1

### 2
python -m pip install --upgrade pip

### 3
python -m pip install yt-dlp PySide6

## for linux 
### 1
#### Ubuntu/Dibian
sudo apt update && sudo apt install -y python3-venv python3-pip
#### Fedora:
sudo dnf install -y python3-pip python3-virtualenv
#### Arch:
sudo pacman -S --noconfirm python-pip python-virtualenv

### 2
python3 -m venv .venv
source .venv/bin/activate

### 3
python3 -m pip install --upgrade pip

### 4
python3 -m pip install yt-dlp PySide6
