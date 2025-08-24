import sys
import logging
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, QMessageBox, 
                               QProgressBar, QTextEdit, QFrame, QFileDialog)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
import os
import re
import json
from yt_dlp import YoutubeDL

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_youtube_url(url):
    """Validate if the URL is a valid YouTube playlist URL"""
    youtube_patterns = [
        r'https?://(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
        r'https?://(?:www\.)?youtube\.com/watch\?.*list=([a-zA-Z0-9_-]+)',
        r'https?://youtu\.be/.*\?.*list=([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True
    return False

class Config:
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser("~"), ".youtube_playlist_config.json")
        self.default_config = {
            "save_directory": os.path.expanduser("~"),
            "base_files_directory": os.path.expanduser("~")
        }
        self.config = self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return self.default_config
        except Exception:
            return self.default_config

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f)
        except Exception:
            pass

    def get_save_directory(self):
        return self.config.get("save_directory", self.default_config["save_directory"])

    def set_save_directory(self, directory):
        self.config["save_directory"] = directory
        self.save_config()

    def get_base_files_directory(self):
        return self.config.get("base_files_directory", self.default_config["base_files_directory"])

    def set_base_files_directory(self, directory):
        self.config["base_files_directory"] = directory
        self.save_config()

class PlaylistProcessor(QThread):
    progress_updated = Signal(str)
    progress_value = Signal(int)  # Progress percentage
    finished = Signal(str, str, bool)  # message, details, success
    
    def __init__(self, playlist_url, save_dir, base_files_dir):
        super().__init__()
        self.playlist_url = playlist_url
        self.save_dir = save_dir
        self.base_files_dir = base_files_dir
        
    def run(self):
        try:
            logger.info(f"Starting playlist processing: {self.playlist_url}")
            self.progress_updated.emit("Validating URL...")
            
            # Validate URL first
            if not validate_youtube_url(self.playlist_url):
                raise ValueError("Invalid YouTube playlist URL. Please check the URL format.")
            
            self.progress_updated.emit("Extracting playlist information...")
            
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': True,
                'ignoreerrors': True,  # Continue on individual video errors
            }

            with YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(self.playlist_url, download=False)
                
            if not playlist_info or 'entries' not in playlist_info:
                raise ValueError("Could not extract playlist information. Please check if the playlist is public and accessible.")

            playlist_title = re.sub(r'[\\/*?:"<>|]', "", playlist_info.get('title', 'playlist'))
            tag_safe_title = re.sub(r'[^\w\-\u0600-\u06FF]+', '-', playlist_title, flags=re.UNICODE)
            safe_folder_name = re.sub(r'[^\w\-\u0600-\u06FF]+', '-', playlist_title, flags=re.UNICODE)
            main_folder = os.path.join(self.save_dir, f"{safe_folder_name}_folder")
            videos_folder = os.path.join(main_folder, "videos")
            main_md_filename = os.path.join(main_folder, f"{safe_folder_name}.md")
            os.makedirs(main_folder, exist_ok=True)
            os.makedirs(videos_folder, exist_ok=True)
            
            # Get banner from playlist thumbnail
            banner_url = playlist_info.get('thumbnail')
            
            playlist_thumbnail = playlist_info.get('thumbnail')
            
            # Create base file
            base_filename = f"{safe_folder_name}.base"
            base_filepath = os.path.join(self.base_files_dir, base_filename)
            
            # Remove /mnt/win/obsidian-vault/ from the videos folder path for base file
            videos_folder_for_base = videos_folder
            if videos_folder.startswith('/mnt/win/obsidian-vault/'):
                videos_folder_for_base = videos_folder.replace('/mnt/win/obsidian-vault/', '', 1)
            
            with open(base_filepath, 'w', encoding='utf-8') as base_file:
                base_file.write(f"""views:
  - type: cards
    name: Table
    filters:
      and:
        - file.inFolder("{videos_folder_for_base}")
    sort:
      - property: playlist_index
        direction: ASC
    imageAspectRatio: 0.5
    image: note.thumbnail
    cardSize: 250""")
            
            with open(main_md_filename, 'w', encoding='utf-8') as main_md:
                main_md.write(f"---\ntags: [playlist]\n")
                if playlist_thumbnail:
                    main_md.write(f'thumbnail: {playlist_thumbnail}\n')
                if banner_url:
                    main_md.write(f'banner: {banner_url}\n')
                    main_md.write(f'banner-x: 50\n')
                    main_md.write(f'banner-y: 50\n')
                main_md.write("---\n")
                main_md.write('---\n')
                main_md.write(f'![[{base_filename}]]\n')
                total_videos = len(playlist_info['entries'])
                # First pass: collect all video info for navigation
                video_info_list = []
                for index, entry in enumerate(playlist_info['entries'], start=1):
                    if not entry:
                        continue
                    
                    video_id = entry['id']
                    title = entry.get('title', 'No Title')
                    duration_seconds = entry.get('duration')
                    if duration_seconds is not None:
                        hours = duration_seconds // 3600
                        minutes = (duration_seconds % 3600) // 60
                        seconds = duration_seconds % 60
                        if hours > 0:
                            duration_str = f"{hours}:{minutes:02}:{seconds:02}"
                        else:
                            duration_str = f"{minutes}:{seconds:02}"
                    else:
                        duration_str = "N/A"
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    # Get highest quality thumbnail for individual videos
                    if 'maxresdefault' in entry.get('thumbnails', []):
                        thumbnail_url = f'https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg'
                    elif 'hqdefault' in entry.get('thumbnails', []):
                        thumbnail_url = f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
                    else:
                        thumbnail_url = f'https://i.ytimg.com/vi/{video_id}/default.jpg'
                    safe_title = re.sub(r'[\\/*?:\"<>|]', "", title)
                    video_md_filename = f"{safe_title}.md"
                    
                    video_info_list.append({
                        'index': index,
                        'title': title,
                        'url': url,
                        'thumbnail_url': thumbnail_url,
                        'duration_str': duration_str,
                        'safe_title': safe_title,
                        'video_md_filename': video_md_filename
                    })
                
                # Second pass: create files with navigation
                for i, video_info in enumerate(video_info_list):
                    percentage_complete = int((i / total_videos) * 100)
                    self.progress_value.emit(percentage_complete)
                    self.progress_updated.emit(f"Processing video {video_info['index']}/{total_videos}...")
                    
                    video_md_path = os.path.join(videos_folder, video_info['video_md_filename'])
                    
                    # Create navigation buttons
                    nav_buttons = []
                    
                    # Previous button (only show if not first video)
                    if i > 0:
                        prev_video = video_info_list[i-1]
                        nav_buttons.append(f'<span class="btn-link">⬅️ [[{prev_video["safe_title"]}|Previous]]</span>')
                    
                    # Back to playlist button
                    nav_buttons.append(f'<span class="btn-link">🏠 [[../{safe_folder_name}|Back to Playlist]]</span>')
                    
                    # Next button (only show if not last video)
                    if i < len(video_info_list) - 1:
                        next_video = video_info_list[i+1]
                        nav_buttons.append(f'<span class="btn-link">[[{next_video["safe_title"]}|Next]] ➡️</span>')
                    
                    # Join navigation buttons
                    navigation_bar = ' | '.join(nav_buttons)
                    
                    with open(video_md_path, 'w', encoding='utf-8') as f:
                        f.write(f"""---
title: '{video_info['title']}'
media_link: {video_info['url']}
thumbnail: {video_info['thumbnail_url']}
duration: {video_info['duration_str']}
playlist_index: {video_info['index']}
tags: [playlist-{tag_safe_title}]
---

{navigation_bar}""")

            # Emit 100% completion
            self.progress_value.emit(100)
            
            success_msg = f"✅ Done!\n📁 Folder created: {main_folder}\n📄 File created: {main_md_filename}\n📄 Base file created: {base_filepath}"
            details = f"Successfully processed {total_videos} videos"
            logger.info(f"Successfully processed playlist with {total_videos} videos")
            self.finished.emit(success_msg, details, True)

        except Exception as e:
            error_msg = f"An error occurred during processing: {str(e)}"
            self.finished.emit(error_msg, str(e), False)

class YoutubePlaylistToObsidianApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Playlist to Obsidian")
        self.setGeometry(100, 100, 700, 600)
        self.processor_thread = None
        
        # Load configuration
        self.config = Config()
        self.save_dir = self.config.get_save_directory()
        self.base_files_dir = self.config.get_base_files_directory()

        # Enhanced Dark Mode Configuration
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background-color: #2c2c2c;
                color: #e0e0e0;
                border: 2px solid #4a4a4a;
                border-radius: 10px;
                padding: 12px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
                color: #888888;
            }
            QPushButton#clearButton {
                background-color: #d13438;
            }
            QPushButton#clearButton:hover {
                background-color: #b71c1c;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
            QProgressBar {
                border: 2px solid #4a4a4a;
                border-radius: 8px;
                text-align: center;
                background-color: #2c2c2c;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 6px;
            }
            QTextEdit {
                background-color: #2c2c2c;
                color: #e0e0e0;
                border: 2px solid #4a4a4a;
                border-radius: 8px;
                padding: 8px;
            }
            QFrame#separator {
                background-color: #4a4a4a;
                max-height: 1px;
            }
        """)

        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        self.setLayout(main_layout)

        # Header section
        header_layout = QHBoxLayout()
        
        # Title
        self.title_label = QLabel("YouTube Playlist to Obsidian")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.title_label)
        
        main_layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.HLine)
        main_layout.addWidget(separator)

        # Input section
        self.label = QLabel("Enter YouTube Playlist URL:")
        self.label.setFont(QFont("Arial", 12))
        self.label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.label)

        self.playlist_url_entry = QLineEdit()
        self.playlist_url_entry.setPlaceholderText("Enter playlist URL here...")
        self.playlist_url_entry.setFont(QFont("Arial", 11))
        main_layout.addWidget(self.playlist_url_entry)

        # Save directory section
        dir_layout = QHBoxLayout()
        
        self.dir_label = QLabel("Save Directory:")
        self.dir_label.setFont(QFont("Arial", 12))
        dir_layout.addWidget(self.dir_label)

        self.dir_entry = QLineEdit()
        self.dir_entry.setText(self.save_dir)
        self.dir_entry.setReadOnly(True)
        self.dir_entry.setFont(QFont("Arial", 11))
        dir_layout.addWidget(self.dir_entry)

        self.browse_button = QPushButton("Browse")
        self.browse_button.setFont(QFont("Arial", 11))
        self.browse_button.setToolTip("Select directory to save playlist files (Ctrl+O)")
        self.browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_button)

        main_layout.addLayout(dir_layout)

        # Base files directory section
        base_dir_layout = QHBoxLayout()
        
        self.base_dir_label = QLabel("Base Files Directory:")
        self.base_dir_label.setFont(QFont("Arial", 12))
        base_dir_layout.addWidget(self.base_dir_label)

        self.base_dir_entry = QLineEdit()
        self.base_dir_entry.setText(self.base_files_dir)
        self.base_dir_entry.setReadOnly(True)
        self.base_dir_entry.setFont(QFont("Arial", 11))
        base_dir_layout.addWidget(self.base_dir_entry)

        self.browse_base_button = QPushButton("Browse")
        self.browse_base_button.setFont(QFont("Arial", 11))
        self.browse_base_button.setToolTip("Select directory to save base files (Ctrl+B)")
        self.browse_base_button.clicked.connect(self.browse_base_directory)
        base_dir_layout.addWidget(self.browse_base_button)

        main_layout.addLayout(base_dir_layout)

        # Buttons section
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        self.process_button = QPushButton("Process Playlist")
        self.process_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.process_button.setToolTip("Process the YouTube playlist and create Obsidian markdown files (Enter)")
        self.process_button.clicked.connect(self.process_playlist)
        buttons_layout.addWidget(self.process_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.clear_button.setToolTip("Clear the input field and reset status (Esc)")
        self.clear_button.clicked.connect(self.clear_input)
        buttons_layout.addWidget(self.clear_button)

        main_layout.addLayout(buttons_layout)

        # Progress section
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status section
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Arial", 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        main_layout.addStretch()
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Enter key to process playlist
        enter_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        enter_shortcut.activated.connect(self.process_playlist)
        
        # Escape key to clear input
        escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape_shortcut.activated.connect(self.clear_input)
        
        # Ctrl+O to browse directory
        browse_shortcut = QShortcut(QKeySequence.Open, self)
        browse_shortcut.activated.connect(self.browse_directory)
        
        # Ctrl+B to browse base directory
        browse_base_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        browse_base_shortcut.activated.connect(self.browse_base_directory)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Save Directory",
            self.save_dir,
            QFileDialog.ShowDirsOnly
        )
        if dir_path:
            self.save_dir = dir_path
            self.dir_entry.setText(dir_path)
            self.config.set_save_directory(dir_path)

    def browse_base_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Base Files Directory",
            self.base_files_dir,
            QFileDialog.ShowDirsOnly
        )
        if dir_path:
            self.base_files_dir = dir_path
            self.base_dir_entry.setText(dir_path)
            self.config.set_base_files_directory(dir_path)

    def clear_input(self):
        self.playlist_url_entry.clear()
        self.status_label.setText("")
        self.progress_label.setText("")
        self.progress_bar.setVisible(False)

    def process_playlist(self):
        playlist_url = self.playlist_url_entry.text().strip()
        if not playlist_url:
            self.show_message("Error", "Please enter a playlist URL.", QMessageBox.Critical)
            return
        
        # Validate URL format
        if not validate_youtube_url(playlist_url):
            self.show_message("Error", "Invalid YouTube playlist URL.\nPlease enter a valid YouTube playlist URL.", QMessageBox.Critical)
            return

        # Disable UI during processing
        self.process_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.playlist_url_entry.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.browse_base_button.setEnabled(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Start processing thread
        self.processor_thread = PlaylistProcessor(playlist_url, self.save_dir, self.base_files_dir)
        self.processor_thread.progress_updated.connect(self.update_progress)
        self.processor_thread.progress_value.connect(self.update_progress_bar)
        self.processor_thread.finished.connect(self.on_processing_finished)
        self.processor_thread.start()

    def update_progress(self, message):
        self.progress_label.setText(message)
    
    def update_progress_bar(self, percentage):
        if self.progress_bar.maximum() == 0:  # Switch from indeterminate to determinate
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percentage)

    def on_processing_finished(self, message, details, success):
        # Re-enable UI
        self.process_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.playlist_url_entry.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.browse_base_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("")
        
        # Show result
        self.status_label.setText(message)
        
        if success:
            self.show_message("Success", "Markdown files created successfully!", QMessageBox.Information)
        else:
            self.show_message("Error", message, QMessageBox.Critical)

    def show_message(self, title, text, icon):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon)
        msg_box.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YoutubePlaylistToObsidianApp()
    window.show()
    sys.exit(app.exec())

