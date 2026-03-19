from datetime import datetime
import json
from pathlib import Path
import re
import time
from uuid import uuid4

import requests
import streamlit as st


API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "meta-llama/Llama-3.2-1B-Instruct"
CHATS_DIR = Path("chats")
MEMORY_PATH = Path("memory.json")
STREAM_DELAY_SECONDS = 0.02
DEFAULT_MEMORY = {
    "name": "",
    "preferred_language": "",
    "interests": [],
    "communication_style": "",
    "favorite_topics": [],
}


class ChatStreamError(Exception):
    pass


class MemoryExtractionError(Exception):
    pass


def load_hf_token():
    """Read the Hugging Face token from Streamlit secrets without crashing."""
    try:
        token = st.secrets["HF_TOKEN"]
    except Exception:
        return None

    if not token or not str(token).strip():
        return None

    return str(token).strip()


def stream_chat_reply(messages, hf_token: str):
    """Stream a reply from the Hugging Face router using server-sent events."""
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": 512,
        "stream": True,
    }

    try:
        with requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=(10, 60),
            stream=True,
        ) as response:
            if response.status_code == 401:
                raise ChatStreamError(
                    "Authentication failed. Check that your Hugging Face token is valid."
                )
            if response.status_code == 429:
                raise ChatStreamError(
                    "The Hugging Face API rate limit was reached. Please wait and try again."
                )
            if not response.ok:
                try:
                    error_payload = response.json()
                    error_message = error_payload.get("error") or error_payload.get("message")
                except ValueError:
                    error_message = response.text.strip() or "Unknown API error."
                raise ChatStreamError(
                    f"Hugging Face API error ({response.status_code}): {error_message}"
                )

            saw_content = False

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if not raw_line.startswith("data: "):
                    continue

                data_line = raw_line[6:].strip()
                if data_line == "[DONE]":
                    break

                try:
                    chunk_data = json.loads(data_line)
                except json.JSONDecodeError:
                    continue

                choices = chunk_data.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                chunk_text = delta.get("content")

                if not chunk_text:
                    continue

                saw_content = True
                yield chunk_text
                time.sleep(STREAM_DELAY_SECONDS)

            if not saw_content:
                raise ChatStreamError("The API returned an empty streamed response.")
    except requests.exceptions.Timeout as exc:
        raise ChatStreamError(
            "The request timed out. Hugging Face may be busy, so please try again."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise ChatStreamError(
            "A network error occurred while contacting the Hugging Face API."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ChatStreamError(f"An unexpected request error occurred: {exc}") from exc


def extract_json_object(text: str):
    text = text.strip()
    if not text:
        return {}

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def timestamp_now():
    return datetime.now().isoformat(timespec="seconds")


def format_timestamp(timestamp_str: str):
    return datetime.fromisoformat(timestamp_str).strftime("%b %d, %I:%M %p")


def build_chat_title(messages):
    for message in messages:
        if message["role"] == "user" and message["content"].strip():
            title = message["content"].strip()
            return title[:27] + "..." if len(title) > 30 else title
    return "New Chat"


def build_memory_system_prompt(memory):
    if not has_meaningful_memory(memory):
        return None

    memory_json = json.dumps(memory, indent=2)
    return (
        "You are a helpful AI assistant. Personalize your responses when appropriate "
        "using the user's saved preferences and facts below. Do not mention the memory "
        "store unless it is directly relevant.\n\n"
        f"User memory:\n{memory_json}"
    )


def build_model_messages(chat_messages, memory):
    model_messages = []
    system_prompt = build_memory_system_prompt(memory)
    if system_prompt:
        model_messages.append({"role": "system", "content": system_prompt})
    model_messages.extend(chat_messages)
    return model_messages


def create_chat():
    now = timestamp_now()
    return {
        "id": str(uuid4()),
        "title": "New Chat",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }


def get_chat_path(chat_id: str):
    return CHATS_DIR / f"{chat_id}.json"


def load_memory():
    if not MEMORY_PATH.exists():
        return dict(DEFAULT_MEMORY)

    try:
        memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_MEMORY)

    if not isinstance(memory, dict):
        return dict(DEFAULT_MEMORY)

    return normalize_memory(memory)


def save_memory(memory):
    MEMORY_PATH.write_text(json.dumps(memory, indent=2), encoding="utf-8")


def clear_memory():
    st.session_state.memory = dict(DEFAULT_MEMORY)
    save_memory(st.session_state.memory)


def normalize_text_list(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []

    cleaned = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def normalize_memory(memory):
    normalized = dict(DEFAULT_MEMORY)

    if not isinstance(memory, dict):
        return normalized

    if isinstance(memory.get("name"), str):
        normalized["name"] = memory["name"].strip()

    if isinstance(memory.get("preferred_language"), str):
        normalized["preferred_language"] = memory["preferred_language"].strip()

    if isinstance(memory.get("communication_style"), str):
        normalized["communication_style"] = memory["communication_style"].strip()

    interests = []
    for key in ("interests", "hobbies", "likes"):
        interests.extend(normalize_text_list(memory.get(key)))
    normalized["interests"] = normalize_text_list(interests)

    normalized["favorite_topics"] = normalize_text_list(memory.get("favorite_topics"))
    if not normalized["favorite_topics"]:
        normalized["favorite_topics"] = normalize_text_list(memory.get("topics"))

    return normalized


def has_meaningful_memory(memory):
    normalized = normalize_memory(memory)
    return any(
        [
            normalized["name"],
            normalized["preferred_language"],
            normalized["communication_style"],
            normalized["interests"],
            normalized["favorite_topics"],
        ]
    )


def merge_memory(existing, updates):
    merged = normalize_memory(existing)
    updates = normalize_memory(updates)

    for key in ("name", "preferred_language", "communication_style"):
        if updates[key]:
            merged[key] = updates[key]

    for key in ("interests", "favorite_topics"):
        merged[key] = normalize_text_list(merged[key] + updates[key])

    return merged


def heuristic_memory_from_message(user_message: str):
    message = user_message.strip()
    lowered = message.lower()
    memory = dict(DEFAULT_MEMORY)

    name_patterns = [
        r"\bmy name is ([A-Z][a-zA-Z'-]+)\b",
        r"\bi am ([A-Z][a-zA-Z'-]+)\b",
        r"\bi'm ([A-Z][a-zA-Z'-]+)\b",
        r"\bit's ([A-Z][a-zA-Z'-]+)\b",
        r"\bcall me ([A-Z][a-zA-Z'-]+)\b",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            memory["name"] = match.group(1)
            break

    if "concise" in lowered or "brief" in lowered or "short" in lowered:
        memory["communication_style"] = "concise"
    elif "detailed" in lowered or "in depth" in lowered or "in-depth" in lowered:
        memory["communication_style"] = "detailed"

    interest_patterns = [
        r"\bi like ([^.!\n]+)",
        r"\bi love ([^.!\n]+)",
        r"\bi enjoy ([^.!\n]+)",
        r"\bi'm interested in ([^.!\n]+)",
    ]
    extracted_interests = []
    for pattern in interest_patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        raw_value = match.group(1)
        raw_value = raw_value.replace(" and ", ",")
        for item in raw_value.split(","):
            cleaned = item.strip(" .!")
            if cleaned:
                extracted_interests.append(cleaned)

    memory["interests"] = normalize_text_list(extracted_interests)
    return normalize_memory(memory)


def extract_user_memory(user_message, hf_token: str):
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract only explicit personal facts or preferences from the user's message. "
                    "Do not guess or infer anything. Return only valid JSON using exactly this "
                    "schema: {\"name\":\"\",\"preferred_language\":\"\",\"interests\":[],"
                    "\"communication_style\":\"\",\"favorite_topics\":[]}. "
                    "Use empty strings or empty arrays for missing values. "
                    "If the message does not explicitly state a field, leave it empty."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 150,
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    except requests.exceptions.Timeout as exc:
        raise MemoryExtractionError("Memory extraction timed out.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise MemoryExtractionError("Memory extraction could not reach the API.") from exc
    except requests.exceptions.RequestException as exc:
        raise MemoryExtractionError(f"Memory extraction request failed: {exc}") from exc

    if not response.ok:
        raise MemoryExtractionError(
            f"Memory extraction failed with status {response.status_code}."
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise MemoryExtractionError("Memory extraction returned an unexpected format.") from exc

    return normalize_memory(extract_json_object(content))


def save_chat(chat):
    CHATS_DIR.mkdir(exist_ok=True)
    chat["updated_at"] = timestamp_now()
    get_chat_path(chat["id"]).write_text(json.dumps(chat, indent=2), encoding="utf-8")


def delete_chat_file(chat_id: str):
    chat_path = get_chat_path(chat_id)
    if chat_path.exists():
        chat_path.unlink()


def load_chats_from_disk():
    CHATS_DIR.mkdir(exist_ok=True)
    chats = []

    for chat_file in sorted(CHATS_DIR.glob("*.json")):
        try:
            chat = json.loads(chat_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(chat, dict):
            continue

        if "id" not in chat or "messages" not in chat:
            continue

        chat.setdefault("title", "New Chat")
        chat.setdefault("created_at", timestamp_now())
        chat.setdefault("updated_at", chat["created_at"])
        chats.append(chat)

    return sorted(chats, key=lambda chat: chat["updated_at"], reverse=True)


def set_active_chat(chat_id: str):
    st.session_state.active_chat_id = chat_id


def add_new_chat():
    chat = create_chat()
    st.session_state.chats.insert(0, chat)
    save_chat(chat)
    set_active_chat(chat["id"])


def delete_chat(chat_id: str):
    chats = st.session_state.chats
    chat_index = next((index for index, chat in enumerate(chats) if chat["id"] == chat_id), None)
    if chat_index is None:
        return

    was_active = st.session_state.active_chat_id == chat_id
    del chats[chat_index]
    delete_chat_file(chat_id)

    if not chats:
        st.session_state.active_chat_id = None
        return

    if was_active:
        replacement_chat = max(chats, key=lambda chat: chat["updated_at"])
        set_active_chat(replacement_chat["id"])


def get_active_chat():
    active_chat_id = st.session_state.active_chat_id
    if not active_chat_id:
        return None

    return next((chat for chat in st.session_state.chats if chat["id"] == active_chat_id), None)


def initialize_session_state():
    if "chats" not in st.session_state:
        loaded_chats = load_chats_from_disk()
        st.session_state.chats = loaded_chats or [create_chat()]
        if not loaded_chats:
            save_chat(st.session_state.chats[0])
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = st.session_state.chats[0]["id"]
    if "memory" not in st.session_state:
        st.session_state.memory = load_memory()
        if not MEMORY_PATH.exists() or not MEMORY_PATH.read_text(encoding="utf-8").strip():
            save_memory(st.session_state.memory)


def render_sidebar():
    st.sidebar.header("Chats")
    if st.sidebar.button("New Chat", use_container_width=True, type="primary"):
        add_new_chat()
        st.rerun()

    with st.sidebar.expander("User Memory", expanded=True):
        if st.button("Clear Memory", use_container_width=True):
            clear_memory()
            st.rerun()

        if st.session_state.memory:
            st.json(normalize_memory(st.session_state.memory), expanded=True)
        else:
            st.caption("No saved user memory yet.")

    st.sidebar.divider()
    st.sidebar.subheader("Recent Chats")

    if not st.session_state.chats:
        st.sidebar.caption("No chats yet. Click `New Chat` to start a conversation.")
        return

    sorted_chats = sorted(
        st.session_state.chats,
        key=lambda chat: chat["updated_at"],
        reverse=True,
    )

    for chat in sorted_chats:
        is_active = chat["id"] == st.session_state.active_chat_id
        button_cols = st.sidebar.columns([5, 1])

        with button_cols[0]:
            if st.button(
                chat["title"],
                key=f"chat_select_{chat['id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                set_active_chat(chat["id"])
                st.rerun()

        with button_cols[1]:
            if st.button("✕", key=f"chat_delete_{chat['id']}", use_container_width=True):
                delete_chat(chat["id"])
                st.rerun()

        st.sidebar.caption(format_timestamp(chat["updated_at"]))


def main():
    st.set_page_config(page_title="My AI Chat", layout="wide")

    initialize_session_state()
    render_sidebar()

    st.title("My AI Chat")
    st.caption("Task 3: streamed chat with persistent history and user memory.")

    hf_token = load_hf_token()
    if hf_token is None:
        st.error(
            "Missing Hugging Face token. Add `HF_TOKEN` to `.streamlit/secrets.toml` to use the chat app."
        )
        return

    active_chat = get_active_chat()
    if active_chat is None:
        st.info("No active chat. Create a new chat from the sidebar to get started.")
        return

    for message in active_chat["messages"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if not active_chat["messages"]:
        st.info("Start the conversation by sending your first message below.")

    user_prompt = st.chat_input("Type a message and press Enter")
    if not user_prompt:
        return

    user_message = {"role": "user", "content": user_prompt}
    active_chat["messages"].append(user_message)
    active_chat["title"] = build_chat_title(active_chat["messages"])
    save_chat(active_chat)
    with st.chat_message("user"):
        st.write(user_prompt)

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(
                stream_chat_reply(
                    build_model_messages(active_chat["messages"], st.session_state.memory),
                    hf_token,
                )
            )
        except ChatStreamError as error:
            st.error(str(error))
            return

    assistant_message = {"role": "assistant", "content": reply}
    active_chat["messages"].append(assistant_message)
    save_chat(active_chat)

    try:
        model_memory_updates = extract_user_memory(user_prompt, hf_token)
    except MemoryExtractionError:
        model_memory_updates = dict(DEFAULT_MEMORY)

    memory_updates = merge_memory(
        heuristic_memory_from_message(user_prompt),
        model_memory_updates,
    )
    if memory_updates:
        st.session_state.memory = merge_memory(st.session_state.memory, memory_updates)
        save_memory(st.session_state.memory)


if __name__ == "__main__":
    main()
