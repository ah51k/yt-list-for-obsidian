import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, QMessageBox, 
                               QProgressBar, QTextEdit, QFrame, QFileDialog)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon
import os
import re
import json
from yt_dlp import YoutubeDL

class Config:
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser("~"), ".youtube_playlist_config.json")
        self.default_config = {
            "save_directory": os.path.expanduser("~")
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

class PlaylistProcessor(QThread):
    progress_updated = Signal(str)
    finished = Signal(str, str, bool)  # message, details, success
    
    def __init__(self, playlist_url, save_dir):
        super().__init__()
        self.playlist_url = playlist_url
        self.save_dir = save_dir
        
    def run(self):
        try:
            self.progress_updated.emit("Extracting playlist information...")
            
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': True,
            }

            with YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(self.playlist_url, download=False)

            playlist_title = re.sub(r'[\\/*?:"<>|]', "", playlist_info.get('title', 'playlist'))
            main_folder = os.path.join(self.save_dir, f"{playlist_title}_folder")
            videos_folder = os.path.join(main_folder, "videos")
            main_md_filename = os.path.join(main_folder, f"{playlist_title}.md")

            self.progress_updated.emit("Creating folders...")
            
            os.makedirs(main_folder, exist_ok=True)
            os.makedirs(videos_folder, exist_ok=True)

            self.progress_updated.emit("Creating markdown files...")
            
            with open(main_md_filename, 'w', encoding='utf-8') as main_md:
                main_md.write(f"<span class = \"mainpage\">{playlist_title}</span>\n")
                main_md.write("---\n")
                main_md.write("| # | Thumbnail | Title & Duration |\n")
                main_md.write("|---|-----------|------------------|\n")
                
                total_videos = len(playlist_info['entries'])
                for index, entry in enumerate(playlist_info['entries'], start=1):
                    if not entry:
                        continue

                    self.progress_updated.emit(f"Processing video {index}/{total_videos}...")
                    
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
                    thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/default.jpg"
                    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)

                    video_md_filename = f"{safe_title}.md"
                    video_md_path = os.path.join(videos_folder, video_md_filename)

                    with open(video_md_path, 'w', encoding='utf-8') as f:
                        f.write(f"""---
title: "{title}"
media_link: {url}
---
<span class = \"btn-link\"> [[../{playlist_title}|Back]] </span>""")

                    md_row = f"| {index} | ![]({thumbnail_url}) | [[videos/{safe_title}\\|{title}]]<br>⏱ {duration_str} |\n"
                    main_md.write(md_row)

            success_msg = f"✅ Done!\n📁 Folder created: {main_folder}\n📄 File created: {main_md_filename}"
            details = f"Successfully processed {total_videos} videos"
            self.finished.emit(success_msg, details, True)

        except Exception as e:
            error_msg = f"An error occurred during processing: {str(e)}"
            self.finished.emit(error_msg, str(e), False)

class YoutubePlaylistToObsidianApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Playlist to Obsidian")
        self.setGeometry(100, 100, 700, 500)
        self.processor_thread = None
        
        # Load configuration
        self.config = Config()
        self.save_dir = self.config.get_save_directory()

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
        self.browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_button)

        main_layout.addLayout(dir_layout)

        # Buttons section
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        self.process_button = QPushButton("Process Playlist")
        self.process_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.process_button.clicked.connect(self.process_playlist)
        buttons_layout.addWidget(self.process_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.setFont(QFont("Arial", 12, QFont.Bold))
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

        # Disable UI during processing
        self.process_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.playlist_url_entry.setEnabled(False)
        self.browse_button.setEnabled(False)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Start processing thread
        self.processor_thread = PlaylistProcessor(playlist_url, self.save_dir)
        self.processor_thread.progress_updated.connect(self.update_progress)
        self.processor_thread.finished.connect(self.on_processing_finished)
        self.processor_thread.start()

    def update_progress(self, message):
        self.progress_label.setText(message)

    def on_processing_finished(self, message, details, success):
        # Re-enable UI
        self.process_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.playlist_url_entry.setEnabled(True)
        self.browse_button.setEnabled(True)
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

