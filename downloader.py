import os
import json
import yt_dlp
import ffmpeg
from urllib.parse import urlparse
import re
import logging

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self):
        self.supported_domains = [
            'youtube.com', 'youtu.be', 'tiktok.com', 'vm.tiktok.com',
            'instagram.com', 'fb.com', 'facebook.com', 'www.tiktok.com',
            'www.instagram.com', 'www.facebook.com'
        ]
        self.cookies_file = self.get_cookies_file()
    
    def get_cookies_file(self):
        """Find and return the cookies file path"""
        possible_paths = [
            'cookies.txt',
            'cookies/cookies.txt', 
            os.path.expanduser('~/.config/yt-dlp/cookies.txt'),
            '/etc/yt-dlp/cookies.txt'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found cookies file: {path}")
                return path
        
        logger.info("No cookies file found, proceeding without cookies")
        return None
    
    def fix_shorts_url(self, url):
        """Fix YouTube Shorts URLs to regular watch URLs"""
        if 'youtube.com/shorts/' in url:
            video_id = url.split('/')[-1].split('?')[0]
            return f'https://www.youtube.com/watch?v={video_id}'
        return url
    
    def sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        if len(filename) > 100:
            filename = filename[:100]
        return filename.strip()
    
    def get_video_info(self, url):
        """Get video information and available formats"""
        try:
            # Fix YouTube Shorts URLs
            url = self.fix_shorts_url(url)
            
            # Get extractor options
            ydl_opts = self.get_extractor_opts(url)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get full info with processing
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Extract basic video info
                video_info = {
                    'title': self.sanitize_filename(info.get('title', 'Unknown Title')),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self.format_duration(info.get('duration', 0)),
                    'uploader': info.get('uploader', 'Unknown Uploader'),
                    'webpage_url': info.get('webpage_url', url),
                    'formats': []
                }
                
                # Extract available formats
                formats = self.extract_formats(info)
                video_info['formats'] = formats
                
                logger.info(f"Found {len(formats)} formats for: {video_info['title']}")
                return video_info
                
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            return None
    
    def get_extractor_opts(self, url):
        """Get extractor options based on platform"""
        opts = {
            'quiet': True,
            'no_warnings': False,
            'extract_flat': False,
        }
        
        # Add cookies if available
        if self.cookies_file:
            opts['cookiefile'] = self.cookies_file
            logger.info(f"Using cookies file: {self.cookies_file}")
        
        # YouTube specific options - 4K support enabled
        if 'youtube.com' in url or 'youtu.be' in url:
            opts.update({
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web', 'android', 'ios'],  # Multiple clients for 4K
                        'player_skip': ['configs'],
                        'formats': ['best', '4k', '1080p', '720p', '480p', '360p']  # Explicitly request 4K
                    }
                }
            })
        
        # Facebook specific options
        elif 'facebook.com' in url or 'fb.com' in url:
            opts.update({
                'extractor_args': {
                    'facebook': {
                        'credentials': None
                    }
                }
            })
        
        # Instagram specific options  
        elif 'instagram.com' in url:
            opts.update({
                'extractor_args': {
                    'instagram': {
                        'shortcode_match': True
                    }
                }
            })
        
        return opts
    
    def extract_formats(self, info):
        """Extract and organize all available formats with 4K support"""
        formats = []
        
        # Add best MP3 audio format
        formats.append({
            'format_id': 'mp3',
            'ext': 'mp3',
            'resolution': 'MP3 Audio (192kbps)',
            'filesize': 'Unknown',
            'type': 'audio',
            'quality': 1
        })
        
        # Process each format
        for f in info.get('formats', []):
            format_info = self.create_format_info(f)
            if format_info and self.is_valid_format(format_info):
                formats.append(format_info)
        
        # Add combined formats for ALL quality videos including 4K
        combined_formats = self.create_combined_formats(info.get('formats', []))
        formats.extend(combined_formats)
        
        # Add auto formats
        formats.extend([
            {
                'format_id': 'best',
                'ext': 'mp4',
                'resolution': 'BEST (Auto Select)',
                'filesize': 'Unknown',
                'type': 'video+audio',
                'quality': 10000
            },
            {
                'format_id': 'bestvideo+bestaudio',
                'ext': 'mp4',
                'resolution': 'BEST VIDEO + BEST AUDIO (4K Ready)',
                'filesize': 'Unknown',
                'type': 'video+audio',
                'quality': 15000
            },
            {
                'format_id': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'ext': 'mp4',
                'resolution': '1080p MAX (Auto Merge)',
                'filesize': 'Unknown',
                'type': 'video+audio',
                'quality': 1080
            },
            {
                'format_id': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
                'ext': 'mp4',
                'resolution': '4K MAX (Auto Merge)',
                'filesize': 'Unknown',
                'type': 'video+audio',
                'quality': 2160
            }
        ])
        
        # Remove duplicates and sort
        return self.deduplicate_and_sort_formats(formats)
    
    def create_format_info(self, format_dict):
        """Create standardized format info"""
        format_note = format_dict.get('format_note', 'unknown')
        if format_note == 'unknown' and format_dict.get('height'):
            format_note = f"{format_dict['height']}p"
        
        # Skip storyboard formats
        if format_dict.get('format_id', '').startswith('sb'):
            return None
        
        # Detect 4K formats
        height = format_dict.get('height', 0)
        if height >= 2160:
            format_note = f"{height}p (4K)"
        elif height >= 1440:
            format_note = f"{height}p (2K)"
        
        return {
            'format_id': format_dict['format_id'],
            'ext': format_dict.get('ext', 'mp4'),
            'resolution': format_note.upper() if format_note != 'unknown' else 'N/A',
            'filesize': self.format_filesize(format_dict.get('filesize')),
            'type': self.get_format_type(format_dict),
            'quality': self.get_quality_value(format_note, format_dict),
            'has_audio': format_dict.get('acodec') != 'none',
            'has_video': format_dict.get('vcodec') != 'none',
        }
    
    def get_format_type(self, format_dict):
        """Determine format type"""
        has_video = format_dict.get('vcodec') != 'none'
        has_audio = format_dict.get('acodec') != 'none'
        
        if has_video and has_audio:
            return 'video+audio'
        elif has_video:
            return 'video'
        elif has_audio:
            return 'audio'
        else:
            return 'unknown'
    
    def is_valid_format(self, format_info):
        """Check if format should be included"""
        # Skip formats without video or audio
        if not format_info['has_video'] and not format_info['has_audio']:
            return False
        
        # Skip very low quality audio
        if format_info['type'] == 'audio' and format_info.get('abr', 0) < 50:
            return False
            
        return True
    
    def create_combined_formats(self, all_formats):
        """Create combined formats for ALL quality videos including 4K"""
        combined = []
        
        # Find best video-only and audio-only formats
        video_formats = [f for f in all_formats if f.get('vcodec') != 'none' and f.get('acodec') == 'none']
        audio_formats = [f for f in all_formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
        # Sort video formats by quality (highest first)
        video_formats.sort(key=lambda x: x.get('height', 0), reverse=True)
        
        # Create combined formats for all high-quality video formats
        for video_fmt in video_formats:
            height = video_fmt.get('height', 0)
            if height >= 360:  # Include all formats from 360p to 4K
                combined.append({
                    'format_id': f"{video_fmt['format_id']}+bestaudio",
                    'ext': 'mp4',
                    'resolution': f"{height}p (+AUDIO)",
                    'filesize': 'Unknown',
                    'type': 'video+audio',
                    'quality': height + 1000
                })
        
        # Special 4K combined format
        combined.append({
            'format_id': 'bestvideo[height>=2160]+bestaudio/best[height>=2160]',
            'ext': 'mp4',
            'resolution': '4K ULTRA (+AUDIO)',
            'filesize': 'Unknown',
            'type': 'video+audio',
            'quality': 5000
        })
        
        return combined
    
    def deduplicate_and_sort_formats(self, formats):
        """Remove duplicates and sort formats by quality"""
        seen = set()
        unique_formats = []
        
        for f in formats:
            key = (f['resolution'], f['type'], f['quality'])
            if key not in seen:
                seen.add(key)
                unique_formats.append(f)
        
        # Sort by quality (highest first)
        unique_formats.sort(key=lambda x: x['quality'], reverse=True)
        
        return unique_formats
    
    def get_quality_value(self, resolution, format_dict=None):
        """Convert resolution to numeric value for sorting"""
        resolution_map = {
            '144P': 144, '240P': 240, '360P': 360, '480P': 480,
            '720P': 720, '1080P': 1080, '1440P': 1440, '2160P': 2160,
            '4320P': 4320, '4K': 2160, '2K': 1440,
            'BEST': 10000, 'N/A': 0, 'MP3 AUDIO (192KBPS)': 1
        }
        
        # Try to get from resolution map
        resolution_upper = resolution.upper()
        quality = resolution_map.get(resolution_upper, 0)
        
        # Extract from resolution string like "2160p"
        if quality == 0:
            match = re.search(r'(\d+)p', resolution_upper)
            if match:
                quality = int(match.group(1))
        
        # If not found, try to extract from height
        if quality == 0 and format_dict and format_dict.get('height'):
            quality = format_dict['height']
        
        return quality
    
    def format_duration(self, seconds):
        """Format duration in seconds to HH:MM:SS"""
        if not seconds:
            return "Unknown"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def format_filesize(self, size_bytes):
        """Format file size in human readable format"""
        if not size_bytes:
            return "Unknown"
        
        try:
            size_float = float(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_float < 1024.0:
                    return f"{size_float:.1f} {unit}"
                size_float /= 1024.0
            return f"{size_float:.1f} TB"
        except (TypeError, ValueError):
            return "Unknown"
    
    def progress_hook(self, d, progress_callback=None):
        """Progress hook for yt-dlp"""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            percent = 0
            if total_bytes > 0:
                percent = (downloaded_bytes / total_bytes) * 100
            
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            progress_info = {
                'status': 'downloading',
                'percent': round(percent, 1),
                'speed': f"{speed / 1024 / 1024:.1f} MB/s" if speed else "0 MB/s",
                'eta': f"{eta} seconds" if eta else "Unknown",
                'filesize': self.format_filesize(total_bytes),
                'filename': os.path.basename(d.get('filename', '')),
                'message': 'Downloading...'
            }
            
            if progress_callback:
                progress_callback(progress_info)
                
        elif d['status'] == 'finished':
            progress_info = {
                'status': 'completed',
                'percent': 100,
                'speed': '0 MB/s',
                'eta': '0 seconds',
                'filesize': self.format_filesize(d.get('total_bytes', 0)),
                'filename': os.path.basename(d.get('filename', '')),
                'message': 'Download completed!'
            }
            
            if progress_callback:
                progress_callback(progress_info)
    
    def download(self, url, format_id, download_type, downloads_folder, progress_callback=None):
        """Download video or audio with 4K and auto-merge support"""
        try:
            # Fix YouTube Shorts URLs
            url = self.fix_shorts_url(url)
            
            # Create downloads folder if it doesn't exist
            os.makedirs(downloads_folder, exist_ok=True)
            
            # Configure download options
            ydl_opts = self.get_download_options(download_type, format_id, downloads_folder, progress_callback)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Handle MP3 conversion
                if download_type == 'audio' or format_id == 'mp3':
                    base_name = os.path.splitext(filename)[0]
                    mp3_file = base_name + '.mp3'
                    
                    if os.path.exists(mp3_file):
                        logger.info(f"MP3 file created: {mp3_file}")
                        return mp3_file
                    else:
                        logger.warning(f"MP3 conversion may have failed, returning original file: {filename}")
                        return filename
                else:
                    if os.path.exists(filename):
                        logger.info(f"Video file created: {filename}")
                        return filename
                    else:
                        base_name = os.path.splitext(filename)[0]
                        for ext in ['.mp4', '.mkv', '.webm', '.m4a']:
                            possible_file = base_name + ext
                            if os.path.exists(possible_file):
                                logger.info(f"Found file with different extension: {possible_file}")
                                return possible_file
                
                logger.error(f"Downloaded file not found: {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            if progress_callback:
                progress_callback({
                    'status': 'error',
                    'message': f'Download failed: {str(e)}'
                })
            return None
    
    def get_download_options(self, download_type, format_id, downloads_folder, progress_callback):
        """Get appropriate download options with 4K and merge support"""
        base_opts = {
            'outtmpl': os.path.join(downloads_folder, '%(title)s.%(ext)s'),
            'progress_hooks': [lambda d: self.progress_hook(d, progress_callback)],
            'quiet': True,
            'no_warnings': False,
        }
        
        # Add platform-specific options
        url_specific_opts = self.get_extractor_opts('')
        base_opts.update(url_specific_opts)
        
        if download_type == 'audio' or format_id == 'mp3':
            # Audio download
            base_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Video download with auto-merge for 4K
            base_opts.update({
                'format': format_id,
                'merge_output_format': 'mp4',  # Auto merge to mp4
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            })
        
        return base_opts
