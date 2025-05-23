import requests
import uuid
import os
from moviepy.editor import ImageClip, TextClip, concatenate_videoclips, CompositeVideoClip, VideoFileClip, AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip # Explicit import for clarity
from typing import Optional # For type hinting

# Ensure temp_images directory exists
TEMP_IMAGE_DIR = "backend/temp_images"
os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

TEMP_AUDIO_DIR = "backend/temp_audio" # For generated audio
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)


def generate_audio_from_pollinations(text: str, output_dir: str = TEMP_AUDIO_DIR, voice: str = "nova") -> Optional[str]:
    """
    Generates audio from text using the Pollinations.ai TTS API and saves it locally.
    Voices: alloy, echo, fable, onyx, nova, shimmer
    """
    if not text:
        print("No text provided for audio generation.")
        return None

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    try:
        # URL encode the text to make it safe for URL
        encoded_text = requests.utils.quote(text)
        # Construct the API URL
        url = f"https://text.pollinations.ai/{encoded_text}?model=openai-audio&voice={voice}"
        
        print(f"Requesting audio from Pollinations: {url}")
        response = requests.get(url, timeout=120) # Increased timeout for potentially long audio
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Save the audio data to a uniquely named file
        audio_filename = os.path.join(output_dir, f"{uuid.uuid4()}.mp3") # Assuming MP3 output
        with open(audio_filename, "wb") as f:
            f.write(response.content)
        
        print(f"Audio successfully generated and saved to: {audio_filename}")
        return audio_filename

    except requests.exceptions.RequestException as e:
        print(f"Error generating audio from Pollinations: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Pollinations API Response Status: {e.response.status_code}")
            print(f"Pollinations API Response Body: {e.response.text}")
        return None
    except IOError as e:
        print(f"Error saving audio file: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during audio generation: {e}")
        return None


def generate_text_from_pollinations(prompt: str) -> str:
    """
    Generates text using the Pollinations.ai text generation API.
    """
    url = f"https://text.pollinations.ai/{requests.utils.quote(prompt)}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error generating text from Pollinations: {e}")
        return "" # Return empty string or raise a custom exception

def generate_images_from_pollinations(prompt: str, num_images: int = 3) -> list[str]:
    """
    Generates images using the Pollinations.ai image generation API and saves them locally.
    Returns a list of file paths to the saved images.
    """
    image_paths = []
    for _ in range(num_images):
        image_prompt = f"{prompt} {uuid.uuid4()}" # Add UUID to prompt for unique images
        url = f"https://pollinations.ai/p/{requests.utils.quote(image_prompt)}?model=flux"
        try:
            response = requests.get(url)
            response.raise_for_status()
            image_filename = os.path.join(TEMP_IMAGE_DIR, f"{uuid.uuid4()}.jpg")
            with open(image_filename, "wb") as f:
                f.write(response.content)
            image_paths.append(image_filename)
        except requests.exceptions.RequestException as e:
            print(f"Error generating image from Pollinations: {e}")
        except IOError as e:
            print(f"Error saving image: {e}")
    return image_paths

def create_video_from_images_and_text(image_paths: list[str], text_segments: list[str], output_path: str = "output.mp4") -> str:
from moviepy.video.fx.all import loop as moviepy_loop

def create_video_from_images_and_text(
    image_paths: list[str],
    text_segments: list[str],
    output_path: str = "output.mp4",
    background_image_path: Optional[str] = None,
    video_background_path: Optional[str] = None,
    video_background_segment: Optional[tuple[float, float]] = None,
    audio_narration_path: Optional[str] = None
) -> str:
    """
    Creates a video from AI-generated images and text segments, 
    with an optional custom image or video background, and optional audio narration.
    Video background takes precedence over image background.
    """
    if not image_paths:
        print("No AI-generated images provided for video creation.")
        return ""

    clips = []
    scene_duration = 3  # seconds for each AI image + text scene
    video_size = None # Final output video size
    
    active_background_clip = None # This will hold the ImageClip or VideoFileClip for the background
    is_video_bg = False

    # 1. Determine Background
    if video_background_path:
        try:
            if not os.path.exists(video_background_path):
                raise FileNotFoundError(f"Video background not found at {video_background_path}")
            
            print(f"Loading video background: {video_background_path}")
            temp_video_bg_clip = VideoFileClip(video_background_path)
            
            if video_background_segment:
                start_time, end_time = video_background_segment
                if start_time >= temp_video_bg_clip.duration:
                    print(f"Warning: Video background segment start time {start_time}s is beyond video duration {temp_video_bg_clip.duration}s. Using full video.")
                    active_background_clip = temp_video_bg_clip
                else:
                    actual_end_time = min(end_time, temp_video_bg_clip.duration)
                    active_background_clip = temp_video_bg_clip.subclip(start_time, actual_end_time)
                    print(f"Using video background segment from {start_time}s to {actual_end_time}s.")
            else:
                active_background_clip = temp_video_bg_clip
            
            video_size = active_background_clip.size
            is_video_bg = True
            print(f"Using video background with size {video_size}. Original duration: {active_background_clip.duration:.2f}s")
            if background_image_path:
                print("Note: Both video and image backgrounds provided. Video background will be used.")

        except Exception as e:
            print(f"Error loading video background '{video_background_path}': {e}. Falling back to image background or no background.")
            if active_background_clip and hasattr(active_background_clip, 'close'): # Close if subclip failed after main load
                active_background_clip.close()
            if temp_video_bg_clip and hasattr(temp_video_bg_clip, 'close') and temp_video_bg_clip != active_background_clip:
                 temp_video_bg_clip.close()
            active_background_clip = None
            video_background_path = None # Ensure fallback
            is_video_bg = False


    if not active_background_clip and background_image_path: # Fallback to image if video failed or not provided
        try:
            if not os.path.exists(background_image_path):
                raise FileNotFoundError(f"Background image not found at {background_image_path}")
            active_background_clip = ImageClip(background_image_path)
            video_size = active_background_clip.size
            is_video_bg = False # It's an image background
            print(f"Using custom image background: {background_image_path} with size {video_size}")
        except Exception as e:
            print(f"Error loading background image '{background_image_path}': {e}. Proceeding without custom background.")
            if active_background_clip and hasattr(active_background_clip, 'close'):
                active_background_clip.close()
            active_background_clip = None
            background_image_path = None

    # 2. Calculate total duration of AI content
    num_ai_images = len(image_paths)
    total_ai_content_duration = num_ai_images * scene_duration

    # 3. Adjust video background duration (loop or cut)
    final_bg_for_compositing = None
    if active_background_clip and is_video_bg:
        if active_background_clip.duration < total_ai_content_duration:
            print(f"Video background duration ({active_background_clip.duration:.2f}s) is shorter than AI content ({total_ai_content_duration:.2f}s). Looping background.")
            try:
                final_bg_for_compositing = moviepy_loop(active_background_clip, duration=total_ai_content_duration)
            except Exception as e: # Sometime loop can fail on very short clips or specific codecs
                print(f"Error looping video background: {e}. Using a single instance of the video background.")
                final_bg_for_compositing = active_background_clip.set_duration(active_background_clip.duration) # Use its original duration
                # total_ai_content_duration might need to be capped later if bg is shorter and not looping
        elif active_background_clip.duration > total_ai_content_duration:
            print(f"Video background duration ({active_background_clip.duration:.2f}s) is longer than AI content ({total_ai_content_duration:.2f}s). Cutting background.")
            final_bg_for_compositing = active_background_clip.subclip(0, total_ai_content_duration)
        else: # Durations match
            final_bg_for_compositing = active_background_clip
    elif active_background_clip and not is_video_bg: # Static image background
        final_bg_for_compositing = active_background_clip.set_duration(scene_duration) # Set duration for scene composition, will be tiled later effectively

    # 4. Create scenes with AI images and text
    num_text_segments = len(text_segments)
    all_scene_clips = [] # Holds each fully composited scene

    for i in range(num_ai_images):
        start_time_for_this_scene = i * scene_duration
        scene_elements = []

        # A. Add background (either video subclip or static image)
        current_bg_segment = None
        if final_bg_for_compositing:
            if is_video_bg: # Looped or cut video background
                current_bg_segment = final_bg_for_compositing.subclip(start_time_for_this_scene, start_time_for_this_scene + scene_duration)
            else: # Static image background, already set to scene_duration
                current_bg_segment = final_bg_for_compositing 
            scene_elements.append(current_bg_segment)
            if not video_size: # Should be set if background is active, but for safety
                 video_size = current_bg_segment.size
        
        # B. Add AI Image
        try:
            ai_image_clip_orig = ImageClip(image_paths[i])
        except Exception as e:
            print(f"Error loading AI image {image_paths[i]}: {e}. Skipping this image for scene {i+1}.")
            # If background exists, we can still make a scene with just text on background
            # If no background either, this scene will be empty or skipped.
            # For now, let's allow text on background.
            ai_image_clip_resized = None # Flag that AI image is missing

        if ai_image_clip_orig: # If AI image loaded successfully
            if video_size: # If there's a background (video or image) defining the size
                target_h = int(video_size[1] * 0.75)
                target_w = int(video_size[0] * 0.90)
                ai_image_clip_resized = ai_image_clip_orig.resize(height=target_h)
                if ai_image_clip_resized.w > target_w:
                    ai_image_clip_resized = ai_image_clip_orig.resize(width=target_w)
                ai_image_clip_resized = ai_image_clip_resized.set_position("center")
            else: # No background, AI image is full frame
                ai_image_clip_resized = ai_image_clip_orig
                if not video_size: video_size = ai_image_clip_resized.size # Define video size by first AI image

            scene_elements.append(ai_image_clip_resized.set_duration(scene_duration))
            # ai_image_clip_orig.close() # Close original if resized version is different object - MoviePy often reuses

        # C. Add Text Overlay
        if i < num_text_segments and text_segments[i]:
            text_clip_w = video_size[0] * 0.8 if video_size else 600
            txt_clip = TextClip(
                text_segments[i], fontsize=24, color='white', bg_color='rgba(0,0,0,0.5)',
                font='Arial', size=(text_clip_w, None), method='caption'
            ).set_position(('center', 'bottom')).set_duration(scene_duration)
            scene_elements.append(txt_clip)

        # D. Composite the scene
        if scene_elements:
            # All elements should have scene_duration. CompositeVideoClip needs a size.
            if not video_size: # Fallback if no bg and no AI images loaded
                print(f"Warning: Scene {i+1} has no defined video size. Skipping.")
                continue
            
            # Ensure all clips in scene_elements are set to the same FPS, e.g., 24
            for clip_idx, clip_item in enumerate(scene_elements):
                if hasattr(clip_item, 'fps') and clip_item.fps is None: # Check if fps is not set
                    scene_elements[clip_idx] = clip_item.set_fps(24)
                elif not hasattr(clip_item, 'fps'): # ImageClips might not have fps by default
                    scene_elements[clip_idx] = clip_item.set_fps(24)


            # If current_bg_segment is a VideoClip, its FPS should ideally be used, or a standard one like 24.
            # TextClip and ImageClip will adapt or need explicit FPS.
            # CompositeVideoClip will use the FPS of the first clip or a specified fps.
            # It's good practice to ensure all source clips for a scene are at a consistent FPS.
            # For now, assuming set_fps(24) on elements if needed, or VideoFileClip sets the standard.

            current_scene_composite = CompositeVideoClip(scene_elements, size=video_size).set_duration(scene_duration)
            all_scene_clips.append(current_scene_composite)
        
        # Clean up original AI image clip if it was loaded and potentially resized
        if 'ai_image_clip_orig' in locals() and ai_image_clip_orig and hasattr(ai_image_clip_orig, 'close'):
            ai_image_clip_orig.close()


    if not all_scene_clips:
        print("No scenes were created. Cannot generate video.")
        if active_background_clip and hasattr(active_background_clip, 'close'): active_background_clip.close()
        if final_bg_for_compositing and final_bg_for_compositing != active_background_clip and hasattr(final_bg_for_compositing, 'close'): final_bg_for_compositing.close()
        return ""

    # 5. Concatenate all scenes
    final_video_composition = concatenate_videoclips(all_scene_clips, method="compose")
    
    # 6. Add Audio Narration if provided
    narration_clip_resource = None # To keep track of audio clip for closing
    if audio_narration_path:
        try:
            if not os.path.exists(audio_narration_path):
                print(f"Audio narration file not found: {audio_narration_path}. Skipping narration.")
            else:
                print(f"Loading audio narration from: {audio_narration_path}")
                narration_clip_resource = AudioFileClip(audio_narration_path)
                # Set the audio of the composite video.
                # The video's duration is determined by total_ai_content_duration.
                # If narration is longer, it will be cut. If shorter, video will have silence at the end.
                final_video_composition = final_video_composition.set_audio(narration_clip_resource)
                print(f"Audio narration added. Video duration: {final_video_composition.duration:.2f}s, Narration duration: {narration_clip_resource.duration:.2f}s")
        except Exception as e:
            print(f"Error adding audio narration: {e}. Proceeding without narration.")
            if narration_clip_resource and hasattr(narration_clip_resource, 'close'):
                narration_clip_resource.close() # Close if loading failed mid-way or set_audio failed

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        print(f"Writing final video to {output_path} with size {final_video_composition.size if final_video_composition else 'N/A'}, duration {final_video_composition.duration if final_video_composition else 'N/A'}s")
        final_video_composition.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    except Exception as e:
        print(f"Error writing video file: {e}")
        return "" # Return empty path on error
    finally:
        # Extensive cleanup
        for scene_clip in all_scene_clips:
            if hasattr(scene_clip, 'close'): scene_clip.close()
        
        if active_background_clip and hasattr(active_background_clip, 'close'):
            active_background_clip.close()
        if final_bg_for_compositing and final_bg_for_compositing != active_background_clip and hasattr(final_bg_for_compositing, 'close'):
            final_bg_for_compositing.close()
        
        if narration_clip_resource and hasattr(narration_clip_resource, 'close'):
            narration_clip_resource.close()
            print(f"Closed audio narration resource: {audio_narration_path}")

        # Clean up temporary AI-generated image files
        for img_path in image_paths:
            try:
                if os.path.exists(img_path): os.remove(img_path)
            except OSError as e:
                print(f"Error deleting temporary AI image {img_path}: {e}")
        
        if final_video_composition and hasattr(final_video_composition, 'close'):
            final_video_composition.close()

    return output_path

def adapt_reddit_story_for_video(reddit_title: str, reddit_body: str) -> str:
    """
    Adapts a Reddit story (title + selftext) into a script suitable for video narration
    using the Pollinations.ai text generation API.
    """
    prompt = f"Create a short video script summarizing the following Reddit post titled '{reddit_title}': {reddit_body}. The script should be engaging and suitable for a short video, broken into small segments for narration over images. Each segment should be a sentence or two."
    
    # Call the existing generate_text_from_pollinations function
    video_script = generate_text_from_pollinations(prompt)
    
    if not video_script:
        # Fallback or error handling if script generation fails
        # For example, use a simpler version or return a default script
        print(f"Pollinations AI failed to generate script for: {reddit_title}. Using title as script.")
        return reddit_title # Fallback to just title if generation fails
        
    return video_script
