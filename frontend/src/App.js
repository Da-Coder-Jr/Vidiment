import React, { useState, useRef } from 'react';
import './App.css';

function App() {
  const [prompt, setPrompt] = useState('');
  const [subreddit, setSubreddit] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [story, setStory] = useState('');
  const [error, setError] = useState('');
  const [backgroundImageFile, setBackgroundImageFile] = useState(null);
  
  const [storyYoutubeUrl, setStoryYoutubeUrl] = useState('');
  const [redditYoutubeUrl, setRedditYoutubeUrl] = useState('');

  const [storyGenerateNarration, setStoryGenerateNarration] = useState(false);
  const [redditGenerateNarration, setRedditGenerateNarration] = useState(false);

  const storyFileInputRef = useRef(null); 
  const redditFileInputRef = useRef(null);


  const handleFileChange = (event) => {
    // Allow clearing the file by selecting the same file input
    // This logic might need adjustment if we want one file input to serve both forms
    // and clear independently. For now, one background image can be "active".
    setBackgroundImageFile(event.target.files[0]);
  };

  const commonApiCall = async (url, formData, isStoryVideo = true) => {
    setIsLoading(true);
    setVideoUrl('');
    if (isStoryVideo) {
      setStory('');
    } else {
      setStory(''); 
    }
    setError('');

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData, 
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setVideoUrl(`http://localhost:8000/static/${data.video_path.split('/').pop()}`);
      if (isStoryVideo) {
        setStory(data.story);
      } else {
        setStory(data.video_script || data.original_title); 
      }
      
      // Reset common fields
      setBackgroundImageFile(null);
      if (storyFileInputRef.current) {
        storyFileInputRef.current.value = "";
      }
      if (redditFileInputRef.current) {
        redditFileInputRef.current.value = "";
      }
      setStoryYoutubeUrl(''); 
      setRedditYoutubeUrl(''); 
      // Do not reset narration checkboxes here, user might want to keep the preference
      // setStoryGenerateNarration(false); 
      // setRedditGenerateNarration(false);


    } catch (e) {
      console.error('Failed to generate video:', e);
      setError(`Failed to generate video: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateStoryVideo = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt for the story video.');
      return;
    }
    
    const formData = new FormData();
    const storyPromptData = { 
        prompt: prompt,
        generate_narration: storyGenerateNarration 
    };
    if (storyYoutubeUrl.trim()) {
        storyPromptData.youtube_url = storyYoutubeUrl.trim();
    }
    formData.append('story_prompt_json', new Blob([JSON.stringify(storyPromptData)], { type: 'application/json'}));

    if (backgroundImageFile) {
      formData.append('background_image', backgroundImageFile);
    }

    commonApiCall('http://localhost:8000/generate_story_video', formData, true);
  };

  const handleGenerateRedditVideo = async () => { 
    if (!subreddit.trim()) {
      setError('Please enter a subreddit name.');
      return;
    }
    
    const formData = new FormData();
    const redditPromptData = { 
        subreddit: subreddit,
        generate_narration: redditGenerateNarration
    };
    if (redditYoutubeUrl.trim()) {
        redditPromptData.youtube_url = redditYoutubeUrl.trim();
    }
    formData.append('reddit_prompt_json', new Blob([JSON.stringify(redditPromptData)], { type: 'application/json'}));

    // Logic for handling background image for Reddit:
    // If you want a separate file input for Reddit, use a different state and ref for it.
    // For now, using the single `backgroundImageFile` state.
    if (backgroundImageFile) { 
      formData.append('background_image', backgroundImageFile);
    }
    
    commonApiCall('http://localhost:8000/generate_reddit_video', formData, false);
  };


  return (
    <div className="App">
      <header className="App-header">
        <h1>AI Video Generator</h1>
      </header>
      <main>
        <section className="generator-section">
          <h2>Story Video Generator</h2>
          <div className="input-section">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter your story prompt here..."
              rows="4"
              disabled={isLoading}
            />
            <input
              type="text"
              value={storyYoutubeUrl}
              onChange={(e) => setStoryYoutubeUrl(e.target.value)}
              placeholder="Enter YouTube Background URL (optional)"
              disabled={isLoading}
              className="youtube-url-input"
            />
            <div className="file-input-container">
              <label htmlFor="bg-upload-story">Optional Background Image (overridden by YouTube URL):</label>
              <input
                type="file"
                id="bg-upload-story"
                accept="image/*"
                onChange={handleFileChange} // This will set the shared backgroundImageFile
                ref={storyFileInputRef}
                disabled={isLoading}
              />
            </div>
            <div className="checkbox-container">
              <input
                type="checkbox"
                id="storyNarration"
                name="storyNarration"
                checked={storyGenerateNarration}
                onChange={(e) => setStoryGenerateNarration(e.target.checked)}
                disabled={isLoading}
              />
              <label htmlFor="storyNarration">Generate Audio Narration</label>
            </div>
            <button onClick={handleGenerateStoryVideo} disabled={isLoading}>
              {isLoading ? 'Generating Story Video...' : 'Generate Story Video'}
            </button>
          </div>
        </section>

        <section className="generator-section">
          <h2>Reddit Video Generator</h2>
          <div className="input-section">
            <input
              type="text"
              value={subreddit}
              onChange={(e) => setSubreddit(e.target.value)}
              placeholder="Enter subreddit name (e.g., AskReddit)"
              disabled={isLoading}
              // Removed inline style, will be handled by general input styling or specific class if needed
            />
            <input
              type="text"
              value={redditYoutubeUrl}
              onChange={(e) => setRedditYoutubeUrl(e.target.value)}
              placeholder="Enter YouTube Background URL (optional)"
              disabled={isLoading}
              className="youtube-url-input"
            />
             <div className="file-input-container">
              <label htmlFor="bg-upload-reddit">Optional Background Image (overridden by YouTube URL):</label>
              <input
                type="file"
                id="bg-upload-reddit" 
                accept="image/*"
                onChange={handleFileChange} // This will also set the shared backgroundImageFile
                ref={redditFileInputRef} 
                disabled={isLoading}
              />
            </div>
            <div className="checkbox-container">
              <input
                type="checkbox"
                id="redditNarration"
                name="redditNarration"
                checked={redditGenerateNarration}
                onChange={(e) => setRedditGenerateNarration(e.target.checked)}
                disabled={isLoading}
              />
              <label htmlFor="redditNarration">Generate Audio Narration</label>
            </div>
            <button onClick={handleGenerateRedditVideo} disabled={isLoading}>
              {isLoading ? 'Generating Reddit Video...' : 'Generate Reddit Video'}
            </button>
          </div>
        </section>

        {error && <p className="error-message">{error}</p>}
        {isLoading && <p className="loading-message">Generating video, please wait...</p>}

        {videoUrl && !isLoading && (
          <div className="video-section">
            <h2>Generated Video</h2>
            <video controls src={videoUrl} width="640" height="480" key={videoUrl}>
              Your browser does not support the video tag.
            </video>
            {story && ( 
              <div className="story-section">
                <h3>{videoUrl.includes("story_") ? "Generated Story" : "Video Script/Title"}</h3>
                <p>{story}</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
