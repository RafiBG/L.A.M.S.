import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
# Use these specific paths for version 0.3
from langchain.agents import AgentExecutor
from langchain.agents import create_tool_calling_agent
# Tools
from tools.time_tool import get_current_date, get_current_time
from tools.serper_web_search import SerperSearchTool
from tools.comfy_tool import ComfyUIImageTool
from tools.music_generation_tool import MusicGenerationTool
from tools.python_executor_tool import PythonExecutorTool
from config import Config

class LLMService:
    def __init__(self, config: Config) -> None:
        self.config = config
        custom_client = httpx.Client(verify=False)
        self.llm_params = {
            "openai_api_key": config.API_KEY,
            "base_url": config.LOCAL_HOST,
            "model_name": config.MODEL,
            "temperature": 0.7
        }

        self.vision_llm = ChatOpenAI(
            openai_api_key=config.API_KEY,
            base_url=config.LOCAL_HOST,
            model_name=config.VISION_MODEL,
            temperature=0.2,
            http_client=custom_client
        )
        
        self.history_db = {} 
        self.serper_web_search_tool = SerperSearchTool(config.SERPER_API_KEY)
        self.comfy_image_tool = ComfyUIImageTool(config)
        self.music_generation_tool = MusicGenerationTool(config)
        self.python_tool = PythonExecutorTool(config)
        
        # Base tools list
        self.tools = [
            get_current_date,
            get_current_time,
            self.serper_web_search_tool.get_web_tool(),
            self.comfy_image_tool.get_tool(),
            self.music_generation_tool.get_tool(),
            self.python_tool.get_tool(),
        ]

    def generate_reply(self, conversation_id: str, prompt: str, images=None) -> str:
        if conversation_id not in self.history_db:
            self.history_db[conversation_id] = []

        images_present = False
        final_prompt = prompt

        # If images exist, describe them via Vision LLM first
        if images and len(images) > 0:
            images_present = True
            image_description = self._describe_images(images, prompt)
            final_prompt = (
                "The user uploaded image(s).\n"
                "Here is a description of what is in the image(s):\n"
                f"{image_description}\n\n"
                f"User's actual question about these images: {prompt}"
            )

        # Run the agent with the (possibly enhanced) prompt
        response = self._run_agent(conversation_id, final_prompt, images_present=images_present)
        return response

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

    def _run_agent(self, conversation_id, prompt, images_present=False):
        llm = ChatOpenAI(**self.llm_params)

        # Disable image generation tool if the user is currently asking about an image 
        # (prevents the bot from trying to "generate" a fix for an uploaded image)
        active_tools = self.tools
        if images_present:
            active_tools = [t for t in self.tools if t.name != "generate_comfy_image"]

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.SYSTEM_MESSAGE),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Use the modern agent creation function
        agent = create_tool_calling_agent(llm, active_tools, chat_prompt)

        agent_executor = AgentExecutor(
            agent=agent,
            tools=active_tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3
        )

        # Build execution input
        history = self.history_db[conversation_id]
        
        result = agent_executor.invoke({
            "input": prompt,
            "history": history
        })

        response = result.get("output", "I'm sorry, I couldn't process that.")

        # Update History
        self.history_db[conversation_id].append(HumanMessage(content=prompt))
        self.history_db[conversation_id].append(AIMessage(content=response))

        # Memory Trimming
        max_messages = int(self.config.SHORT_MEMORY) * 2
        if len(self.history_db[conversation_id]) > max_messages:
            self.history_db[conversation_id] = \
            self.history_db[conversation_id][-max_messages:]

        return response
    
    def clear_memory(self, conversation_id: str) -> None:
        if conversation_id in self.history_db:
            del self.history_db[conversation_id]