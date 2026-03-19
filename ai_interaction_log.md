### Task: Set Up
**Prompt:** "Hello! with your help I will be building a functional ChatGPT-style chat application using Streamlit and the Hugging Face Inference API. The goal is to: [pasted in the goals] Remember this for future instructions; don't do anything yet. First I would like to Create and use a virtual environment -- .venv. [pasted in requirements]"
**AI Suggestion:** Established the overall project goals and confirmed that future steps should align with building a Streamlit chat app with Hugging Face API integration, multi-turn chat persistence, streaming, and a memory panel. Created a local `.venv`, installed `streamlit` and `requests` in that environment, updated `requirements.txt`, and verified that Streamlit was installed correctly from the virtual environment.
**My Modifications & Reflections:** No code changes.

### Task: Create Streamlit Configuration Files
**Prompt:** "Thanks! Create `.streamlit/secrets.toml` with a Hugging Face token entry and `.streamlit/config.toml` with a custom app theme."
**AI Suggestion:** Added an `HF_TOKEN` placeholder in `secrets.toml` and created a dark-themed Streamlit `config.toml` with custom colors and font settings.
**My Modifications & Reflections:** I changed the primary and background colors to deep purple/fuchsia because I liked them more! Then I pasted in my Hugging Face token.

### Task: Git Set Up
**Prompt:** "Help me set up git and GitHub early for deployment. Can you explain how to push my local project to GitHub and whether I should let GitHub create a `.gitignore` when making the repository?"
**AI Suggestion:** Added a file to exclude the secret.toml file, and Python cache files, then initialized a git repository, configured the local git username and email, created the initial commit, and renamed the branch to `main`. Suggested creating an empty GitHub repository with no README, no `.gitignore`, and no license, then connecting it with `git remote add origin ...` and uploading with `git push -u origin main`.
**My Modifications & Reflections:** The local git setup worked and I created the first commit successfully. I created an empty GitHub repo so the first push would just be simple. 

### Task: Part A: Page Setup & API Connection
**Prompt:** "Build Part A of the Streamlit chat app: set the page config, load the Hugging Face token from Streamlit secrets, send one hardcoded test message, display the model response, and show clear in-app errors instead of crashing when the token or API call fails."
**AI Suggestion:** Created a minimal `app.py` for Part A using native Streamlit components, a small sidebar scaffold to match the required layout, secure token loading, a single hardcoded API request to the Hugging Face Inference Router, and user-visible error handling for missing secrets, invalid tokens, rate limits, network issues, and malformed API responses.
**My Modifications & Reflections:** The code was successful! But first, my VS code terminal didn't display the necessary responses/load the browser app for a bit. I closed and reopened the terminal and it worked then.

### Task: Part B: Multi-Turn Conversation UI
**Prompt:** "Extend Part A into a real multi-turn chat interface using native Streamlit chat components, store the conversation in `st.session_state`, send the full history with each API request, and keep the input bar fixed at the bottom."
**AI Suggestion:** Replaced the hardcoded test message with a full workflow, rendered messages using `st.chat_message`, initialized a file to hold the conversation, sent the entire message history to the Hugging Face chat completions endpoint on each turn, and preserved the Part A error handling so API problems still show up in the app instead of crashing it.
**My Modifications & Reflections:** The updated app.py file compiled successfully with `python -m py_compile app.py`. I still need to test it in the browser by sending multiple messages in a row to confirm that the model keeps context and the input bar stays visible the way the assignment expects.

### Task: Part C: Chat Management
**Prompt:** "The next goal is to streamline the chat according to the following requirements (pasted in the prompt)".
**AI Suggestion:** Store all conversations and track selected one with .active_chat_id. App loads the saved files and sorts them. Rendered sidebar UI and formalized a deletion option that switches to the most recent file after deleting..
**My Modifications & Reflections:** I had to prompt the AI a few times to make the deletion work properly, then it was fine.

### Task: Part D: Chat Persistence
**Prompt:** "Now we want to have chats saved beyond a single session. Save everything as a separate JSON file and it should load in the next session."
**AI Suggestion:** Saved each convo as a JSON file so whenever it's started up, all are read and restored using `active_chat_id`. Deleting a chat would remove the matching file.
**My Modifications & Reflections:** No changes were necessary.
 
### Task 2: Response Streaming (20 points)
**Prompt:** "Display the model’s reply token-by-token as it is generated instead of waiting for the full response."
**AI Suggestion:** Updated the app to stream replies live from the Hugging Face API using stream=True and Streamlit’s native chat display. Each chunk was rendered as it arrived, then the full response was saved to chat history, with a short delay added so the streaming effect was visible. 
**My Modifications & Reflections:** No changes were necessary, it rendered in chunks correctly.


### Task 3: User Memory
**Prompt:** "Store user preferences and some tidbits about them (pasted in)"
 **AI Suggestion:** Extract user preferences and save it in `memory.json` - fields like name, interests, preferred lang, communication, etc. This is injected into future model requests as a system prompt.
  **AI Suggestion:** I tested this and found that after a few messages the app sidebar would start 'hallucinating' info I never shared (it started saying the user interests included some baseball player I've never heard of). The AI addressed this by tightening the prompts and the restrictions. It took some back and forth before it stopped.
