from click import prompt
import httpx, re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import trim_messages
# Specific paths for version 0.3
from langchain.agents import AgentExecutor
from langchain.agents import create_tool_calling_agent
# Tools
from tools.time_tool import get_current_date, get_current_time
from tools.serper_web_tool import SerperSearchTool
from tools.comfy_tool import ComfyUIImageTool
from tools.music_generation_tool import MusicGenerationTool
from tools.python_executor_tool import PythonExecutorTool
from tools.memory_tool import MemoryTool
from tools.searxng_web_tool import SearXNGTool
from tools.website_reader_tool import WebsiteReaderTool

from services.memory_service import MemoryService
from config import Config

class SlackStreamingHandler(BaseCallbackHandler):
    def __init__(self, callback_fn):
        self.callback_fn = callback_fn
        self.full_content = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.full_content += token
        # Trigger the Slack update for every new token
        self.callback_fn(self.full_content, is_final=False)

class LLMService:
    def __init__(self, config: Config) -> None:
        self.config = config
        custom_client = httpx.Client(verify=False)

        # Provider
        provider = config.PROVIDER.lower()
        if provider == "ollama":
            llm_base_url = config.OLLAMA_HOST
        elif provider == "lmstudio":
            llm_base_url = config.LM_STUDIO_HOST or "http://localhost:1234/v1"
        elif provider == "openai":
            llm_base_url = config.OPEN_AI_HOST or "https://api.openai.com/v1"
        else:
            raise ValueError(f"Unsupported provider: {config.PROVIDER}")
        
        if config.SEARCH_PROVIDER.lower() == "searxng":
            self.searxng_tool = SearXNGTool(config.SEARXNG_HOST, config.SEARCH_LIMIT, config.SEARXNG_ENGINES) 
            web_tool = self.searxng_tool.get_tool()
            print(f"DEBUG: Web Search initialized using SearXNG at {config.SEARXNG_HOST}")
        else:
            self.search_engine = SerperSearchTool(config.SERPER_API_KEY, config.SEARCH_LIMIT)
            web_tool = self.search_engine.get_web_tool()
            print(f"DEBUG: Web Search initialized using Serper API")

        self.llm_params = {
            "openai_api_key": config.API_KEY,
            "base_url": llm_base_url,
            "model_name": config.MODEL,
            "temperature": 0.7,
        }

        self.llm = ChatOpenAI(**self.llm_params, http_client=custom_client)

        self.vision_llm = ChatOpenAI(
            openai_api_key = config.API_KEY,
            base_url = llm_base_url,
            model_name = config.VISION_MODEL,
            temperature = 0.2,
            http_client = custom_client
        )

        self.history_db = {} 
        self.serper_web_search_tool = SerperSearchTool(config.SERPER_API_KEY, config.SEARCH_LIMIT)
        self.comfy_image_tool = ComfyUIImageTool(config)
        self.music_generation_tool = MusicGenerationTool(config)
        self.python_tool = PythonExecutorTool(config)

        self.memory_service = MemoryService(config)
        
        self.memory_tool = MemoryTool(self.memory_service, "default")
        self.python_tool = PythonExecutorTool(config)
        self.comfy_image_tool = ComfyUIImageTool(config)
        self.music_generation_tool = MusicGenerationTool(config)
        self.read_url_tool = WebsiteReaderTool()

        # Base tools list static
        self.base_tools = [
        get_current_date,
        get_current_time,            
        web_tool, # This will now be EITHER SearXNG or Serper
        self.comfy_image_tool.get_tool(),
        self.music_generation_tool.get_tool(),
        self.python_tool.get_tool(),
        *self.read_url_tool.get_tool()
]
    # Generate Reply is not used anymore but keeping for reference if needed for non-streaming in the future. 
    # The main method now is generate_reply_stream which handles both streaming and non-streaming based on the callback function provided.
    def generate_reply(self, conversation_id: str, prompt: str, images = None) -> str:
        if conversation_id not in self.history_db:
            self.history_db[conversation_id] = []

        images_present = False
        final_prompt = prompt
        pass_images_to_agent = None

        if images and len(images) > 0:
            images_present = True
            # Proxy Mode (Describe first)
            if self.config.VISION_MODE == "proxy_vision":
                image_description = self._describe_images(images, prompt)
                final_prompt = (
                    "The user uploaded image(s).\n"
                    "Description of image(s):\n"
                    f"{image_description}\n\n"
                    f"User's question: {prompt}"
                )
                #print(f"[Debug Proxy Vision] Using model for vision: {self.config.VISION_MODEL} in mode {self.config.VISION_MODE}")
                # Main Vision Mode
            else:
                pass_images_to_agent = images
                #print(f"[Debug Main Vision] Using model for vision: {self.config.VISION_MODEL} in mode {self.config.VISION_MODE}")

        # Run the agent
        response = self._run_agent(
            conversation_id,
            final_prompt,
            images_present = images_present,
            raw_images = pass_images_to_agent,
        )
        
        return response

    def generate_reply_stream(self, conversation_id: str, prompt: str, callback_fn, images=None):
        if conversation_id not in self.history_db:
            self.history_db[conversation_id] = []

        images_present = bool(images and len(images) > 0)
        final_prompt = prompt
        pass_images_to_agent = None

        if images_present:
            if self.config.VISION_MODE == "proxy_vision":
                image_description = self._describe_images(images, prompt)
                final_prompt = f"The user uploaded image(s).\nDescription: {image_description}\n\nUser Question: {prompt}"
            else:
                pass_images_to_agent = images

        stream_handler = SlackStreamingHandler(callback_fn)

        llm = ChatOpenAI(
            **self.llm_params, 
            streaming=True, 
            callbacks=[stream_handler] 
        )
    
        self.memory_tool.conversation_id = conversation_id
        active_tools = self.base_tools + self.memory_tool.get_tools()
    
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.SYSTEM_MESSAGE),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="input"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, active_tools, chat_prompt)
        agent_executor = AgentExecutor(agent=agent, tools=active_tools, verbose=True, handle_parsing_errors=True)

        raw_history = self.history_db.get(conversation_id, [])
        history = self._get_trimmed_history(raw_history, llm)
    
        if pass_images_to_agent and self.config.VISION_MODE == "main_vision":
            content = [{"type": "text", "text": final_prompt}]
            for img in pass_images_to_agent:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img['base64']}"}})
            agent_input = [HumanMessage(content=content)]
        else:
            agent_input = [HumanMessage(content=final_prompt)]

        try:
            result = agent_executor.invoke({"input": agent_input, "history": history})
            full_response = result.get("output", "")
        
            # Final cleanup and status tags
            final_cleaned = self._strip_thinking(full_response) if not self.config.SHOW_THINKING else full_response
            callback_fn(final_cleaned, is_final=True)

            # Update History
            self.history_db[conversation_id].append(HumanMessage(content=prompt))
            self.history_db[conversation_id].append(AIMessage(content=final_cleaned))
            return final_cleaned

        except Exception as e:
            print(f"Streaming Error: {e}")
            callback_fn("", is_final=True) 
            return "[Error] Slack may send a retry while bot is thinking."

    def _describe_images(self, images, user_prompt):
        content = [{
            "type": "text",
            "text": f"Analyze these images. User question: {user_prompt}"
        }]

        for img in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img['base64']}"}
            })

        vision_response = self.vision_llm.invoke([
            ("system", "You are a helpful assistant that describes images for a tool-using agent."),
            HumanMessage(content=content)
        ])
        return vision_response.content

    def _run_agent(self, conversation_id, prompt, images_present=False, raw_images=None):
        if raw_images and self.config.VISION_MODE == "main_vision":
            llm = self.vision_llm
        else:
            llm = ChatOpenAI(**self.llm_params)

        # Aggressive Tool Filtering
        self.memory_tool.conversation_id = conversation_id # Update the ID for this chat
        active_tools = self.base_tools + self.memory_tool.get_tools()

        if images_present:
            forbidden_tools = ["generate_comfy_image", "search_memory"]
            active_tools = [t for t in active_tools if getattr(t, 'name', '') not in forbidden_tools]

        safe_prompt = prompt if (prompt and prompt.strip()) else "Describe this image in detail."

    # Construct working payload
        if raw_images and self.config.VISION_MODE == "main_vision":
            content = [{
                "type": "text",
                "text": f"SYSTEM: You are currently looking at an image. Answer the user's question based ONLY on what you see.\nUSER: {safe_prompt}"
            }]
            for img in raw_images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img['base64']}"}
                })
            agent_input_message = [HumanMessage(content=content)]
        else:
            agent_input_message = [HumanMessage(content=safe_prompt)]

        # Prompt
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.SYSTEM_MESSAGE),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="input"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, active_tools, chat_prompt)

        agent_executor = AgentExecutor(
            agent=agent,
            tools=active_tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=4
        )

        raw_history = self.history_db.get(conversation_id, [])
        history = self._get_trimmed_history(raw_history, llm)


        try:
            result = agent_executor.invoke({
                "input": agent_input_message,
                "history": history
            })
            response = result.get("output", "")
        except Exception as e:
            print(f"Error: {e}")
            response = "I am having trouble answering. Check the AI server if is running and the configuration."

        if self.config.SHOW_THINKING == False:
            response = self._strip_thinking(response)

        # History Management
        if conversation_id not in self.history_db:
            self.history_db[conversation_id] = []

        return response
    
    def clear_memory(self, conversation_id: str) -> None:
        if conversation_id in self.history_db:
            del self.history_db[conversation_id]

    def _strip_thinking(self, text: str) -> str:
        """Removes reasoning blocks from the output."""
        # Removes everything between <think> and </think>
        text = re.sub(r"<think>[\s\S]*?</think>", "", text)
        # DeepSeek <thought> and </thought>
        text = re.sub(r"\[thought\][\s\S]*?\[/thought\]", "", text,)
        return text.strip()
    
    def quick_query(self, prompt: str) -> str:
        try:
            # Temperature 0 for strict decisions
            response = self.llm.invoke(prompt, temperature=0)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            print(f"LLM Quick Query Error: {e}")
            return "no"
        
    def get_latest_search_info(self):
        """Returns a tuple of (provider_name, links_list)"""
        links = []

        # Check SearXNG
        if hasattr(self, "searxng_tool") and self.searxng_tool.latest_links:
            links.extend(self.searxng_tool.latest_links)
            self.searxng_tool.latest_links = [] # Clear links to not appear in next message
            return "SearXNG", links

        # Check Serper
        if hasattr(self, 'search_engine') and self.search_engine.latest_links:
            links = list(self.search_engine.latest_links)
            self.search_engine.latest_links = [] # Clear
            return "Serper", links


        return None, []
    
    def _get_trimmed_history(self, history, llm = None):
        def simple_counts(messages):
            # Fallback: roughly 1 token per 4 characters
            total_chars = sum(len(str(m.content)) for m in messages)
            return total_chars // 4

        return trim_messages(
            history,
            token_counter=simple_counts,
            max_tokens=self.config.MAX_TOKENS, 
            strategy="last",
            start_on="human",
            include_system=True,
        )