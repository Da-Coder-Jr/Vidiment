import yt_dlp
import os
import uuid

OUTPUT_DIR = "backend/temp_yt_downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_youtube_video(url: str, output_dir: str = OUTPUT_DIR) -> str | None:
    """
    Downloads a YouTube video to the specified directory.

    Args:
        url: The URL of the YouTube video.
        output_dir: The directory to save the downloaded video.

    Returns:
        The file path of the downloaded video, or None if download fails.
    """
    # Generate a unique filename to prevent collisions and ensure predictability
    unique_id = str(uuid.uuid4())
    output_filename_template = f"{unique_id}.%(ext)s" # yt-dlp will fill in the extension
    output_filepath_template = os.path.join(output_dir, output_filename_template)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        'outtmpl': output_filepath_template,
        'merge_output_format': 'mp4',
        'noplaylist': True, # Download only the video if URL is part of a playlist
        'quiet': True, # Suppress yt-dlp console output
        # 'verbose': False, # Ensure verbose is not True if quiet is True
    }

    actual_downloaded_filepath = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False) # Get info first
            # Construct the expected filename based on the info
            # This is more reliable than trying to guess after download or listing dir
            ext = info_dict.get('ext', 'mp4') # Default to mp4 if ext not found
            actual_downloaded_filepath = os.path.join(output_dir, f"{unique_id}.{ext}")
            
            # Now set the outtmpl to the exact path for download
            ydl.params['outtmpl'] = actual_downloaded_filepath 
            ydl.download([url])

        if actual_downloaded_filepath and os.path.exists(actual_downloaded_filepath):
            print(f"Successfully downloaded YouTube video to: {actual_downloaded_filepath}")
            return actual_downloaded_filepath
        else:
            # Fallback: if the above method for path reconstruction failed, try to find the file
            # This is less ideal but can be a backup.
            # For simplicity, the current approach with explicit outtmpl should work.
            # If not, this is where one might list the directory for a file matching unique_id.
            print(f"Download completed but could not confirm file path for ID {unique_id} in {output_dir}")
            # Try to find it - this is a bit of a hack, ideally outtmpl is king
            for f in os.listdir(output_dir):
                if f.startswith(unique_id):
                    print(f"Found matching file: {f}")
                    return os.path.join(output_dir,f)
            return None

    except yt_dlp.utils.DownloadError as de:
        if "is not a valid URL" in str(de) or "Unsupported URL" in str(de):
             print(f"Invalid or unsupported YouTube URL: {url}. Error: {de}")
        else:
            print(f"Error downloading YouTube video: {url}. Error: {de}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during YouTube video download: {url}. Error: {e}")
        return None

if __name__ == '__main__':
    # Test cases
    test_url_valid = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Rick Astley - for testing, short
    # test_url_valid_short = "https://www.youtube.com/watch?v=example" # Replace with a real short video URL
    test_url_invalid = "https://www.youtube.com/watch?v=invalidvideo123abc"
    test_url_not_youtube = "https://www.google.com"

    print(f"Testing with valid URL: {test_url_valid}")
    file_path = download_youtube_video(test_url_valid)
    if file_path:
        print(f"Downloaded to: {file_path}")
        # Clean up the downloaded file
        # try:
        #     os.remove(file_path)
        #     print(f"Cleaned up: {file_path}")
        # except OSError as e:
        #     print(f"Error cleaning up test file {file_path}: {e}")
    else:
        print("Download failed.")

    # print(f"\nTesting with invalid URL: {test_url_invalid}")
    # file_path_invalid = download_youtube_video(test_url_invalid)
    # if file_path_invalid:
    #     print(f"Downloaded to: {file_path_invalid}") # Should not happen
    # else:
    #     print("Download failed as expected.")

    # print(f"\nTesting with non-YouTube URL: {test_url_not_youtube}")
    # file_path_not_yt = download_youtube_video(test_url_not_youtube)
    # if file_path_not_yt:
    #     print(f"Downloaded to: {file_path_not_yt}") # Should not happen
    # else:
    #     print("Download failed as expected.")
