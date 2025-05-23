from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
import uuid
from typing import Optional

from .video_generator import generate_text_from_pollinations, generate_images_from_pollinations, create_video_from_images_and_text, adapt_reddit_story_for_video
from .reddit_fetcher import fetch_reddit_stories
from .youtube_downloader import download_youtube_video, OUTPUT_DIR as YT_DOWNLOAD_DIR

app = FastAPI()

# Ensure temp_uploads directory exists
TEMP_UPLOADS_DIR = "backend/temp_uploads"
os.makedirs(TEMP_UPLOADS_DIR, exist_ok=True)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Adjust if your frontend runs on a different port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StoryPrompt(BaseModel):
    prompt: str
    youtube_url: Optional[str] = None
    generate_narration: Optional[bool] = False

class RedditPrompt(BaseModel):
    subreddit: str
    youtube_url: Optional[str] = None
    generate_narration: Optional[bool] = False

# Ensure output directory exists and create it if it doesn't
OUTPUT_DIR = "backend/output_videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Helper function to save uploaded file
async def save_upload_file(upload_file: UploadFile, destination_dir: str) -> str | None:
    if not upload_file:
        return None
    try:
        # Ensure filename is somewhat unique to avoid overwrites during concurrent requests
        filename = f"{uuid.uuid4()}_{upload_file.filename}"
        file_path = os.path.join(destination_dir, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return file_path
    except Exception as e:
        print(f"Error saving uploaded file {upload_file.filename}: {e}")
        return None
    finally:
        if hasattr(upload_file, 'file') and hasattr(upload_file.file, 'close'):
             upload_file.file.close()


# Helper function to clean up a temporary file
def cleanup_temp_file(file_path: str | None):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Cleaned up temporary file: {file_path}")
        except OSError as e:
            print(f"Error deleting temporary file {file_path}: {e}")

# Mount static files directory
# This should be after the OUTPUT_DIR is confirmed to exist
app.mount("/static", StaticFiles(directory=OUTPUT_DIR), name="static")


@app.get("/")
async def root():
    return {"message": "API is running"}

@app.post("/generate_story_video")
async def generate_story_video_endpoint(
    story_prompt_json: str = Form(...), # Expect StoryPrompt as JSON string
    background_image: Optional[UploadFile] = File(None)
):
    try:
        story_prompt = StoryPrompt.parse_raw(story_prompt_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid story_prompt format: {e}")

    prompt = story_prompt.prompt
    youtube_url = story_prompt.youtube_url

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    temp_bg_image_path = None
    temp_yt_video_path = None
    temp_audio_narration_path = None # For generated audio
    video_bg_to_use = None
    image_bg_to_use = None

    try:
        if youtube_url:
            print(f"YouTube URL provided: {youtube_url}. Downloading...")
            temp_yt_video_path = download_youtube_video(youtube_url, output_dir=YT_DOWNLOAD_DIR)
            if temp_yt_video_path:
                video_bg_to_use = temp_yt_video_path
                print(f"YouTube video downloaded to: {temp_yt_video_path}")
            else:
                print(f"Failed to download YouTube video from {youtube_url}. Proceeding without it.")
                # Optionally, raise HTTPException or return a specific message
                # For now, we allow fallback to image background or no background

        if background_image and not video_bg_to_use: # Only use uploaded image if YT video is not used
            if not background_image.content_type.startswith("image/"):
                cleanup_temp_file(temp_yt_video_path) # Clean up downloaded YT video if image is invalid
                raise HTTPException(status_code=400, detail="Uploaded background file must be an image.")
            temp_bg_image_path = await save_upload_file(background_image, TEMP_UPLOADS_DIR)
            if not temp_bg_image_path:
                cleanup_temp_file(temp_yt_video_path)
                raise HTTPException(status_code=500, detail="Could not save uploaded background image.")
            image_bg_to_use = temp_bg_image_path
            print(f"Uploaded background image saved to: {temp_bg_image_path}")
        elif background_image and video_bg_to_use:
            print("Both YouTube URL and background image provided. YouTube video will take precedence.")
            # The uploaded image won't be saved or used in this case. Ensure its temp file is closed by `save_upload_file` if it was processed.

        generated_story = generate_text_from_pollinations(prompt)
        if not generated_story:
            raise HTTPException(status_code=500, detail="Failed to generate story text")

        # Generate narration if requested
        if story_prompt.generate_narration:
            print(f"Narration requested for story. Generating audio for: '{generated_story[:100]}...'") # Log first 100 chars
            temp_audio_narration_path = generate_audio_from_pollinations(generated_story)
            if temp_audio_narration_path:
                print(f"Audio narration generated: {temp_audio_narration_path}")
            else:
                print("Failed to generate audio narration for story. Proceeding without it.")
                # Optionally, raise an error or inform client, for now just proceed

        text_segments = [s.strip() for s in generated_story.split('.') if s.strip() and len(s.strip()) > 5]
        if not text_segments:
            text_segments = [generated_story] if generated_story.strip() else ["Default text."]

        num_images_to_generate = min(len(text_segments), 5)
        ai_image_paths = generate_images_from_pollinations(prompt, num_images=num_images_to_generate)
        if not ai_image_paths:
            raise HTTPException(status_code=500, detail="Failed to generate AI images")

        if len(ai_image_paths) < len(text_segments):
            text_segments = text_segments[:len(ai_image_paths)]
        elif not ai_image_paths and text_segments:
             raise HTTPException(status_code=500, detail="Generated text segments but no AI images could be created.")

        output_video_filename = os.path.join(OUTPUT_DIR, f"story_{uuid.uuid4()}.mp4")
        
        test_segment = (0, 10) if video_bg_to_use else None 

        video_path = create_video_from_images_and_text(
            image_paths=ai_image_paths,
            text_segments=text_segments,
            output_path=output_video_filename,
            background_image_path=image_bg_to_use, 
            video_background_path=video_bg_to_use,
            video_background_segment=test_segment,
            audio_narration_path=temp_audio_narration_path
        )

        if not video_path:
            raise HTTPException(status_code=500, detail="Failed to create video")

        return {"video_path": video_path, "story": generated_story}
    finally:
        cleanup_temp_file(temp_bg_image_path)
        cleanup_temp_file(temp_yt_video_path)
        cleanup_temp_file(temp_audio_narration_path) # Cleanup generated audio


@app.post("/generate_reddit_video")
async def generate_reddit_video_endpoint(
    reddit_prompt_json: str = Form(...), # Expect RedditPrompt as JSON string
    background_image: Optional[UploadFile] = File(None)
):
    try:
        reddit_prompt = RedditPrompt.parse_raw(reddit_prompt_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid reddit_prompt format: {e}")

    subreddit_name = reddit_prompt.subreddit
    youtube_url = reddit_prompt.youtube_url
    
    if not subreddit_name:
        raise HTTPException(status_code=400, detail="Subreddit name cannot be empty")

    temp_bg_image_path = None
    temp_yt_video_path = None
    temp_audio_narration_path = None # For generated audio
    video_bg_to_use = None
    image_bg_to_use = None
    
    try:
        if youtube_url:
            print(f"YouTube URL provided for Reddit video: {youtube_url}. Downloading...")
            temp_yt_video_path = download_youtube_video(youtube_url, output_dir=YT_DOWNLOAD_DIR)
            if temp_yt_video_path:
                video_bg_to_use = temp_yt_video_path
                print(f"YouTube video downloaded to: {temp_yt_video_path}")
            else:
                print(f"Failed to download YouTube video from {youtube_url} for Reddit video.")

        if background_image and not video_bg_to_use:
            if not background_image.content_type.startswith("image/"):
                cleanup_temp_file(temp_yt_video_path)
                raise HTTPException(status_code=400, detail="Uploaded background file must be an image.")
            temp_bg_image_path = await save_upload_file(background_image, TEMP_UPLOADS_DIR)
            if not temp_bg_image_path:
                cleanup_temp_file(temp_yt_video_path)
                raise HTTPException(status_code=500, detail="Could not save uploaded background image.")
            image_bg_to_use = temp_bg_image_path
            print(f"Uploaded background image for Reddit video saved to: {temp_bg_image_path}")
        elif background_image and video_bg_to_use:
            print("Both YouTube URL and background image provided for Reddit video. YouTube video will take precedence.")


        stories = fetch_reddit_stories(subreddit_name, limit=1)
        if not stories:
            raise HTTPException(status_code=404, detail=f"No stories found for subreddit r/{subreddit_name} or subreddit does not exist.")

        first_story = stories[0]
        original_title = first_story['title']
        original_selftext = first_story['selftext']

        video_script = adapt_reddit_story_for_video(original_title, original_selftext)
        if not video_script:
            raise HTTPException(status_code=500, detail="Failed to adapt Reddit story into video script.")

        # Generate narration if requested
        if reddit_prompt.generate_narration:
            print(f"Narration requested for Reddit story. Generating audio for: '{video_script[:100]}...'")
            temp_audio_narration_path = generate_audio_from_pollinations(video_script)
            if temp_audio_narration_path:
                print(f"Audio narration generated for Reddit story: {temp_audio_narration_path}")
            else:
                print("Failed to generate audio narration for Reddit story. Proceeding without it.")

        text_segments = [s.strip() for s in video_script.split('.') if s.strip() and len(s.strip()) > 5]
        if not text_segments:
            text_segments = [video_script] if video_script.strip() else [original_title]

        image_prompt_basis = text_segments[0] if text_segments else original_title
        num_images_to_generate = min(len(text_segments), 5)
        
        ai_image_paths = generate_images_from_pollinations(image_prompt_basis, num_images=num_images_to_generate)
        if not ai_image_paths:
            raise HTTPException(status_code=500, detail="Failed to generate AI images for Reddit video.")

        if len(ai_image_paths) < len(text_segments):
            text_segments = text_segments[:len(ai_image_paths)]
        elif not ai_image_paths and text_segments:
            raise HTTPException(status_code=500, detail="Generated text segments but no AI images could be created.")

        output_video_filename = os.path.join(OUTPUT_DIR, f"reddit_{subreddit_name}_{uuid.uuid4()}.mp4")
        
        test_segment = (0, 10) if video_bg_to_use else None

        video_path = create_video_from_images_and_text(
            image_paths=ai_image_paths,
            text_segments=text_segments,
            output_path=output_video_filename,
            background_image_path=image_bg_to_use,
            video_background_path=video_bg_to_use,
            video_background_segment=test_segment,
            audio_narration_path=temp_audio_narration_path
        )

        if not video_path:
            raise HTTPException(status_code=500, detail="Failed to create video from Reddit story.")

        return {
            "video_path": video_path,
            "original_title": original_title,
            "video_script": video_script
        }
    finally:
        cleanup_temp_file(temp_bg_image_path)
        cleanup_temp_file(temp_yt_video_path)
        cleanup_temp_file(temp_audio_narration_path) # Cleanup generated audio
