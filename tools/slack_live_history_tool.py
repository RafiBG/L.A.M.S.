import logging
from langchain_core.tools import tool

logger = logging.getLogger("SlackHistoryTool")

class SlackLiveHistoryTool:
    def __init__(self):
        self.history_pull_success = False
        self.history_pull_failed = False
        # Combined name cache for both human users and bot names
        self.name_cache = {}
        print("DEBUG: SlackHistory Tool Loaded with User Name Resolution")

    def _get_speaker_name(self, client, msg):
        """
        Helper method to resolve the real name of the speaker, 
        whether they are a human user or a bot/AI.
        """
        # 1. Check if it's a Bot/AI message
        bot_id = msg.get("bot_id")
        if bot_id:
            if bot_id in self.name_cache:
                return self.name_cache[bot_id]
            
            try:
                # Look up the bot's profile name
                response = client.bots_info(bot=bot_id)
                if response.get("ok"):
                    bot_name = response.get("bot", {}).get("name")
                    if bot_name:
                        resolved_name = f"{bot_name} (You)"
                    else:
                        resolved_name = "AI-Bot (You)" # Fallback if name field is empty
                        
                    self.name_cache[bot_id] = resolved_name
                    return resolved_name
            except Exception as e:
                logger.warning(f"Could not resolve bot name for {bot_id}: {e}")
            
            # Hard fallback default if API fails completely
            return "AI-Bot (You)"

        # 2. Check if it's a Human User message
        user_id = msg.get("user")
        if user_id:
            if user_id in self.name_cache:
                return self.name_cache[user_id]
            
            try:
                response = client.users_info(user=user_id)
                if response.get("ok"):
                    user_info = response.get("user", {})
                    profile = user_info.get("profile", {})
                    real_name = profile.get("display_name") or user_info.get("real_name") or user_info.get("name")
                    
                    self.name_cache[user_id] = real_name
                    return real_name
            except Exception as e:
                logger.warning(f"Could not resolve real name for user {user_id}: {e}")
            return user_id

        return "Unknown"

    def get_tool(self, client, conversation_id: str):
        slack_client = client
        raw_context = conversation_id

        @tool
        def pull_recent_slack_context(limit: int = 15) -> str:
            """
            Use this tool to pull the latest live messages from the current Slack channel 
            or thread. Use this if humans are talking among themselves without tagging you, 
            or when you need fresh, updated context regarding what was just discussed above.
            'limit' is an optional integer specifying how many messages back to read (default 15).
            """
            self.history_pull_success = True
            
            try:
                print(f"\n[Tool] AI Pulled live Slack History to read past {limit} messages for: {raw_context}\n")
                
                if "_" in raw_context:
                    channel_id, thread_ts = raw_context.split("_", 1)
                    response = slack_client.conversations_replies(
                        channel = channel_id,
                        ts = thread_ts,
                        limit = limit
                    )
                    is_threaded = True
                else:
                    channel_id = raw_context
                    response = slack_client.conversations_history(
                        channel=channel_id,
                        limit = limit
                    )
                    is_threaded = False

                if not response.get("ok"):
                    return f"Slack API reported an error fetching context: {response.get('error', 'Unknown Error')}"

                raw_messages = response.get("messages", [])
                
                if not is_threaded:
                    raw_messages.reverse()

                formatted_lines = []
                for msg in raw_messages:
                    text = msg.get("text", "").strip()
                    if not text:
                        continue
                    
                    # Pass the entire 'msg' map to our unified resolution helper
                    speaker = self._get_speaker_name(slack_client, msg)
                    formatted_lines.append(f"[{speaker}]: {text}")

                if not formatted_lines:
                    return "The requested history timeline returned no text messages."

                output_context = f"--- START OF RECENT LIVE SLACK HISTORY ({len(formatted_lines)} Messages) ---\n"
                output_context += "\n".join(formatted_lines)
                output_context += "\n--- END OF RECENT LIVE SLACK HISTORY ---"
                
                return output_context

            except Exception as e:
                self.history_pull_failed = True
                error_msg = f"Error executing live Slack history sync: {str(e)}"
                logger.error(error_msg)
                return error_msg

        return pull_recent_slack_context